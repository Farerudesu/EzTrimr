import os
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSettings, QPoint, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QTransform, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QPushButton, QFrame, QStackedWidget
from PyQt6.QtMultimediaWidgets import QVideoWidget
from eztrimr.core.state import PreviewState
from eztrimr.ui.widgets.timecode_input import TimecodeInput


class VideoCanvas(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = PreviewState.EMPTY
        self.error_msg = ""
        self.original_pixmap = None
        
    def paintEvent(self, event):
        # Draw base background color
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bg_color = QColor("#000000")
        if self.state == PreviewState.ERROR:
            bg_color = QColor("#1a0000")
        elif self.state == PreviewState.AUDIO:
            bg_color = QColor("#1a1a1a")
            
        painter.fillRect(self.rect(), bg_color)
        
        from eztrimr.ui.theme import get_token
        from eztrimr.ui.icons import EZIcon

        if self.state == PreviewState.EMPTY:
            # 1. Dashed boundary border around inner 80%
            w, h = self.width(), self.height()
            margin_x = int(w * 0.1)
            margin_y = int(h * 0.1)
            rect = self.rect().adjusted(margin_x, margin_y, -margin_x, -margin_y)
            
            border_color = get_token("border")
            pen = QPen(border_color, 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, 8, 8)
            
            # 2. Render film icon at 48px centered
            film_px = EZIcon.get("film", 48, get_token("text_muted"))
            icon_x = int((w - 48) / 2)
            icon_y = int((h - 48) / 2 - 25)
            painter.drawPixmap(icon_x, icon_y, film_px)
            
            # 3. Primary text: "No file loaded"
            painter.setPen(get_token("text_muted"))
            font = painter.font()
            font.setFamily("Segoe UI")
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            
            text1 = "No file loaded"
            r1 = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignCenter, text1)
            y_pos = icon_y + 48 + 24
            painter.drawText(int((w - r1.width()) / 2), y_pos, text1)
            
            # 4. Secondary subtext: "Open a file or drop one here" at 60% opacity
            muted = get_token("text_muted")
            painter.setPen(QColor(muted.red(), muted.green(), muted.blue(), int(255 * 0.6)))
            font.setPointSize(9)
            font.setBold(False)
            painter.setFont(font)
            
            text2 = "Open a file or drop one here"
            r2 = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignCenter, text2)
            painter.drawText(int((w - r2.width()) / 2), y_pos + 18, text2)
            
        elif self.state == PreviewState.ERROR:
            # 1. Warning icon at 32px color #cc3333
            w, h = self.width(), self.height()
            icon_px = EZIcon.get("warning", 32, QColor("#cc3333"))
            icon_x = int((w - 32) / 2)
            icon_y = int((h - 32) / 2 - 35)
            painter.drawPixmap(icon_x, icon_y, icon_px)
            
            # 2. Primary text: "Could not load file"
            painter.setPen(QColor("#cc3333"))
            font = painter.font()
            font.setFamily("Segoe UI")
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            
            text1 = "Could not load file"
            r1 = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignCenter, text1)
            y_pos = icon_y + 32 + 20
            painter.drawText(int((w - r1.width()) / 2), y_pos, text1)
            
            # 3. Secondary text: short error reason
            painter.setPen(QColor("#884444"))
            font.setPointSize(9)
            font.setBold(False)
            painter.setFont(font)
            
            text2 = self.error_msg or "Unknown error"
            if len(text2) > 60:
                text2 = text2[:57] + "..."
            r2 = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignCenter, text2)
            painter.drawText(int((w - r2.width()) / 2), y_pos + 18, text2)
            
        elif self.state == PreviewState.AUDIO:
            # Render waveform icon at 32px
            w, h = self.width(), self.height()
            wave_px = EZIcon.get("waveform", 32, get_token("text_muted"))
            icon_x = int((w - 32) / 2)
            icon_y = int((h - 32) / 2 - 15)
            painter.drawPixmap(icon_x, icon_y, wave_px)
            
            painter.setPen(get_token("text_muted"))
            font = painter.font()
            font.setFamily("Segoe UI")
            font.setPointSize(10)
            painter.setFont(font)
            
            text = "Audio only"
            r = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.drawText(int((w - r.width()) / 2), icon_y + 32 + 18, text)
            
        elif self.state == PreviewState.LOADING:
            # Loading text
            w, h = self.width(), self.height()
            painter.setPen(get_token("text_muted"))
            font = painter.font()
            font.setFamily("Segoe UI")
            font.setPointSize(10)
            painter.setFont(font)
            
            text = "Loading..."
            r = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.drawText(int((w - r.width()) / 2), int((h - r.height()) / 2), text)
            
        elif self.state == PreviewState.LOADED and self.original_pixmap:
            # QLabel handles pixmap drawing
            painter.end()
            super().paintEvent(event)
            return
            
        painter.end()


class FirstRunHintBanner(QFrame):
    dismissed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hintBanner")
        self.setStyleSheet("""
            QFrame#hintBanner {
                background-color: #252525;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
            QLabel {
                background: transparent;
                color: #888888;
                font-family: "Segoe UI";
                font-size: 13px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        
        self.text_label = QLabel("Drop a video file here to get started, or click Open above.")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("background: transparent; border: none; padding: 0;")
        
        layout.addWidget(self.text_label, 1)
        layout.addWidget(self.close_btn)
        
        self.close_btn.clicked.connect(self.on_close_clicked)
        
    def init_icons(self):
        from eztrimr.ui.icons import EZIcon
        from eztrimr.ui.theme import get_token
        self.close_btn.setIcon(EZIcon.icon("close", 12, get_token("text_muted")))
        self.close_btn.setToolTip("Dismiss guide permanently")
        
    def on_close_clicked(self):
        settings = QSettings("EZTrimr", "EZTrimr")
        settings.setValue("first_run", False)
        self.dismissed.emit()


class ExportProgressPill(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("progressPill")
        self.setStyleSheet("""
            QFrame#progressPill {
                background-color: rgba(37, 37, 37, 0.85);
                border: 1px solid #3c3c3c;
                border-radius: 20px;
            }
            QLabel {
                background: transparent;
                color: #f0f0f0;
                font-family: "Segoe UI";
                font-size: 12px;
                font-weight: 500;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 16, 0)
        layout.setSpacing(8)
        
        self.icon_label = QLabel()
        self.text_label = QLabel("Exporting... 0%")
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        
        from eztrimr.ui.icons import EZIcon
        from eztrimr.ui.theme import get_token
        self.base_pixmap = EZIcon.get("film", 14, get_token("text_primary"))
        self.icon_label.setPixmap(self.base_pixmap)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate_step)
        self.current_angle = 0
        
    def show_progress(self, progress: int):
        self.text_label.setText(f"Exporting... {progress}%")
        if not self.timer.isActive():
            self.timer.start(200)
            
    def stop_progress(self):
        self.timer.stop()
        
    def rotate_step(self):
        if not self.base_pixmap or self.base_pixmap.isNull():
            return
        transform = QTransform().rotate(self.current_angle)
        rotated = self.base_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        self.icon_label.setPixmap(rotated)
        self.current_angle = (self.current_angle + 90) % 360


class PreviewWidget(QWidget):
    openFileRequested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. First-run hint banner
        settings = QSettings("EZTrimr", "EZTrimr")
        first_run = settings.value("first_run", True)
        if isinstance(first_run, str):
            first_run = (first_run.lower() == "true")
        else:
            first_run = bool(first_run)
            
        self.hint_banner = None
        if first_run:
            self.hint_banner = FirstRunHintBanner(self)
            layout.addWidget(self.hint_banner)
            self.hint_banner.dismissed.connect(self.dismiss_hint)
            # Initialize close icon after brief layout delay
            QTimer.singleShot(50, self.hint_banner.init_icons)

        # 2. QStackedWidget containing custom canvas (QLabel) and native video widget (QVideoWidget)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Custom Video Canvas
        self.canvas = VideoCanvas()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.stacked_widget.addWidget(self.canvas)

        # Native Video Widget
        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.stacked_widget.addWidget(self.video_widget)

        layout.addWidget(self.stacked_widget)

        # 3. Flat retry button (Try another file) placed relative to canvas
        self.error_button = QPushButton("Try another file", self)
        self.error_button.setObjectName("queueControlBtn")
        self.error_button.hide()
        self.error_button.clicked.connect(self.openFileRequested.emit)

        # 4. Floating Progress Pill
        self.progress_pill = ExportProgressPill(self)
        self.progress_pill.hide()

        # Timecode control row
        self.timecode_layout = QHBoxLayout()
        self.timecode_layout.setContentsMargins(12, 0, 12, 0)
        self.timecode_layout.setSpacing(8)

        self.in_input = TimecodeInput("In:")
        self.timecode_layout.addWidget(self.in_input)

        self.timecode_layout.addStretch()

        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("playButton")
        self.play_button.setFixedWidth(32)
        self.play_button.setFixedHeight(26)
        self.play_button.setEnabled(False)
        self.timecode_layout.addWidget(self.play_button)

        self.timecode_label = QLabel("00:00:00.000")
        self.timecode_label.setObjectName("timecodeLabel")
        self.timecode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timecode_label.setStyleSheet("font-family: Consolas, Monaco, monospace; font-size: 13px;")
        self.timecode_layout.addWidget(self.timecode_label)

        self.timecode_layout.addStretch()

        self.out_input = TimecodeInput("Out:")
        self.timecode_layout.addWidget(self.out_input)

        layout.addLayout(self.timecode_layout)

        self.state = PreviewState.EMPTY
        self.original_pixmap = None
        self.use_native_video = True
        self.set_empty()

    def dismiss_hint(self) -> None:
        if self.hint_banner:
            from eztrimr.ui.theme import AnimationHelper
            AnimationHelper.fade_out(self.hint_banner, 180, then_hide=True)

    def set_inputs_enabled(self, enabled: bool) -> None:
        self.in_input.setEnabled(enabled)
        self.out_input.setEnabled(enabled)
        self.play_button.setEnabled(enabled)

    def set_empty(self) -> None:
        self.state = PreviewState.EMPTY
        self.canvas.state = PreviewState.EMPTY
        self.original_pixmap = None
        self.canvas.setPixmap(QPixmap())
        self.error_button.hide()
        self.stacked_widget.setCurrentIndex(0)
        
        self.timecode_label.setText("00:00:00.000")
        self.set_inputs_enabled(False)
        self.play_button.setText("▶")
        self.in_input.set_seconds(0.0)
        self.out_input.set_seconds(0.0)
        self.canvas.update()

    def set_loading(self) -> None:
        self.state = PreviewState.LOADING
        self.canvas.state = PreviewState.LOADING
        self.original_pixmap = None
        self.canvas.setPixmap(QPixmap())
        self.error_button.hide()
        self.stacked_widget.setCurrentIndex(0)
        self.set_inputs_enabled(False)
        self.canvas.update()

    def set_thumbnail(self, source, animate: bool = False) -> None:
        if not source:
            self.set_audio_only()
            return

        self.state = PreviewState.LOADED
        self.canvas.state = PreviewState.LOADED
        self.error_button.hide()
        
        if self.use_native_video:
            self.stacked_widget.setCurrentIndex(1)
        else:
            self.stacked_widget.setCurrentIndex(0)
            if isinstance(source, bytes):
                pixmap = QPixmap()
                pixmap.loadFromData(source, "JPEG")
                self.original_pixmap = pixmap
            elif isinstance(source, QPixmap):
                self.original_pixmap = source
            else:
                self.original_pixmap = QPixmap(source)
                try:
                    if os.path.exists(source):
                        os.unlink(source)
                except Exception:
                    pass
            
            self.canvas.original_pixmap = self.original_pixmap
            self.update_thumbnail_scale()
            
            # Smooth transition fade-in when thumbnail sets (e.g. when first loaded)
            if animate:
                from eztrimr.ui.theme import AnimationHelper
                AnimationHelper.fade_in(self.canvas, 180)
                
        self.set_inputs_enabled(True)

    def set_audio_only(self) -> None:
        self.state = PreviewState.AUDIO
        self.canvas.state = PreviewState.AUDIO
        self.original_pixmap = None
        self.canvas.setPixmap(QPixmap())
        self.error_button.hide()
        self.stacked_widget.setCurrentIndex(0)
        self.set_inputs_enabled(True)
        self.canvas.update()

    def set_error(self, msg: str = "") -> None:
        self.state = PreviewState.ERROR
        self.canvas.state = PreviewState.ERROR
        self.canvas.error_msg = msg
        self.original_pixmap = None
        self.canvas.setPixmap(QPixmap())
        self.stacked_widget.setCurrentIndex(0)
        
        self.timecode_label.setText("00:00:00.000")
        self.set_inputs_enabled(False)
        
        # Center retry button
        self.error_button.show()
        w = self.width()
        h = self.height()
        btn_w = 140
        btn_h = 30
        self.error_button.setGeometry(int((w - btn_w) / 2), int(h / 2) + 30, btn_w, btn_h)
        self.canvas.update()

    def show_export_progress(self, progress: int) -> None:
        self.progress_pill.show_progress(progress)
        if not self.progress_pill.isVisible():
            pill_w = 200
            pill_h = 44
            self.progress_pill.setGeometry(
                int((self.width() - pill_w) / 2),
                int((self.height() - pill_h) / 2),
                pill_w,
                pill_h
            )
            from eztrimr.ui.theme import AnimationHelper
            AnimationHelper.fade_in(self.progress_pill, 180)

    def hide_export_progress(self) -> None:
        if self.progress_pill.isVisible():
            from eztrimr.ui.theme import AnimationHelper
            AnimationHelper.fade_out(self.progress_pill, 180, then_hide=True)
            self.progress_pill.stop_progress()

    def update_thumbnail_scale(self) -> None:
        if self.state == PreviewState.LOADED and self.original_pixmap:
            canvas_size = self.canvas.size()
            if canvas_size.width() > 0 and canvas_size.height() > 0:
                scaled_pixmap = self.original_pixmap.scaled(
                    canvas_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.canvas.setPixmap(scaled_pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.state == PreviewState.LOADED:
            self.update_thumbnail_scale()
            
        # Reposition overlays
        if self.error_button.isVisible():
            w = self.width()
            h = self.height()
            btn_w = 140
            btn_h = 30
            self.error_button.setGeometry(int((w - btn_w) / 2), int(h / 2) + 30, btn_w, btn_h)
            
        if self.progress_pill.isVisible():
            pill_w = 200
            pill_h = 44
            self.progress_pill.setGeometry(
                int((self.width() - pill_w) / 2),
                int((self.height() - pill_h) / 2),
                pill_w,
                pill_h
            )
