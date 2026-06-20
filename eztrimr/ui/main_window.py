import config
import os
import subprocess
import tempfile
from PyQt6.QtCore import Qt, QSize, QSettings, QTimer, QDateTime, QUrl, QEasingCurve, QPropertyAnimation
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink, QVideoFrame
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QShortcut, QKeySequence, QTransform
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
    QMessageBox,
    QFileDialog,
    QComboBox
)
from eztrimr.ui import theme
from eztrimr.ui.widgets.file_info import FileInfoPanel
from eztrimr.ui.widgets.preview import PreviewWidget
from eztrimr.ui.widgets.settings_panel import SettingsPanel
from eztrimr.ui.widgets.timeline import TimelineWidget
from eztrimr.core.state import app_state
from eztrimr.core.preview import PreviewFrameWorker
from eztrimr.core.processor import FFmpegWorker, build_trim_command, build_merge_command
from eztrimr.core.timecode import seconds_to_timecode


def get_media_duration(file_path: str) -> float:
    """Synchronously queries the duration of a file using ffprobe for progress calibration."""
    cmd = [
        config.FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file_path
    ]
    try:
        import json
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        if res.returncode == 0:
            data = json.loads(res.stdout.decode("utf-8", errors="replace"))
            return float(data.get("format", {}).get("duration", 0.0))
    except Exception:
        pass
    return 0.0


class AnimatedStatusIcon(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.animation_type = None  # "waveform" or "film"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.tick = 0
        self.angle = 0

    def start(self, animation_type: str) -> None:
        self.animation_type = animation_type
        self.tick = 0
        self.angle = 0
        self.timer.start(80)  # 80ms interval
        self.show()

    def stop(self) -> None:
        self.timer.stop()
        self.animation_type = None
        self.hide()

    def update_animation(self) -> None:
        self.tick += 1
        if self.animation_type == "film":
            self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        from eztrimr.ui.theme import get_token
        accent_color = get_token("accent") or QColor("#007acc")
        
        if self.animation_type == "waveform":
            import math
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent_color)
            for i in range(3):
                h = 7 + 5 * math.sin(self.tick * 0.4 + i * 1.5)
                x = 2 + i * 5
                y = 8 - h / 2
                painter.drawRoundedRect(x, int(y), 3, int(h), 1, 1)
        elif self.animation_type == "film":
            from eztrimr.ui.icons import EZIcon
            pix = EZIcon.get("film", 16, accent_color)
            if not pix.isNull():
                painter.translate(8, 8)
                painter.rotate(self.angle)
                painter.drawPixmap(-8, -8, pix)
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.setMinimumSize(960, 600)
        self.resize(1280, 720)

        # Enable drag and drop
        self.setAcceptDrops(True)

        # Active workers and resources
        self.active_preview_worker = None
        self.pending_preview_timestamp = None
        self.ffmpeg_worker = None
        self.current_concat_file = None

        # Phase 5 Audio workers & cache
        self.audio_analyser = None
        self.audio_preview_thread = None
        self.temp_preview_files = []

        # Playback system
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.on_playback_tick)
        self.last_playback_time = 0
        self.last_preview_frame_time = 0

        # Native media player for audio and video playback
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)

        # Initialize Menu Bar
        self.init_menu_bar()

        # Central Widget & Vertical Layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- ZONE 1: TOOLBAR (44px) ---
        self.init_toolbar()

        # --- MIDDLE SPLITTER AREA (flex) ---
        self.init_middle_area()

        # Link native video output to the stacked video widget
        self.media_player.setVideoOutput(self.center_panel.video_widget)

        # --- ZONE 5: TIMELINE (110px) ---
        self.init_timeline()

        # --- ZONE 6: STATUS BAR (28px) ---
        self.init_status_bar()

        # --- INITIALIZE BUTTON ICONS ---
        self.update_button_icons()

        # Connect toolbar button actions
        self.open_button.clicked.connect(self.open_file_dialog)
        self.add_button.clicked.connect(self.add_current_to_queue)
        self.export_button.clicked.connect(self.on_export_clicked)

        # Connect preview inputs and play button
        self.center_panel.in_input.timeChanged.connect(self.on_input_in_changed)
        self.center_panel.out_input.timeChanged.connect(self.on_input_out_changed)
        self.center_panel.play_button.clicked.connect(self.toggle_playback)

        # Connect timeline widget signals
        self.timeline_widget.inPointChanged.connect(self.on_timeline_in_changed)
        self.timeline_widget.outPointChanged.connect(self.on_timeline_out_changed)
        self.timeline_widget.playheadChanged.connect(self.on_timeline_playhead_changed)
        self.timeline_widget.playheadReleased.connect(self.on_timeline_playhead_released)
        self.timeline_widget.trimReleased.connect(self.on_timeline_trim_released)

        # Connect settings panel audio/video signals
        self.right_panel.volumeChanged.connect(self.on_audio_setting_changed)
        self.right_panel.normalizeToggled.connect(self.on_audio_setting_changed)
        self.right_panel.muteToggled.connect(self.on_audio_setting_changed)
        self.right_panel.extractToggled.connect(self.on_audio_setting_changed)
        self.right_panel.extractFormatChanged.connect(self.on_audio_setting_changed)
        self.right_panel.videoFormatChanged.connect(self.on_video_format_changed)
        self.right_panel.videoCodecChanged.connect(self.on_audio_setting_changed)
        self.right_panel.videoCrfChanged.connect(self.on_audio_setting_changed)
        self.right_panel.videoResolutionChanged.connect(self.on_audio_setting_changed)
        self.right_panel.videoFpsChanged.connect(self.on_audio_setting_changed)
        self.right_panel.previewRequested.connect(self.on_audio_preview_requested)

        # Connect global format selector signals
        self.format_combo.currentTextChanged.connect(self.on_toolbar_format_changed)

        # Connect queue list changes to update Export button states
        self.left_panel.queueChanged.connect(self.update_export_button_state)
        self.left_panel.mergeExportRequested.connect(self.export_merge)

        # Keyboard shortcuts
        self.delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.left_panel.queue_list)
        self.delete_shortcut.activated.connect(self.left_panel.remove_selected)

        # Undo stack for trim operations
        self.undo_stack = []

        # Connect openFileRequested from the preview panel
        self.center_panel.openFileRequested.connect(self.open_file_dialog)

        # Initialize all keyboard shortcuts
        self.init_shortcuts()

        # Restore geometry/state/splitter
        settings = QSettings("EZTrimr", "EZTrimr")
        geom = settings.value("window/geometry")
        state = settings.value("window/state")
        splitter_state = settings.value("window/splitter")
        if geom:
            self.restoreGeometry(geom)
        if state:
            self.restoreState(state)
        if splitter_state:
            self.splitter.restoreState(splitter_state)

    def update_export_button_state(self) -> None:
        """Enables export button if a file is loaded or if there are items in the merge queue."""
        has_media = bool(app_state.file_path)
        has_merge_items = len(app_state.merge_files) > 0
        self.export_button.setEnabled(has_media or has_merge_items)
        self.update_button_icons()

    def init_toolbar(self) -> None:
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("toolbarFrame")
        toolbar_frame.setFixedHeight(44)
        
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(12, 0, 12, 0)
        toolbar_layout.setSpacing(8)

        # Left side items
        self.app_title = QLabel(config.APP_NAME)
        self.app_title.setObjectName("appTitleLabel")
        toolbar_layout.addWidget(self.app_title)

        # Separator (1px vertical line, 20px tall)
        sep = QFrame()
        sep.setObjectName("toolbarSeparator")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        toolbar_layout.addWidget(sep)

        # Open File Button
        self.open_button = QPushButton("Open File")
        self.open_button.setIconSize(QSize(16, 16))
        toolbar_layout.addWidget(self.open_button)

        # Add to List Button
        self.add_button = QPushButton("Add to List")
        self.add_button.setIconSize(QSize(16, 16))
        self.add_button.setEnabled(False)  # Disabled until file loaded
        toolbar_layout.addWidget(self.add_button)

        # Spacer in the middle
        toolbar_layout.addStretch()

        # Right side items
        # Export Button (Accent colored in QSS when enabled)
        self.export_button = QPushButton("Export")
        self.export_button.setObjectName("exportButton")
        self.export_button.setIconSize(QSize(16, 16))
        self.export_button.setEnabled(False)  # Disabled until file loaded
        toolbar_layout.addWidget(self.export_button)

        # Output Format Selector
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MKV", "MOV", "AVI", "WEBM", "MP3", "OGG"])
        self.format_combo.setObjectName("toolbarFormatCombo")
        self.format_combo.setFixedWidth(80)
        toolbar_layout.addWidget(self.format_combo)

        self.main_layout.addWidget(toolbar_frame)

    def init_middle_area(self) -> None:
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)

        # 1. Left Panel (File Info & Merge Queue)
        self.left_panel_container = QFrame()
        self.left_panel_container.setObjectName("leftPanelFrame")
        left_layout = QVBoxLayout(self.left_panel_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.left_panel = FileInfoPanel()
        left_layout.addWidget(self.left_panel)
        
        # 2. Center Panel (Video Preview & Timecode)
        self.center_panel = PreviewWidget()

        # 3. Right Panel (Settings Tabs)
        self.right_panel_container = QFrame()
        self.right_panel_container.setObjectName("rightPanelFrame")
        right_layout = QVBoxLayout(self.right_panel_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.right_panel = SettingsPanel()
        right_layout.addWidget(self.right_panel)

        # Add to splitter
        self.splitter.addWidget(self.left_panel_container)
        self.splitter.addWidget(self.center_panel)
        self.splitter.addWidget(self.right_panel_container)

        self.left_panel_container.setMinimumWidth(150)
        self.center_panel.setMinimumWidth(400)
        self.right_panel_container.setMinimumWidth(240)
        
        self.main_layout.addWidget(self.splitter)
        self.splitter.setSizes([220, 800, 260])

    def init_timeline(self) -> None:
        timeline_frame = QFrame()
        timeline_frame.setObjectName("timelinePanelFrame")
        timeline_frame.setFixedHeight(110)

        timeline_layout = QVBoxLayout(timeline_frame)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(0)

        self.timeline_widget = TimelineWidget()
        timeline_layout.addWidget(self.timeline_widget)

        self.main_layout.addWidget(timeline_frame)

    def init_status_bar(self) -> None:
        status_bar = self.statusBar()
        status_bar.setFixedHeight(28)
        status_bar.setContentsMargins(12, 0, 12, 0)

        self.status_icon = AnimatedStatusIcon(self)
        self.status_icon.hide()
        status_bar.addWidget(self.status_icon)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        status_bar.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(160)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        
        status_bar.addPermanentWidget(self.progress_bar)

    def update_button_icons(self) -> None:
        from eztrimr.ui.icons import EZIcon
        self.open_button.setIcon(EZIcon.icon("folder-open", 16))
        self.add_button.setIcon(EZIcon.icon("plus", 16))
        self.export_button.setIcon(EZIcon.icon("download", 16))

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event is not None and event.type() == event.Type.PaletteChange:
            self.update_button_icons()

    def init_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        
        # File Menu
        file_menu = menu_bar.addMenu("File")
        
        open_action = file_menu.addAction("Open File")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file_dialog)
        
        export_action = file_menu.addAction("Export...")
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.trigger_export)
        
        export_audio_action = file_menu.addAction("Export Audio Only")
        export_audio_action.setShortcut("Ctrl+Shift+E")
        export_audio_action.triggered.connect(self.export_audio_only_shortcut)
        
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        # Settings Menu
        settings_menu = menu_bar.addMenu("Settings")
        
        self.live_preview_action = settings_menu.addAction("Live preview while scrubbing")
        self.live_preview_action.setCheckable(True)
        self.live_preview_action.setChecked(app_state.live_scrub_preview)
        self.live_preview_action.triggered.connect(self.toggle_live_preview)

        self.show_waveform_action = settings_menu.addAction("Show waveform in timeline")
        self.show_waveform_action.setCheckable(True)
        self.show_waveform_action.setChecked(app_state.show_waveform)
        self.show_waveform_action.triggered.connect(self.toggle_show_waveform)
        
        settings_menu.addSeparator()
        preferences_action = settings_menu.addAction("Preferences...")
        preferences_action.triggered.connect(self.open_settings_dialog)

        # Help Menu
        help_menu = menu_bar.addMenu("Help")
        about_action = help_menu.addAction("About EZTrimr")
        about_action.triggered.connect(self.open_about_dialog)

    def toggle_live_preview(self, checked: bool) -> None:
        app_state.live_scrub_preview = checked
        settings = QSettings("EZTrimr", "EZTrimr")
        settings.setValue("preview/live_scrub", checked)

    def toggle_show_waveform(self, checked: bool) -> None:
        app_state.show_waveform = checked
        settings = QSettings("EZTrimr", "EZTrimr")
        settings.setValue("preview/show_waveform", checked)
        self.timeline_widget.set_waveform(app_state.waveform_samples, checked)

    def open_settings_dialog(self) -> None:
        from eztrimr.ui.widgets.settings_dialog import SettingsDialog
        from PyQt6.QtWidgets import QDialog
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Sync options to local state
            app_state.live_scrub_preview = dialog.live_scrub_checkbox.isChecked()
            app_state.show_waveform = dialog.waveform_checkbox.isChecked()
            self.live_preview_action.setChecked(app_state.live_scrub_preview)
            self.show_waveform_action.setChecked(app_state.show_waveform)
            # Update timeline waveform visibility
            self.timeline_widget.set_waveform(app_state.waveform_samples, app_state.show_waveform)

    def open_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "About EZTrimr",
            f"<h3>EZTrimr v{config.APP_VERSION}</h3>"
            "<p>A simple, no-nonsense Windows desktop video editor.</p>"
            "<p>Built with Python, PyQt6, pydub, and FFmpeg.</p>"
        )

    # --- DRAG AND DROP EVENTS ---
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            tokens = theme.get_current_tokens()
            handle_color = tokens.get("handle_color", "#0078d4")
            self.center_panel.setStyleSheet(
                f"border: 2px dashed {handle_color}; border-radius: 6px;"
            )
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.center_panel.setStyleSheet("")

    def dropEvent(self, event: QDropEvent) -> None:
        self.center_panel.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            first_file = urls[0].toLocalFile()
            self._start_load(first_file)
            
            # Add all dropped files to the merge queue
            for url in urls:
                app_state.add_merge_file(url.toLocalFile())
            self.left_panel.refresh_queue()

    # --- FILE DIALOG & LOADING WORKFLOW ---
    def open_file_dialog(self) -> None:
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Open Media File — EZTrimr")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilters([
            "All files (*.*)",
            "Common video (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v)",
            "Common audio (*.mp3 *.wav *.aac *.flac *.ogg *.m4a *.opus)",
        ])
        dialog.selectNameFilter("All files (*.*)")
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                self._start_load(files[0])

    def _start_load(self, file_path: str) -> None:
        if not self.open_button.isEnabled():
            return

        self.open_button.setEnabled(False)
        self.status_label.setText("Loading…")
        self.status_icon.start("waveform")

        # Clear undo history
        if hasattr(self, "undo_stack"):
            self.undo_stack.clear()

        # Stop playback timer if running
        if self.playback_timer.isActive():
            self.playback_timer.stop()
        self.center_panel.play_button.setText("▶")

        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()

        # Abort any active preview worker if running
        if self.active_preview_worker and self.active_preview_worker.isRunning():
            try:
                self.active_preview_worker.success.disconnect()
                self.active_preview_worker.finished.disconnect()
            except TypeError:
                pass
        self.active_preview_worker = None
        self.pending_preview_timestamp = None

        # Abort any active audio analyser or preview threads
        if hasattr(self, "audio_analyser") and self.audio_analyser and self.audio_analyser.isRunning():
            try:
                self.audio_analyser.terminate()
                self.audio_analyser.wait()
            except Exception:
                pass
        self.audio_analyser = None

        if hasattr(self, "audio_preview_thread") and self.audio_preview_thread and self.audio_preview_thread.isRunning():
            try:
                self.audio_preview_thread.terminate()
                self.audio_preview_thread.wait()
            except Exception:
                pass
        self.audio_preview_thread = None

        # Reset native media player source
        self.media_player.setSource(QUrl())

        app_state.reset_media_state()
        self.left_panel.reset_info()
        self.center_panel.set_loading()
        self.timeline_widget.set_duration(0.0)
        self.export_button.setEnabled(False)
        self.add_button.setEnabled(False)

        # Kick off MediaLoader
        from eztrimr.core.media import MediaLoader
        self.media_loader = MediaLoader(file_path)
        self.media_loader.probe_done.connect(self.on_probe_done)
        self.media_loader.thumbnail_done.connect(self.on_thumbnail_done)
        self.media_loader.load_failed.connect(self.on_load_failed)
        self.media_loader.progress.connect(self.on_progress)
        self.media_loader.finished.connect(self.on_load_finished)
        self.media_loader.start()

    # --- LOADER SIGNALS SLOTS ---
    def on_probe_done(self, probe_dict: dict) -> None:
        from fractions import Fraction
        import os

        streams = probe_dict.get("streams", [])
        has_video = False
        video_codec = ""
        width = 0
        height = 0
        fps = 0.0
        duration_sec = 0.0

        has_audio = False
        audio_codec = ""
        sample_rate = 0
        channels = 0
        audio_bitrate_kbps = 0

        for s in streams:
            if s.get("codec_type") == "video":
                has_video = True
                video_codec = s.get("codec_name", "")
                width = int(s.get("width", 0))
                height = int(s.get("height", 0))

                r_fps = s.get("r_frame_rate", "0/0")
                try:
                    frac = Fraction(r_fps)
                    fps = round(float(frac), 3)
                except Exception:
                    fps = 0.0

                if "duration" in s:
                    try:
                        duration_sec = float(s["duration"])
                    except ValueError:
                        pass
                break

        for s in streams:
            if s.get("codec_type") == "audio":
                has_audio = True
                audio_codec = s.get("codec_name", "")
                sample_rate = int(s.get("sample_rate", 0))
                channels = int(s.get("channels", 0))

                bitrate = s.get("bit_rate") or s.get("bitrate")
                if bitrate:
                    try:
                        audio_bitrate_kbps = int(bitrate) // 1000
                    except ValueError:
                        pass
                break

        fmt = probe_dict.get("format", {})
        if duration_sec <= 0.0 and "duration" in fmt:
            try:
                duration_sec = float(fmt["duration"])
            except ValueError:
                pass

        # Populate AppState
        app_state.file_path = self.media_loader.file_path
        app_state.file_size_bytes = int(fmt.get("size", 0))
        app_state.has_video = has_video
        app_state.video_codec = video_codec
        app_state.width = width
        app_state.height = height
        app_state.fps = fps
        app_state.duration_sec = duration_sec
        app_state.has_audio = has_audio
        app_state.audio_codec = audio_codec
        app_state.sample_rate = sample_rate
        app_state.channels = channels
        app_state.audio_bitrate_kbps = audio_bitrate_kbps

        # Default extract format based on loaded media if audio-only
        if not has_video and has_audio:
            app_state.audio_extract_only = True
            _, ext = os.path.splitext(self.media_loader.file_path)
            ext_lower = ext.lstrip(".").lower()
            if ext_lower in ("mp3", "wav", "aac", "flac", "ogg"):
                app_state.audio_extract_format = ext_lower
            else:
                app_state.audio_extract_format = "mp3"
        else:
            app_state.audio_extract_only = False
            app_state.audio_extract_format = "mp3"

        app_state.trim_in = 0.0
        app_state.trim_out = duration_sec
        app_state.is_loaded = True
        app_state.is_dirty = False
        self.center_panel.use_native_video = has_video

        # In-place UI Updates
        self.left_panel.update_info()
        self.timeline_widget.set_duration(app_state.duration_sec)
        self.export_button.setEnabled(True)
        self.add_button.setEnabled(True)
        
        # Configure preview inputs ranges and initial values
        self.center_panel.in_input.set_range(0.0, app_state.duration_sec)
        self.center_panel.out_input.set_range(0.0, app_state.duration_sec)
        self.center_panel.in_input.set_seconds(0.0)
        self.center_panel.out_input.set_seconds(app_state.duration_sec)

        self.update_button_icons()
        self.status_label.setText(f"Loaded: {app_state.file_name}")

        self.video_sink_active = False
        if app_state.has_audio or app_state.has_video:
            self.media_player.setSource(QUrl.fromLocalFile(app_state.file_path))
            self.sync_audio_output_volume()

            self.status_label.setText(f"Loaded: {app_state.file_name} (Analyzing audio...)")
            from eztrimr.core.audio import AudioAnalyser
            self.audio_analyser = AudioAnalyser(app_state.file_path)
            self.audio_analyser.analysis_done.connect(self.on_audio_analysis_done)
            self.audio_analyser.analysis_failed.connect(self.on_audio_analysis_failed)
            self.audio_analyser.start()
        else:
            self.right_panel.update_from_state()

    def on_thumbnail_done(self, thumb_path: str) -> None:
        self.center_panel.set_thumbnail(thumb_path, animate=True)

    def on_load_failed(self, error_msg: str) -> None:
        self.status_icon.stop()
        self.center_panel.set_error()
        self.status_label.setText("Failed to load file")
        QMessageBox.critical(self, "Could not open file", error_msg)
        
        app_state.reset_media_state()
        self.left_panel.reset_info()
        self.update_export_button_state()

    def on_progress(self, status_str: str) -> None:
        self.status_label.setText(status_str)

    def on_load_finished(self) -> None:
        self.open_button.setEnabled(True)
        self.progress_bar.hide()
        self.progress_bar.setRange(0, 100)
        self.update_export_button_state()
        if not app_state.has_audio:
            self.status_icon.stop()

    # --- TIMELINE WIDGET EVENT SIGNALS ---
    def on_timeline_in_changed(self, seconds: float) -> None:
        app_state.in_point_seconds = seconds
        self.center_panel.in_input.set_seconds(seconds)

    def on_timeline_out_changed(self, seconds: float) -> None:
        app_state.out_point_seconds = seconds
        self.center_panel.out_input.set_seconds(seconds)

    def on_timeline_playhead_changed(self, seconds: float) -> None:
        if self.playback_timer.isActive():
            self.playback_timer.stop()
            self.center_panel.play_button.setText("▶")
        app_state.playhead_seconds = seconds
        self.center_panel.timecode_label.setText(seconds_to_timecode(seconds))
        if app_state.has_audio:
            self.media_player.setPosition(int(seconds * 1000))
        if app_state.live_scrub_preview and app_state.has_video:
            self.request_preview_frame(seconds)

    def on_timeline_playhead_released(self, seconds: float) -> None:
        app_state.playhead_seconds = seconds
        if app_state.has_audio:
            self.media_player.setPosition(int(seconds * 1000))
        if app_state.has_video:
            self.request_preview_frame(seconds)

    def toggle_playback(self) -> None:
        if not app_state.is_loaded:
            return

        if self.playback_timer.isActive():
            self.playback_timer.stop()
            if app_state.has_audio:
                self.media_player.pause()
            self.center_panel.play_button.setText("▶")
        else:
            # Wrap back to trim_in if at or past the end of the selection
            if app_state.playhead_seconds >= app_state.trim_out - 0.05:
                app_state.playhead_seconds = app_state.trim_in
                self.timeline_widget.set_playhead(app_state.playhead_seconds)
                self.center_panel.timecode_label.setText(seconds_to_timecode(app_state.playhead_seconds))
            
            if app_state.has_audio:
                self.sync_audio_output_volume()
                self.media_player.setPosition(int(app_state.playhead_seconds * 1000))
                self.media_player.play()
                
            self.playback_timer.start(40)  # 25 FPS
            self.center_panel.play_button.setText("⏸")
            self.last_playback_time = QDateTime.currentMSecsSinceEpoch()

    def on_playback_tick(self) -> None:
        if not app_state.is_loaded:
            self.playback_timer.stop()
            if app_state.has_audio:
                self.media_player.stop()
            self.center_panel.play_button.setText("▶")
            return

        if app_state.has_audio:
            # Drive playhead position from master audio clock
            new_playhead = self.media_player.position() / 1000.0
            self.last_playback_time = QDateTime.currentMSecsSinceEpoch()
        else:
            current_time = QDateTime.currentMSecsSinceEpoch()
            elapsed_sec = (current_time - self.last_playback_time) / 1000.0
            self.last_playback_time = current_time
            new_playhead = app_state.playhead_seconds + elapsed_sec

        if new_playhead >= app_state.trim_out:
            new_playhead = app_state.trim_out
            self.playback_timer.stop()
            if app_state.has_audio:
                self.media_player.pause()
            self.center_panel.play_button.setText("▶")

        app_state.playhead_seconds = new_playhead
        self.timeline_widget.set_playhead(new_playhead)
        self.center_panel.timecode_label.setText(seconds_to_timecode(new_playhead))

        if app_state.has_video:
            now = QDateTime.currentMSecsSinceEpoch()
            if now - self.last_preview_frame_time >= 120:
                self.request_preview_frame(new_playhead)
                self.last_preview_frame_time = now

    def on_timeline_trim_released(self, trim_in: float, trim_out: float) -> None:
        app_state.set_trim_points(trim_in, trim_out)

    # --- TIMECODE INPUT EVENT SIGNALS ---
    def on_input_in_changed(self, seconds: float) -> None:
        app_state.set_trim_points(seconds, app_state.out_point_seconds)
        # Update timeline in handle
        self.timeline_widget.set_trim_in(app_state.in_point_seconds)
        # Refresh inputs in case clamping occurred
        self.center_panel.in_input.set_seconds(app_state.in_point_seconds)

    def on_input_out_changed(self, seconds: float) -> None:
        app_state.set_trim_points(app_state.in_point_seconds, seconds)
        # Update timeline out handle
        self.timeline_widget.set_trim_out(app_state.out_point_seconds)
        # Refresh inputs in case clamping occurred
        self.center_panel.out_input.set_seconds(app_state.out_point_seconds)

    # --- PREVIEW FRAME UPDATES ---
    def request_preview_frame(self, seconds: float) -> None:
        if self.center_panel.use_native_video:
            return
        # If a worker is currently running, store as pending and do not launch another
        if self.active_preview_worker and self.active_preview_worker.isRunning():
            self.pending_preview_timestamp = seconds
            return

        self.pending_preview_timestamp = None
        self._spawn_preview_worker(seconds)

    def _spawn_preview_worker(self, seconds: float) -> None:
        self.active_preview_worker = PreviewFrameWorker(
            app_state.file_path,
            seconds,
            config.FFMPEG_PATH,
            self
        )
        self.active_preview_worker.success.connect(self.on_preview_frame_success)
        self.active_preview_worker.finished.connect(self.on_preview_worker_finished)
        self.active_preview_worker.start()

    def on_preview_frame_success(self, jpeg_bytes: bytes) -> None:
        self.center_panel.set_thumbnail(jpeg_bytes)

    def on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.center_panel.use_native_video = False
            self.center_panel.stacked_widget.setCurrentIndex(0)
            self.request_preview_frame(app_state.playhead_seconds)

    def on_preview_worker_finished(self) -> None:
        self.active_preview_worker = None
        # If there is a pending request, launch it now
        if self.pending_preview_timestamp is not None:
            ts = self.pending_preview_timestamp
            self.pending_preview_timestamp = None
            self._spawn_preview_worker(ts)

    # --- MERGE QUEUE ACTIONS ---
    def add_current_to_queue(self) -> None:
        if app_state.file_path:
            app_state.add_merge_file(app_state.file_path)
            self.left_panel.refresh_queue()
            self.status_label.setText(f"Added to merge queue: {app_state.file_name}")

    def trigger_export(self) -> None:
        if self.export_button.isEnabled():
            self.on_export_clicked()

    # --- EXPORT WORKFLOW ---
    def on_export_clicked(self) -> None:
        has_trim = bool(app_state.file_path)
        has_merge = len(app_state.merge_files) > 0

        if has_trim and has_merge:
            msg = QMessageBox(self)
            msg.setWindowTitle("Export — EZTrimr")
            msg.setText("Choose the type of export operation you would like to run:")
            
            btn_trim = msg.addButton("Export Trim", QMessageBox.ButtonRole.AcceptRole)
            btn_merge = msg.addButton("Merge Queue", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = msg.addButton(QMessageBox.StandardButton.Cancel)
            
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == btn_trim:
                self.export_trim()
            elif clicked == btn_merge:
                self.export_merge()
        elif has_trim:
            self.export_trim()
        elif has_merge:
            self.export_merge()

    def set_ui_enabled_during_export(self, enabled: bool) -> None:
        self.open_button.setEnabled(enabled)
        self.add_button.setEnabled(enabled and bool(app_state.file_path))
        self.export_button.setEnabled(enabled)
        self.menuBar().setEnabled(enabled)
        self.timeline_widget.setEnabled(enabled)
        self.center_panel.setEnabled(enabled)
        self.left_panel.setEnabled(enabled)
        self.right_panel.setEnabled(enabled)

    def export_trim(self) -> None:
        if not app_state.file_path:
            return

        base, ext = os.path.splitext(app_state.file_path)
        if app_state.audio_extract_only:
            suggested_ext = f".{app_state.audio_extract_format.lower()}"
            suggested_name = f"{base}_audio{suggested_ext}"
            title = "Export Audio Only"
            default_suffix = app_state.audio_extract_format.lower()
        else:
            suggested_ext = f".{app_state.export_video_format.lower()}"
            suggested_name = f"{base}_trimmed{suggested_ext}"
            title = "Export Trimmed Video"
            default_suffix = app_state.export_video_format.lower()

        dialog = QFileDialog(self)
        dialog.setWindowTitle(title)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setDefaultSuffix(default_suffix)
        dialog.selectFile(suggested_name)
        if app_state.audio_extract_only:
            dialog.setNameFilter(f"Audio File (*.{default_suffix})")
        else:
            dialog.setNameFilter(f"Video File (*.{default_suffix})")
        
        if dialog.exec():
            selected = dialog.selectedFiles()
            if not selected:
                return
            destination = selected[0]

            if os.path.abspath(destination) == os.path.abspath(app_state.file_path):
                QMessageBox.warning(
                    self,
                    "Invalid Export Path",
                    "The destination path cannot match the source file path."
                )
                return

            self.status_label.setText("Exporting trim...")
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.center_panel.progress_pill.show()
            self.center_panel.progress_pill.show_progress(0)
            self.status_icon.start("film")
            self.set_ui_enabled_during_export(False)

            cmd = build_trim_command(
                app_state.file_path,
                destination,
                app_state.in_point_seconds,
                app_state.out_point_seconds,
                config.FFMPEG_PATH,
                has_video=app_state.has_video,
                audio_mute=app_state.audio_mute,
                audio_filter_chain=app_state.audio_filter_chain,
                audio_extract_only=app_state.audio_extract_only,
                audio_extract_format=app_state.audio_extract_format,
                export_video_codec=app_state.export_video_codec,
                export_video_resolution=app_state.export_video_resolution,
                export_video_fps=app_state.export_video_fps,
                export_video_crf=app_state.export_video_crf,
                export_video_bitrate=app_state.export_video_bitrate,
                export_hw_accel=app_state.export_hw_accel
            )
            duration = app_state.out_point_seconds - app_state.in_point_seconds

            self.ffmpeg_worker = FFmpegWorker(cmd, duration, destination, self)
            self.ffmpeg_worker.progressChanged.connect(self.on_ffmpeg_progress)
            self.ffmpeg_worker.finishedSuccessfully.connect(self.on_ffmpeg_success)
            self.ffmpeg_worker.failed.connect(self.on_ffmpeg_failure)
            self.ffmpeg_worker.start()

    def export_merge(self) -> None:
        if not app_state.merge_files:
            return

        first_file = app_state.merge_files[0]
        base, ext = os.path.splitext(first_file)
        if app_state.audio_extract_only:
            suggested_ext = f".{app_state.audio_extract_format.lower()}"
            suggested_name = os.path.join(os.path.dirname(first_file), f"merged_audio{suggested_ext}")
            title = "Export Audio Only"
            default_suffix = app_state.audio_extract_format.lower()
        else:
            suggested_ext = f".{app_state.export_video_format.lower()}"
            suggested_name = os.path.join(os.path.dirname(first_file), f"merged{suggested_ext}")
            title = "Export Merged Video"
            default_suffix = app_state.export_video_format.lower()

        dialog = QFileDialog(self)
        dialog.setWindowTitle(title)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setDefaultSuffix(default_suffix)
        dialog.selectFile(suggested_name)
        if app_state.audio_extract_only:
            dialog.setNameFilter(f"Audio File (*.{default_suffix})")
        else:
            dialog.setNameFilter(f"Video File (*.{default_suffix})")

        if dialog.exec():
            selected = dialog.selectedFiles()
            if not selected:
                return
            destination = selected[0]

            # Verify no overwrite conflict
            dest_abs = os.path.abspath(destination)
            for f in app_state.merge_files:
                if os.path.abspath(f) == dest_abs:
                    QMessageBox.warning(
                        self,
                        "Invalid Export Path",
                        "The destination path cannot match any source files in the merge queue."
                    )
                    return

            self.status_label.setText("Merging clips...")
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.center_panel.progress_pill.show()
            self.center_panel.progress_pill.show_progress(0)
            self.status_icon.start("film")
            self.set_ui_enabled_during_export(False)

            # Probe durations of all merge queue files to compute the exact progress total duration
            total_duration = 0.0
            for file_path in app_state.merge_files:
                total_duration += get_media_duration(file_path)

            self.current_concat_file = tempfile.mktemp(suffix=".txt", prefix="eztrimr_concat_")
            cmd = build_merge_command(
                app_state.merge_files,
                destination,
                self.current_concat_file,
                config.FFMPEG_PATH,
                has_video=app_state.has_video,
                audio_mute=app_state.audio_mute,
                audio_filter_chain=app_state.audio_filter_chain,
                audio_extract_only=app_state.audio_extract_only,
                audio_extract_format=app_state.audio_extract_format,
                export_video_codec=app_state.export_video_codec,
                export_video_resolution=app_state.export_video_resolution,
                export_video_fps=app_state.export_video_fps,
                export_video_crf=app_state.export_video_crf,
                export_video_bitrate=app_state.export_video_bitrate,
                export_hw_accel=app_state.export_hw_accel
            )

            self.ffmpeg_worker = FFmpegWorker(cmd, total_duration or 100.0, destination, self)
            self.ffmpeg_worker.progressChanged.connect(self.on_ffmpeg_progress)
            self.ffmpeg_worker.finishedSuccessfully.connect(self.on_ffmpeg_success)
            self.ffmpeg_worker.failed.connect(self.on_ffmpeg_failure)
            self.ffmpeg_worker.start()

    def on_ffmpeg_progress(self, progress: int) -> None:
        self.progress_bar.setValue(progress)
        self.center_panel.progress_pill.show_progress(progress)

    def on_ffmpeg_success(self, output_path: str) -> None:
        self.center_panel.progress_pill.stop_progress()
        self.center_panel.progress_pill.hide()
        self.status_icon.stop()
        self.set_ui_enabled_during_export(True)
        self.progress_bar.hide()
        self.status_label.setText("Export successful!")
        self.cleanup_concat_file()
        
        # Trigger completion color flash
        from eztrimr.ui.theme import AnimationHelper
        AnimationHelper.color_flash(self, QColor("#4caf50"), 1000)
        
        duration = get_media_duration(output_path)
        from eztrimr.core.utils import format_duration_ms, format_file_size
        formatted_duration = format_duration_ms(duration)
        
        try:
            size_bytes = os.path.getsize(output_path)
            formatted_size = format_file_size(size_bytes)
        except Exception:
            formatted_size = "Unknown"
            
        msg = QMessageBox(self)
        msg.setWindowTitle("Export Successful")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("File exported successfully!")
        msg.setInformativeText(
            f"<b>Path:</b> {output_path}<br/>"
            f"<b>Size:</b> {formatted_size}<br/>"
            f"<b>Duration:</b> {formatted_duration}"
        )
        
        open_folder_btn = msg.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        
        msg.exec()
        
        if msg.clickedButton() == open_folder_btn:
            # Reveal the file in Windows Explorer
            import subprocess
            win_path = os.path.abspath(output_path).replace("/", "\\")
            subprocess.Popen(f'explorer.exe /select,"{win_path}"')

    def on_ffmpeg_failure(self, error_msg: str) -> None:
        self.center_panel.progress_pill.stop_progress()
        self.center_panel.progress_pill.hide()
        self.status_icon.stop()
        self.set_ui_enabled_during_export(True)
        self.progress_bar.hide()
        self.status_label.setText("Export failed")
        self.cleanup_concat_file()
        
        # Extract last 10 lines of stderr
        lines = error_msg.strip().split("\n")
        last_10_lines = "\n".join(lines[-10:])
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Export Failed")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText("FFmpeg operation failed.")
        msg.setInformativeText("Check details below for the error log.")
        msg.setDetailedText(last_10_lines)
        msg.exec()

    def cleanup_concat_file(self) -> None:
        if self.current_concat_file and os.path.exists(self.current_concat_file):
            try:
                os.unlink(self.current_concat_file)
            except Exception:
                pass
            self.current_concat_file = None

    def sync_audio_output_volume(self) -> None:
        """Sets the linear volume of QAudioOutput corresponding to AppState."""
        if not hasattr(self, "audio_output") or not self.audio_output:
            return
        if app_state.audio_mute:
            self.audio_output.setMuted(True)
        else:
            self.audio_output.setMuted(False)
            # Translate dB to linear volume: volume = 10 ** (db / 20.0)
            db = app_state.audio_volume_db
            linear_vol = 10 ** (db / 20.0)
            # QAudioOutput setVolume expects a value from 0.0 to 1.0.
            # Clamp it to prevent out-of-range warnings in PyQt
            linear_vol = max(0.0, min(1.0, linear_vol))
            self.audio_output.setVolume(linear_vol)

    # --- Phase 5 Audio Slots ---
    def on_audio_setting_changed(self, val=None) -> None:
        app_state.is_dirty = True
        self.sync_audio_output_volume()
        
        # Sync toolbar format dropdown without triggering signal recursion
        self.format_combo.blockSignals(True)
        if app_state.audio_extract_only:
            self.format_combo.setCurrentText(app_state.audio_extract_format.upper())
        else:
            self.format_combo.setCurrentText(app_state.export_video_format.upper())
        self.format_combo.blockSignals(False)

    def on_video_format_changed(self, fmt: str) -> None:
        # Sync toolbar format combo box
        self.format_combo.blockSignals(True)
        self.format_combo.setCurrentText(fmt.upper())
        self.format_combo.blockSignals(False)
        app_state.is_dirty = True

    def on_toolbar_format_changed(self, text: str) -> None:
        fmt = text.lower()
        if fmt in ("mp3", "ogg"):
            app_state.audio_extract_only = True
            app_state.audio_extract_format = fmt
        else:
            app_state.audio_extract_only = False
            app_state.export_video_format = fmt
            
        app_state.is_dirty = True
        self.right_panel.update_from_state()

    def on_audio_preview_requested(self) -> None:
        if not app_state.file_path:
            return

        # Abort active preview thread
        if hasattr(self, "audio_preview_thread") and self.audio_preview_thread and self.audio_preview_thread.isRunning():
            try:
                self.audio_preview_thread.preview_ready.disconnect()
                self.audio_preview_thread.preview_failed.disconnect()
                self.audio_preview_thread.terminate()
                self.audio_preview_thread.wait()
            except Exception:
                pass
        self.audio_preview_thread = None
        
        self.right_panel.preview_status.setText("Preparing preview...")
        self.right_panel.preview_btn.setEnabled(False)

        from eztrimr.core.audio import AudioPreviewThread
        self.audio_preview_thread = AudioPreviewThread(
            file_path=app_state.file_path,
            seek_sec=app_state.playhead_seconds,
            duration_sec=app_state.duration_seconds,
            volume_db=app_state.audio_volume_db,
            normalize=app_state.audio_normalize
        )
        self.audio_preview_thread.preview_ready.connect(self.on_audio_preview_ready)
        self.audio_preview_thread.preview_failed.connect(self.on_audio_preview_failed)
        self.audio_preview_thread.start()

    def on_audio_preview_ready(self, temp_file_path: str) -> None:
        self.right_panel.preview_status.setText("Playing preview...")
        self.right_panel.preview_btn.setEnabled(True)
        
        if not hasattr(self, "temp_preview_files"):
            self.temp_preview_files = []
        self.temp_preview_files.append(temp_file_path)

        # Open the generated preview clip in the system default audio player
        try:
            import platform
            if platform.system() == "Windows":
                os.startfile(temp_file_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", temp_file_path])
            else:
                subprocess.Popen(["xdg-open", temp_file_path])
        except Exception as e:
            self.right_panel.preview_status.setText(f"Playback failed: {str(e)}")
            return

        # Schedule a cleanup timer for temp file deletion in 10 seconds
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10000, lambda: self.cleanup_temp_preview_file(temp_file_path))

    def on_audio_preview_failed(self, err: str) -> None:
        self.right_panel.preview_status.setText("Preview failed.")
        self.right_panel.preview_btn.setEnabled(True)
        QMessageBox.warning(self, "Audio Preview Failed", f"Could not create preview:\n{err}")

    def cleanup_temp_preview_file(self, path: str) -> None:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        if hasattr(self, "temp_preview_files") and path in self.temp_preview_files:
            try:
                self.temp_preview_files.remove(path)
            except ValueError:
                pass

    def on_audio_analysis_done(self, peak_dbfs: float, rms_dbfs: float, waveform_samples: list[float]) -> None:
        self.status_icon.stop()
        app_state.peak_dbfs = peak_dbfs
        app_state.rms_dbfs = rms_dbfs
        app_state.waveform_samples = waveform_samples
        
        # update right panel UI
        self.right_panel.update_from_state()
        
        # update timeline waveform
        self.timeline_widget.set_waveform(waveform_samples, app_state.show_waveform)
        
        self.status_label.setText(f"Loaded: {app_state.file_name} (Audio analyzed)")
        
        # Trigger completion color flash
        from eztrimr.ui.theme import AnimationHelper
        AnimationHelper.color_flash(self.timeline_widget, QColor("#2196f3"), 1000)

    def on_audio_analysis_failed(self, error_msg: str) -> None:
        self.status_icon.stop()
        self.status_label.setText(f"Loaded: {app_state.file_name} (Audio analysis failed)")
        self.right_panel.update_from_state()

    def init_shortcuts(self) -> None:
        # Register global application shortcuts
        # 1. Export: Ctrl+E (updates menu bar shortcut)
        self.export_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        self.export_shortcut.activated.connect(self.trigger_export)
        
        # 2. Export audio only: Ctrl+Shift+E
        self.export_audio_shortcut = QShortcut(QKeySequence("Ctrl+Shift+E"), self)
        self.export_audio_shortcut.activated.connect(self.export_audio_only_shortcut)
        
        # 3. Set in-point: I
        self.set_in_shortcut = QShortcut(QKeySequence("I"), self)
        self.set_in_shortcut.activated.connect(self.shortcut_set_in_point)
        
        # 4. Set out-point: O
        self.set_out_shortcut = QShortcut(QKeySequence("O"), self)
        self.set_out_shortcut.activated.connect(self.shortcut_set_out_point)
        
        # 5. Step back 1s: Left
        self.step_back_1_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.step_back_1_shortcut.activated.connect(lambda: self.step_playhead(-1.0))
        
        # 6. Step forward 1s: Right
        self.step_forward_1_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.step_forward_1_shortcut.activated.connect(lambda: self.step_playhead(1.0))
        
        # 7. Step back 5s: Shift+Left
        self.step_back_5_shortcut = QShortcut(QKeySequence("Shift+Left"), self)
        self.step_back_5_shortcut.activated.connect(lambda: self.step_playhead(-5.0))
        
        # 8. Step forward 5s: Shift+Right
        self.step_forward_5_shortcut = QShortcut(QKeySequence("Shift+Right"), self)
        self.step_forward_5_shortcut.activated.connect(lambda: self.step_playhead(5.0))
        
        # 9. Go to start: Home
        self.go_start_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Home), self)
        self.go_start_shortcut.activated.connect(self.go_to_start)
        
        # 10. Go to end: End
        self.go_end_shortcut = QShortcut(QKeySequence(Qt.Key.Key_End), self)
        self.go_end_shortcut.activated.connect(self.go_to_end)
        
        # 11. Undo trim: Ctrl+Z
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo_trim)
        
        # 12. Toggle mute: Ctrl+M
        self.mute_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        self.mute_shortcut.activated.connect(self.toggle_mute_shortcut)
        
        # 13. Toggle waveform: Ctrl+W
        self.waveform_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self.waveform_shortcut.activated.connect(self.toggle_waveform_shortcut)
        
        # 14. Keyboard ref.: F1
        self.kbd_ref_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        self.kbd_ref_shortcut.activated.connect(self.open_shortcuts_ref)
        
        # 15. Add to queue: Ctrl+A
        self.add_queue_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        self.add_queue_shortcut.activated.connect(self.add_to_queue_shortcut)
        
        # 16. Clear queue: Ctrl+Shift+C
        self.clear_queue_shortcut_obj = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self.clear_queue_shortcut_obj.activated.connect(self.clear_queue_shortcut)
        
        # 17. Cancel operation: Escape
        self.cancel_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.cancel_shortcut.activated.connect(self.cancel_operation)
        
        # 18. Quit: Ctrl+Q
        self.quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.quit_shortcut.activated.connect(self.close)

    def export_audio_only_shortcut(self) -> None:
        if not app_state.file_path:
            return
        app_state.audio_extract_only = True
        self.right_panel.update_from_state()
        self.trigger_export()

    def shortcut_set_in_point(self) -> None:
        if not app_state.file_path:
            return
        self.save_undo_state()
        new_in = app_state.playhead_seconds
        app_state.set_trim_points(new_in, app_state.out_point_seconds)
        self.timeline_widget.set_trim_in(app_state.in_point_seconds)
        self.center_panel.in_input.set_seconds(app_state.in_point_seconds)

    def shortcut_set_out_point(self) -> None:
        if not app_state.file_path:
            return
        self.save_undo_state()
        new_out = app_state.playhead_seconds
        app_state.set_trim_points(app_state.in_point_seconds, new_out)
        self.timeline_widget.set_trim_out(app_state.out_point_seconds)
        self.center_panel.out_input.set_seconds(app_state.out_point_seconds)

    def step_playhead(self, seconds: float) -> None:
        if not app_state.file_path:
            return
        new_playhead = app_state.playhead_seconds + seconds
        new_playhead = max(0.0, min(new_playhead, app_state.duration_seconds))
        app_state.set_playhead(new_playhead)
        self.timeline_widget.set_playhead(new_playhead)
        self.center_panel.timecode_label.setText(seconds_to_timecode(new_playhead))
        if app_state.has_audio:
            self.media_player.setPosition(int(new_playhead * 1000))
        if app_state.has_video:
            self.request_preview_frame(new_playhead)

    def go_to_start(self) -> None:
        if not app_state.file_path:
            return
        target = 0.0
        app_state.set_playhead(target)
        self.timeline_widget.set_playhead(target)
        self.center_panel.timecode_label.setText(seconds_to_timecode(target))
        if app_state.has_audio:
            self.media_player.setPosition(0)
        if app_state.has_video:
            self.request_preview_frame(target)

    def go_to_end(self) -> None:
        if not app_state.file_path:
            return
        target = app_state.duration_seconds
        app_state.set_playhead(target)
        self.timeline_widget.set_playhead(target)
        self.center_panel.timecode_label.setText(seconds_to_timecode(target))
        if app_state.has_audio:
            self.media_player.setPosition(int(target * 1000))
        if app_state.has_video:
            self.request_preview_frame(target)

    def save_undo_state(self) -> None:
        curr_state = (app_state.in_point_seconds, app_state.out_point_seconds)
        if not self.undo_stack or self.undo_stack[-1] != curr_state:
            self.undo_stack.append(curr_state)
            if len(self.undo_stack) > 50:
                self.undo_stack.pop(0)

    def undo_trim(self) -> None:
        if not self.undo_stack:
            return
        prev_in, prev_out = self.undo_stack.pop()
        app_state.set_trim_points(prev_in, prev_out)
        self.timeline_widget.set_trim_in(prev_in)
        self.timeline_widget.set_trim_out(prev_out)
        self.center_panel.in_input.blockSignals(True)
        self.center_panel.out_input.blockSignals(True)
        self.center_panel.in_input.set_seconds(prev_in)
        self.center_panel.out_input.set_seconds(prev_out)
        self.center_panel.in_input.blockSignals(False)
        self.center_panel.out_input.blockSignals(False)
        
        # Color flash to show success
        from eztrimr.ui.theme import AnimationHelper
        AnimationHelper.color_flash(self.timeline_widget, QColor("#4caf50"), 800)

    def toggle_mute_shortcut(self) -> None:
        if not app_state.file_path:
            return
        app_state.audio_mute = not app_state.audio_mute
        self.right_panel.update_from_state()
        self.on_audio_setting_changed()

    def toggle_waveform_shortcut(self) -> None:
        checked = not app_state.show_waveform
        self.show_waveform_action.setChecked(checked)
        self.toggle_show_waveform(checked)

    def open_shortcuts_ref(self) -> None:
        from eztrimr.ui.widgets.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.tab_widget.setCurrentIndex(2)
        dialog.exec()

    def add_to_queue_shortcut(self) -> None:
        if app_state.file_path:
            self.add_current_to_queue()

    def clear_queue_shortcut(self) -> None:
        self.left_panel.clear_queue()

    def cancel_operation(self) -> None:
        if self.ffmpeg_worker and self.ffmpeg_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Cancel Export?",
                "Are you sure you want to cancel the export operation?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.ffmpeg_worker.terminate()
                self.ffmpeg_worker.wait()
                self.set_ui_enabled_during_export(True)
                self.progress_bar.hide()
                self.center_panel.progress_pill.stop_progress()
                self.center_panel.progress_pill.hide()
                self.status_label.setText("Export cancelled")
                self.cleanup_concat_file()

    def closeEvent(self, event) -> None:
        # Safeguard: Confirm and Terminate any active export workers when application is closed
        if self.ffmpeg_worker and self.ffmpeg_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Cancel Export?",
                "An export operation is currently running. Do you want to cancel the export and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            else:
                self.ffmpeg_worker.terminate()
                self.ffmpeg_worker.wait()
            
        # Abort audio analyser
        if hasattr(self, "audio_analyser") and self.audio_analyser and self.audio_analyser.isRunning():
            try:
                self.audio_analyser.terminate()
                self.audio_analyser.wait()
            except Exception:
                pass
            
        # Abort audio preview
        if hasattr(self, "audio_preview_thread") and self.audio_preview_thread and self.audio_preview_thread.isRunning():
            try:
                self.audio_preview_thread.terminate()
                self.audio_preview_thread.wait()
            except Exception:
                pass

        # Save window state / geometry and splitters
        settings = QSettings("EZTrimr", "EZTrimr")
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        settings.setValue("window/splitter", self.splitter.saveState())

        # Clean up any temp preview files
        if hasattr(self, "temp_preview_files") and self.temp_preview_files:
            for temp_file in list(self.temp_preview_files):
                self.cleanup_temp_preview_file(temp_file)

        self.cleanup_concat_file()
        super().closeEvent(event)



