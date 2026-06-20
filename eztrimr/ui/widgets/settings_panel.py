import os
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSettings, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve
from PyQt6.QtGui import QColor, QTransform
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSlider,
    QFrame,
    QCheckBox,
    QPushButton,
    QTabWidget,
    QGraphicsOpacityEffect,
    QScrollArea
)
from eztrimr.core.state import app_state
from eztrimr.ui.icons import EZIcon


class SkeletonLoader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 16)
        
        # Loader styling using bg_control
        from eztrimr.ui.theme import get_token
        self.setStyleSheet(f"background-color: {get_token('bg_control').name()}; border-radius: 3px;")
        
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(600)
        self.anim.setKeyValueAt(0.0, 0.4)
        self.anim.setKeyValueAt(0.5, 1.0)
        self.anim.setKeyValueAt(1.0, 0.4)
        self.anim.setLoopCount(-1) # Infinite
        
    def start_loading(self):
        self.show()
        self.anim.start()
        
    def stop_loading(self):
        self.anim.stop()
        self.hide()


class LoudnessMeter(QWidget):
    """Simple horizontal loudness bar meter."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(12)
        self.db = -60.0

    def set_value(self, db: float) -> None:
        self.db = max(-60.0, min(db, 0.0))
        self.update()

    def paintEvent(self, event) -> None:
        from PyQt6.QtGui import QPainter, QLinearGradient
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background track
        from eztrimr.ui.theme import get_token
        bg_color = get_token("bg_control")
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 4, 4)

        # Calculate fill ratio
        val = (self.db + 60.0) / 60.0  # 0.0 to 1.0
        if val > 0:
            fill_w = int(self.width() * val)
            
            # Gradient fill (green -> yellow -> red)
            grad = QLinearGradient(0, 0, self.width(), 0)
            grad.setColorAt(0.0, QColor("#28a745"))
            grad.setColorAt(0.7, QColor("#ffc107"))
            grad.setColorAt(1.0, QColor("#dc3545"))

            painter.setBrush(grad)
            painter.drawRoundedRect(0, 0, fill_w, self.height(), 4, 4)
        painter.end()


class SettingsPanel(QWidget):
    # Core Video setting signals
    videoFormatChanged = pyqtSignal(str)
    videoCodecChanged = pyqtSignal(str)
    videoCrfChanged = pyqtSignal(int)
    videoResolutionChanged = pyqtSignal(str)
    videoFpsChanged = pyqtSignal(str)
    previewRequested = pyqtSignal()

    volumeChanged = pyqtSignal(float)
    normalizeToggled = pyqtSignal(bool)
    muteToggled = pyqtSignal(bool)
    extractToggled = pyqtSignal(bool)
    extractFormatChanged = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.analysis_in_progress = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Video Tab Setup
        self.video_tab = QFrame()
        self.video_tab.setObjectName("tabContentFrame")
        video_outer_layout = QVBoxLayout(self.video_tab)
        video_outer_layout.setContentsMargins(0, 0, 0, 0)
        video_outer_layout.setSpacing(0)

        # Scroll Area for Video tab contents
        self.video_scroll = QScrollArea()
        self.video_scroll.setWidgetResizable(True)
        self.video_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.video_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.video_scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        self.video_scroll_content = QWidget()
        self.video_scroll_content.setObjectName("scrollContentVideo")
        self.video_scroll_content.setStyleSheet("QWidget#scrollContentVideo { background-color: transparent; }")

        video_tab_layout = QVBoxLayout(self.video_scroll_content)
        video_tab_layout.setContentsMargins(8, 8, 8, 8)
        video_tab_layout.setSpacing(10)

        self.video_scroll.setWidget(self.video_scroll_content)
        video_outer_layout.addWidget(self.video_scroll)

        # 1. Output Format Section
        self.v_format_frame = QFrame()
        v_format_layout = QVBoxLayout(self.v_format_frame)
        v_format_layout.setContentsMargins(0, 0, 0, 0)
        v_format_layout.setSpacing(6)

        v_format_hdr = QLabel("OUTPUT CONTAINER FORMAT")
        v_format_hdr.setObjectName("sectionHeader")
        v_format_layout.addWidget(v_format_hdr)

        self.v_format_combo = QComboBox()
        self.v_format_combo.addItems(["MP4", "MKV", "MOV", "AVI", "WEBM"])
        v_format_layout.addWidget(self.v_format_combo)
        video_tab_layout.addWidget(self.v_format_frame)

        # Divider 1
        v_div1 = QFrame()
        v_div1.setFrameShape(QFrame.Shape.HLine)
        v_div1.setFrameShadow(QFrame.Shadow.Sunken)
        v_div1.setStyleSheet("background-color: #3c3c3c; max-height: 1px; border: none;")
        video_tab_layout.addWidget(v_div1)

        # 2. Video Encoder Section
        self.v_encoder_frame = QFrame()
        v_encoder_layout = QVBoxLayout(self.v_encoder_frame)
        v_encoder_layout.setContentsMargins(0, 0, 0, 0)
        v_encoder_layout.setSpacing(6)

        v_encoder_hdr = QLabel("VIDEO ENCODER SETTINGS")
        v_encoder_hdr.setObjectName("sectionHeader")
        v_encoder_layout.addWidget(v_encoder_hdr)

        codec_row = QHBoxLayout()
        self.codec_label_text = QLabel("Video Codec:")
        self.v_codec_combo = QComboBox()
        self.v_codec_combo.addItems(["Copy (Fast)", "H.264", "H.265", "VP9"])
        codec_row.addWidget(self.codec_label_text)
        codec_row.addWidget(self.v_codec_combo)
        v_encoder_layout.addLayout(codec_row)

        # Video Bitrate Row
        bitrate_row = QHBoxLayout()
        self.bitrate_label_text = QLabel("Video Bitrate:")
        self.v_bitrate_combo = QComboBox()
        self.v_bitrate_combo.addItems([
            "Auto",
            "2 Mbps",
            "5 Mbps",
            "10 Mbps",
            "20 Mbps"
        ])
        bitrate_row.addWidget(self.bitrate_label_text)
        bitrate_row.addWidget(self.v_bitrate_combo)
        v_encoder_layout.addLayout(bitrate_row)

        # Hardware Acceleration Row
        hw_row = QHBoxLayout()
        self.hw_label_text = QLabel("Hardware Accel:")
        self.v_hw_combo = QComboBox()
        self.v_hw_combo.addItems([
            "None (CPU)",
            "NVIDIA CUDA (NVENC)",
            "Intel QuickSync (QSV)",
            "AMD AMF"
        ])
        hw_row.addWidget(self.hw_label_text)
        hw_row.addWidget(self.v_hw_combo)
        v_encoder_layout.addLayout(hw_row)
        
        # Grey out unsupported hardware acceleration options
        self.check_hw_accel_support()

        crf_row = QHBoxLayout()
        self.crf_label_text = QLabel("CRF Quality (Lower is better):")
        self.v_crf_value_label = QLabel("23")
        self.v_crf_value_label.setStyleSheet("font-weight: bold;")
        crf_row.addWidget(self.crf_label_text)
        crf_row.addStretch()
        crf_row.addWidget(self.v_crf_value_label)
        v_encoder_layout.addLayout(crf_row)

        self.v_crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.v_crf_slider.setRange(0, 51)
        self.v_crf_slider.setValue(23)
        v_encoder_layout.addWidget(self.v_crf_slider)

        self.v_crf_desc = QLabel("CRF 0 is lossless. Standard defaults: H.264 = 23, H.265 = 28, VP9 = 31.")
        self.v_crf_desc.setStyleSheet("color: #888888; font-size: 11px;")
        self.v_crf_desc.setWordWrap(True)
        v_encoder_layout.addWidget(self.v_crf_desc)

        video_tab_layout.addWidget(self.v_encoder_frame)

        # Divider 2
        v_div2 = QFrame()
        v_div2.setFrameShape(QFrame.Shape.HLine)
        v_div2.setFrameShadow(QFrame.Shadow.Sunken)
        v_div2.setStyleSheet("background-color: #3c3c3c; max-height: 1px; border: none;")
        video_tab_layout.addWidget(v_div2)

        # 3. Resolution & FPS Section
        self.v_res_fps_frame = QFrame()
        v_res_fps_layout = QVBoxLayout(self.v_res_fps_frame)
        v_res_fps_layout.setContentsMargins(0, 0, 0, 0)
        v_res_fps_layout.setSpacing(8)

        v_res_fps_hdr = QLabel("RESOLUTION & FRAMERATE")
        v_res_fps_hdr.setObjectName("sectionHeader")
        v_res_fps_layout.addWidget(v_res_fps_hdr)

        res_row = QHBoxLayout()
        self.res_label_text = QLabel("Resolution:")
        self.v_res_combo = QComboBox()
        self.v_res_combo.addItems(["Original", "1080p", "720p", "480p"])
        res_row.addWidget(self.res_label_text)
        res_row.addWidget(self.v_res_combo)
        v_res_fps_layout.addLayout(res_row)

        fps_row = QHBoxLayout()
        self.fps_label_text = QLabel("Framerate:")
        self.v_fps_combo = QComboBox()
        self.v_fps_combo.addItems(["Original", "60 fps", "30 fps", "24 fps"])
        fps_row.addWidget(self.fps_label_text)
        fps_row.addWidget(self.v_fps_combo)
        v_res_fps_layout.addLayout(fps_row)

        video_tab_layout.addWidget(self.v_res_fps_frame)
        video_tab_layout.addStretch()
        
        # Audio Tab Setup
        self.audio_tab = QFrame()
        self.audio_tab.setObjectName("tabContentFrame")
        audio_outer_layout = QVBoxLayout(self.audio_tab)
        audio_outer_layout.setContentsMargins(0, 0, 0, 0)
        audio_outer_layout.setSpacing(0)

        # Scroll Area for Audio tab contents
        self.audio_scroll = QScrollArea()
        self.audio_scroll.setWidgetResizable(True)
        self.audio_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.audio_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.audio_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.audio_scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        self.audio_scroll_content = QWidget()
        self.audio_scroll_content.setObjectName("scrollContentAudio")
        self.audio_scroll_content.setStyleSheet("QWidget#scrollContentAudio { background-color: transparent; }")

        self.audio_tab_layout = QVBoxLayout(self.audio_scroll_content)
        self.audio_tab_layout.setContentsMargins(8, 8, 8, 8)
        self.audio_tab_layout.setSpacing(10)

        self.audio_scroll.setWidget(self.audio_scroll_content)
        audio_outer_layout.addWidget(self.audio_scroll)

        # Empty Audio tab banner (no file loaded)
        self.audio_empty_frame = QFrame()
        audio_empty_layout = QVBoxLayout(self.audio_empty_frame)
        audio_empty_layout.setContentsMargins(0, 0, 0, 0)
        audio_empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.audio_empty_label = QLabel()
        self.audio_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.audio_empty_label.setWordWrap(True)
        audio_empty_layout.addWidget(self.audio_empty_label)
        self.audio_tab_layout.addWidget(self.audio_empty_frame)

        # 1. No Audio Warning Label
        self.no_audio_label = QLabel("No active audio stream detected in media file.")
        self.no_audio_label.setStyleSheet("color: #ff5b52; font-style: italic;")
        self.no_audio_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_audio_label.setWordWrap(True)
        self.audio_tab_layout.addWidget(self.no_audio_label)
        self.no_audio_label.hide()

        # 2. Loudness Status Section
        self.loudness_frame = QFrame()
        loudness_layout = QVBoxLayout(self.loudness_frame)
        loudness_layout.setContentsMargins(0, 0, 0, 0)
        loudness_layout.setSpacing(6)
        
        loudness_hdr = QLabel("LOUDNESS ANALYSIS")
        loudness_hdr.setObjectName("sectionHeader")
        loudness_layout.addWidget(loudness_hdr)

        stats_layout = QHBoxLayout()
        self.peak_label_text = QLabel("Peak:")
        self.peak_value_label = QLabel("—")
        self.peak_skeleton = SkeletonLoader()
        self.rms_label_text = QLabel("RMS:")
        self.rms_value_label = QLabel("—")
        self.rms_skeleton = SkeletonLoader()
        
        stats_layout.addWidget(self.peak_label_text)
        stats_layout.addWidget(self.peak_value_label)
        stats_layout.addWidget(self.peak_skeleton)
        stats_layout.addSpacing(16)
        stats_layout.addWidget(self.rms_label_text)
        stats_layout.addWidget(self.rms_value_label)
        stats_layout.addWidget(self.rms_skeleton)
        stats_layout.addStretch()
        loudness_layout.addLayout(stats_layout)

        # Hide skeletons initially
        self.peak_skeleton.hide()
        self.rms_skeleton.hide()

        self.meter = LoudnessMeter()
        loudness_layout.addWidget(self.meter)
        self.audio_tab_layout.addWidget(self.loudness_frame)

        # Divider 1
        self.a_div1 = QFrame()
        self.a_div1.setFrameShape(QFrame.Shape.HLine)
        self.a_div1.setFrameShadow(QFrame.Shadow.Sunken)
        self.a_div1.setStyleSheet("background-color: #3c3c3c; max-height: 1px; border: none;")
        self.audio_tab_layout.addWidget(self.a_div1)

        # 3. Volume Section
        self.volume_frame = QFrame()
        volume_layout = QVBoxLayout(self.volume_frame)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(6)

        volume_hdr = QLabel("VOLUME & GAIN")
        volume_hdr.setObjectName("sectionHeader")
        volume_layout.addWidget(volume_hdr)

        vol_row = QHBoxLayout()
        self.vol_label_text = QLabel("Adjust Volume:")
        self.vol_value_label = QLabel("0.0 dB")
        self.vol_value_label.setStyleSheet("font-weight: bold;")
        vol_row.addWidget(self.vol_label_text)
        vol_row.addStretch()
        vol_row.addWidget(self.vol_value_label)
        volume_layout.addLayout(vol_row)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(-200, 200)
        self.volume_slider.setValue(0)
        self.volume_slider.setSingleStep(5)
        self.volume_slider.setPageStep(20)
        self.volume_slider.setToolTip("Adjust output volume (–20 to +20 dB)")
        volume_layout.addWidget(self.volume_slider)

        self.clipping_warning = QLabel("⚠️ Clipping warning! Combined gain exceeds 0 dBFS.")
        self.clipping_warning.setStyleSheet("color: #dc3545; font-size: 11px; font-weight: bold;")
        self.clipping_warning.setWordWrap(True)
        volume_layout.addWidget(self.clipping_warning)
        self.clipping_warning.hide()

        self.norm_checkbox = QCheckBox("Normalize audio")
        self.norm_checkbox.setToolTip("Target –23 LUFS (EBU R128 standard)")
        volume_layout.addWidget(self.norm_checkbox)
        
        self.norm_desc = QLabel("Locks dynamic range to broadcast standards.")
        self.norm_desc.setStyleSheet("color: #888888; font-size: 11px; margin-left: 20px;")
        self.norm_desc.setWordWrap(True)
        volume_layout.addWidget(self.norm_desc)

        self.audio_tab_layout.addWidget(self.volume_frame)

        # Divider 2
        self.a_div2 = QFrame()
        self.a_div2.setFrameShape(QFrame.Shape.HLine)
        self.a_div2.setFrameShadow(QFrame.Shadow.Sunken)
        self.a_div2.setStyleSheet("background-color: #3c3c3c; max-height: 1px; border: none;")
        self.audio_tab_layout.addWidget(self.a_div2)

        # 4. Audio Output Section
        self.output_frame = QFrame()
        output_layout = QVBoxLayout(self.output_frame)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(8)

        output_hdr = QLabel("AUDIO OUTPUT CONFIG")
        output_hdr.setObjectName("sectionHeader")
        output_layout.addWidget(output_hdr)

        self.mute_checkbox = QCheckBox("Mute audio track")
        self.mute_checkbox.setToolTip("Remove audio track from output  [Ctrl+M]")
        output_layout.addWidget(self.mute_checkbox)

        self.extract_checkbox = QCheckBox("Extract audio only")
        self.extract_checkbox.setToolTip("Export audio track without video  [Ctrl+Shift+E]")
        output_layout.addWidget(self.extract_checkbox)

        self.format_container = QWidget()
        format_layout = QHBoxLayout(self.format_container)
        format_layout.setContentsMargins(20, 0, 0, 0)
        format_layout.setSpacing(6)
        
        self.format_lbl = QLabel("Target Format:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP3", "WAV", "AAC", "FLAC", "OGG"])
        format_layout.addWidget(self.format_lbl)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        output_layout.addWidget(self.format_container)
        self.format_container.hide()

        self.audio_tab_layout.addWidget(self.output_frame)
        self.audio_tab_layout.addStretch()

        # 5. Preview Audio Settings Section
        self.preview_frame = QFrame()
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(6)

        self.preview_btn = QPushButton("Preview 3s")
        self.preview_btn.setObjectName("previewAudioButton")
        self.preview_btn.setFixedHeight(32)
        self.preview_btn.setToolTip("Play 3 seconds from playhead position")
        preview_layout.addWidget(self.preview_btn)

        self.preview_status = QLabel("")
        self.preview_status.setStyleSheet("color: #888888; font-size: 11px;")
        self.preview_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_status)

        self.audio_tab_layout.addWidget(self.preview_frame)

        self.tabs.addTab(self.video_tab, "Video")
        self.tabs.addTab(self.audio_tab, "Audio")
        main_layout.addWidget(self.tabs)

        # Wire handlers
        self.volume_slider.valueChanged.connect(self.on_volume_slider_changed)
        self.norm_checkbox.toggled.connect(self.on_normalize_toggled)
        self.mute_checkbox.toggled.connect(self.on_mute_toggled)
        self.extract_checkbox.toggled.connect(self.on_extract_toggled)
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        self.preview_btn.clicked.connect(self.previewRequested.emit)

        self.v_format_combo.currentTextChanged.connect(self.on_v_format_changed)
        self.v_codec_combo.currentTextChanged.connect(self.on_v_codec_changed)
        self.v_bitrate_combo.currentTextChanged.connect(self.on_v_bitrate_changed)
        self.v_hw_combo.currentTextChanged.connect(self.on_v_hw_changed)
        self.v_crf_slider.valueChanged.connect(self.on_v_crf_changed)
        self.v_res_combo.currentTextChanged.connect(self.on_v_res_changed)
        self.v_fps_combo.currentTextChanged.connect(self.on_v_fps_changed)

        # Initialize
        self.refresh_empty_state_label()
        self.init_icons()
        self.update_from_state()

    def init_icons(self) -> None:
        from eztrimr.ui.icons import EZIcon
        self.preview_btn.setIcon(EZIcon.icon("play", 14))
        self.mute_checkbox.setIcon(EZIcon.icon("audio-mute", 14))
        self.norm_checkbox.setIcon(EZIcon.icon("normalize", 14))

    def refresh_empty_state_label(self) -> None:
        from eztrimr.ui.icons import EZIcon
        from eztrimr.ui.theme import get_token
        color = get_token("text_muted")
        muted_hex = color.name()
        self.audio_empty_label.setText(
            f"<div align='center'>"
            f"{EZIcon.to_base64_img('waveform', 32, color)}<br/><br/>"
            f"<span style='font-size: 13px; font-weight: bold; color: {muted_hex};'>Load a file to see audio settings</span>"
            f"</div>"
        )

    def on_tab_changed(self, index: int) -> None:
        new_widget = self.tabs.widget(index)
        if new_widget:
            # Smooth fade-in on tab switch
            from eztrimr.ui.theme import AnimationHelper
            AnimationHelper.fade_in(new_widget, 120)

    def set_analysis_in_progress(self, in_progress: bool) -> None:
        self.analysis_in_progress = in_progress
        if in_progress:
            self.peak_value_label.hide()
            self.rms_value_label.hide()
            self.peak_skeleton.start_loading()
            self.rms_skeleton.start_loading()
        else:
            self.peak_skeleton.stop_loading()
            self.rms_skeleton.stop_loading()
            self.peak_value_label.show()
            self.rms_value_label.show()
            
            # Fade in real values smoothly
            from eztrimr.ui.theme import AnimationHelper
            AnimationHelper.fade_in(self.peak_value_label, 300)
            AnimationHelper.fade_in(self.rms_value_label, 300)

    def update_from_state(self) -> None:
        has_media = app_state.is_loaded
        has_audio = app_state.has_audio

        # --- Sync Video Tab ---
        self.video_tab.setEnabled(has_media)
        if has_media:
            self.v_format_combo.blockSignals(True)
            self.v_format_combo.setCurrentText(app_state.export_video_format.upper())
            self.v_format_combo.blockSignals(False)

            self.v_codec_combo.blockSignals(True)
            if app_state.export_video_codec == "copy":
                self.v_codec_combo.setCurrentText("Copy (Fast)")
            elif app_state.export_video_codec == "h264":
                self.v_codec_combo.setCurrentText("H.264")
            elif app_state.export_video_codec == "h265":
                self.v_codec_combo.setCurrentText("H.265")
            elif app_state.export_video_codec == "vp9":
                self.v_codec_combo.setCurrentText("VP9")
            self.v_codec_combo.blockSignals(False)

            self.v_crf_slider.blockSignals(True)
            self.v_crf_slider.setValue(app_state.export_video_crf)
            self.v_crf_slider.blockSignals(False)
            self.v_crf_value_label.setText(str(app_state.export_video_crf))

            self.v_res_combo.blockSignals(True)
            res_display = app_state.export_video_resolution.capitalize() if app_state.export_video_resolution == "original" else app_state.export_video_resolution
            self.v_res_combo.setCurrentText(res_display)
            self.v_res_combo.blockSignals(False)

            self.v_fps_combo.blockSignals(True)
            fps_display = app_state.export_video_fps.capitalize() if app_state.export_video_fps == "original" else f"{app_state.export_video_fps} fps"
            self.v_fps_combo.setCurrentText(fps_display)
            self.v_fps_combo.blockSignals(False)

            self.v_bitrate_combo.blockSignals(True)
            self.v_bitrate_combo.setCurrentText(app_state.export_video_bitrate)
            self.v_bitrate_combo.blockSignals(False)

            self.v_hw_combo.blockSignals(True)
            import config
            if app_state.export_hw_accel == "NVIDIA CUDA (NVENC)" and not config.NVENC_SUPPORTED:
                app_state.export_hw_accel = "None (CPU)"
            elif app_state.export_hw_accel == "Intel QuickSync (QSV)" and not config.QSV_SUPPORTED:
                app_state.export_hw_accel = "None (CPU)"
            elif app_state.export_hw_accel == "AMD AMF" and not config.AMF_SUPPORTED:
                app_state.export_hw_accel = "None (CPU)"

            matching_text = app_state.export_hw_accel
            for i in range(self.v_hw_combo.count()):
                item_text = self.v_hw_combo.itemText(i)
                if item_text == matching_text or item_text == f"{matching_text} [Unsupported]":
                    self.v_hw_combo.setCurrentIndex(i)
                    break
            self.v_hw_combo.blockSignals(False)

            self.apply_video_codec_constraints()

        # --- Sync Audio Tab Layout (Empty/Loaded state visibility rules) ---
        if not has_media:
            self.audio_empty_frame.show()
            self.loudness_frame.hide()
            self.volume_frame.hide()
            self.output_frame.hide()
            self.preview_frame.hide()
            self.no_audio_label.hide()
            self.a_div1.hide()
            self.a_div2.hide()
            return
            
        self.audio_empty_frame.hide()
        
        if not has_audio:
            self.loudness_frame.hide()
            self.volume_frame.hide()
            self.output_frame.hide()
            self.preview_frame.hide()
            self.no_audio_label.show()
            self.a_div1.hide()
            self.a_div2.hide()
            return

        self.no_audio_label.hide()
        self.loudness_frame.show()
        self.volume_frame.show()
        self.output_frame.show()
        self.preview_frame.show()
        self.a_div1.show()
        self.a_div2.show()

        # Sync Peak/RMS Stats (if not actively analyzing)
        if not self.analysis_in_progress:
            peak = app_state.peak_dbfs
            rms = app_state.rms_dbfs
            self.peak_value_label.setText(f"{peak:.1f} dBFS")
            self.rms_value_label.setText(f"{rms:.1f} dBFS")
            self.meter.set_value(peak)

        # Sync controls
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(int(app_state.audio_volume_db * 10))
        self.volume_slider.blockSignals(False)
        self.vol_value_label.setText(f"{app_state.audio_volume_db:+.1f} dB")

        self.norm_checkbox.blockSignals(True)
        self.norm_checkbox.setChecked(app_state.audio_normalize)
        self.norm_checkbox.blockSignals(False)

        self.mute_checkbox.blockSignals(True)
        self.mute_checkbox.setChecked(app_state.audio_mute)
        self.mute_checkbox.blockSignals(False)

        self.extract_checkbox.blockSignals(True)
        self.extract_checkbox.setChecked(app_state.audio_extract_only)
        self.extract_checkbox.blockSignals(False)

        self.format_combo.blockSignals(True)
        self.format_combo.setCurrentText(app_state.audio_extract_format.upper())
        self.format_combo.blockSignals(False)

        self.apply_mute_or_extract_constraints()
        self.check_clipping_risk()

    def on_v_format_changed(self, text: str) -> None:
        fmt = text.lower()
        app_state.export_video_format = fmt
        app_state.is_dirty = True
        self.videoFormatChanged.emit(fmt)

    def on_v_codec_changed(self, text: str) -> None:
        codec = text.lower()
        if "copy" in codec:
            app_state.export_video_codec = "copy"
        elif "264" in codec:
            app_state.export_video_codec = "h264"
        elif "265" in codec:
            app_state.export_video_codec = "h265"
        elif "vp9" in codec:
            app_state.export_video_codec = "vp9"
            
        app_state.is_dirty = True
        self.apply_video_codec_constraints()
        
        # Auto-update CRF default based on chosen codec
        if app_state.export_video_codec == "h264":
            app_state.export_video_crf = 23
        elif app_state.export_video_codec == "h265":
            app_state.export_video_crf = 28
        elif app_state.export_video_codec == "vp9":
            app_state.export_video_crf = 31
        self.v_crf_slider.blockSignals(True)
        self.v_crf_slider.setValue(app_state.export_video_crf)
        self.v_crf_slider.blockSignals(False)
        self.v_crf_value_label.setText(str(app_state.export_video_crf))

        self.videoCodecChanged.emit(app_state.export_video_codec)

    def on_v_crf_changed(self, val: int) -> None:
        app_state.export_video_crf = val
        app_state.is_dirty = True
        self.v_crf_value_label.setText(str(val))
        self.videoCrfChanged.emit(val)

    def on_v_res_changed(self, text: str) -> None:
        res = text.lower()
        app_state.export_video_resolution = res
        app_state.is_dirty = True
        self.videoResolutionChanged.emit(res)

    def on_v_fps_changed(self, text: str) -> None:
        fps_raw = text.split(" ")[0].lower()
        app_state.export_video_fps = fps_raw
        app_state.is_dirty = True
        self.videoFpsChanged.emit(fps_raw)

    def check_hw_accel_support(self) -> None:
        import config
        model = self.v_hw_combo.model()
        
        # NVENC (Index 1)
        item_nvenc = model.item(1)
        if item_nvenc:
            item_nvenc.setEnabled(config.NVENC_SUPPORTED)
            if not config.NVENC_SUPPORTED:
                item_nvenc.setText("NVIDIA CUDA (NVENC) [Unsupported]")
                
        # QSV (Index 2)
        item_qsv = model.item(2)
        if item_qsv:
            item_qsv.setEnabled(config.QSV_SUPPORTED)
            if not config.QSV_SUPPORTED:
                item_qsv.setText("Intel QuickSync (QSV) [Unsupported]")
                
        # AMF (Index 3)
        item_amf = model.item(3)
        if item_amf:
            item_amf.setEnabled(config.AMF_SUPPORTED)
            if not config.AMF_SUPPORTED:
                item_amf.setText("AMD AMF [Unsupported]")

    def on_v_bitrate_changed(self, text: str) -> None:
        app_state.export_video_bitrate = text
        app_state.is_dirty = True
        settings = QSettings("EZTrimr", "EZTrimr")
        settings.setValue("advanced/video_bitrate", text)
        self.apply_video_codec_constraints()
        self.videoCodecChanged.emit(app_state.export_video_codec)

    def on_v_hw_changed(self, text: str) -> None:
        if " [Unsupported]" in text:
            text = text.replace(" [Unsupported]", "")
        app_state.export_hw_accel = text
        app_state.is_dirty = True
        settings = QSettings("EZTrimr", "EZTrimr")
        settings.setValue("advanced/hw_accel", text)
        self.apply_video_codec_constraints()
        self.videoCodecChanged.emit(app_state.export_video_codec)

    def apply_video_codec_constraints(self) -> None:
        is_copy = (app_state.export_video_codec == "copy")
        is_auto_bitrate = (app_state.export_video_bitrate == "Auto")
        
        self.v_bitrate_combo.setEnabled(not is_copy)
        self.v_hw_combo.setEnabled(not is_copy)
        
        self.v_crf_slider.setEnabled(not is_copy and is_auto_bitrate)
        self.v_crf_desc.setEnabled(not is_copy and is_auto_bitrate)
        self.crf_label_text.setEnabled(not is_copy and is_auto_bitrate)
        self.v_crf_value_label.setEnabled(not is_copy and is_auto_bitrate)
        
        self.v_res_combo.setEnabled(not is_copy)
        self.v_fps_combo.setEnabled(not is_copy)
        self.res_label_text.setEnabled(not is_copy)
        self.fps_label_text.setEnabled(not is_copy)

    def on_volume_slider_changed(self, val: int) -> None:
        gain_db = val / 10.0
        app_state.audio_volume_db = gain_db
        app_state.is_dirty = True
        self.vol_value_label.setText(f"{gain_db:+.1f} dB")
        self.check_clipping_risk()
        self.volumeChanged.emit(gain_db)

    def on_normalize_toggled(self, checked: bool) -> None:
        app_state.audio_normalize = checked
        app_state.is_dirty = True
        self.normalizeToggled.emit(checked)

    def on_mute_toggled(self, checked: bool) -> None:
        app_state.audio_mute = checked
        app_state.is_dirty = True
        self.apply_mute_or_extract_constraints()
        self.muteToggled.emit(checked)

    def on_extract_toggled(self, checked: bool) -> None:
        app_state.audio_extract_only = checked
        app_state.is_dirty = True
        self.apply_mute_or_extract_constraints()
        self.extractToggled.emit(checked)

    def on_format_changed(self, text: str) -> None:
        fmt = text.lower()
        app_state.audio_extract_format = fmt
        app_state.is_dirty = True
        self.extractFormatChanged.emit(fmt)

    def apply_mute_or_extract_constraints(self) -> None:
        """Enforces mutually exclusive check states between mute and audio extraction."""
        if app_state.audio_mute:
            self.extract_checkbox.setEnabled(False)
            self.format_container.hide()
            self.preview_btn.setEnabled(False)
            self.volume_slider.setEnabled(False)
            self.norm_checkbox.setEnabled(False)
        elif app_state.audio_extract_only:
            self.mute_checkbox.setEnabled(False)
            self.format_container.show()
            self.preview_btn.setEnabled(True)
            self.volume_slider.setEnabled(True)
            self.norm_checkbox.setEnabled(True)
        else:
            self.extract_checkbox.setEnabled(True)
            self.mute_checkbox.setEnabled(True)
            self.format_container.hide()
            self.preview_btn.setEnabled(True)
            self.volume_slider.setEnabled(True)
            self.norm_checkbox.setEnabled(True)

    def check_clipping_risk(self) -> None:
        """Displays visual warning if normalized loudness + gain volume raises clipping danger."""
        if app_state.peak_dbfs + app_state.audio_volume_db > 0.0 and not app_state.audio_mute:
            self.clipping_warning.show()
        else:
            self.clipping_warning.hide()
