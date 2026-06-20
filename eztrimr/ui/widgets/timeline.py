from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, pyqtProperty, QPropertyAnimation, QSettings
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygon
from PyQt6.QtWidgets import QWidget
from eztrimr.ui import theme
from eztrimr.core.utils import format_timecode


class TimelineWidget(QWidget):
    inPointChanged = pyqtSignal(float)
    outPointChanged = pyqtSignal(float)
    playheadChanged = pyqtSignal(float)
    playheadReleased = pyqtSignal(float)
    trimReleased = pyqtSignal(float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(110)
        self.setMouseTracking(True)  # Enable hover events without mouse press
        
        self.duration_sec = 0.0
        self._trim_in = 0.0
        self._trim_out = 0.0
        self.playhead_sec = 0.0
        self.drag_state = None  # can be "playhead", "in_point", "out_point", or None
        self.hovered_handle = None  # can be "playhead", "in_point", "out_point", or None
        
        # Audio Waveform attributes
        self.waveform_samples = []
        self.show_waveform = False
        self._waveform_opacity = 0.0
        self._waveform_anim = None

    @property
    def trim_in(self) -> float:
        return self._trim_in

    @property
    def trim_out(self) -> float:
        return self._trim_out

    def set_duration(self, duration_sec: float) -> None:
        self.duration_sec = duration_sec if duration_sec is not None else 0.0
        self.playhead_sec = 0.0
        self._trim_in = 0.0
        self._trim_out = self.duration_sec
        self.waveform_samples = []
        self.update()

    def set_playhead(self, seconds: float) -> None:
        if self.duration_sec > 0:
            self.playhead_sec = max(0.0, min(seconds, self.duration_sec))
            self.update()

    def set_trim_in(self, seconds: float) -> None:
        if self.duration_sec > 0:
            self._trim_in = max(0.0, min(seconds, self.duration_sec))
            self.update()

    def set_trim_out(self, seconds: float) -> None:
        if self.duration_sec > 0:
            self._trim_out = max(0.0, min(seconds, self.duration_sec))
            self.update()

    @pyqtProperty(float)
    def waveformOpacity(self) -> float:
        return self._waveform_opacity

    @waveformOpacity.setter
    def waveformOpacity(self, val: float) -> None:
        self._waveform_opacity = val
        self.update()

    def set_waveform(self, samples: list[float], visible: bool) -> None:
        settings = QSettings("EZTrimr", "EZTrimr")
        reduce_motion = settings.value("reduce_motion", False, type=bool)

        if reduce_motion:
            self.waveform_samples = samples
            self.show_waveform = visible
            self._waveform_opacity = 1.0 if visible else 0.0
            self.update()
            return

        if visible:
            self.waveform_samples = samples
            self.show_waveform = True
            
            if self._waveform_anim is not None:
                self._waveform_anim.stop()

            self._waveform_anim = QPropertyAnimation(self, b"waveformOpacity")
            self._waveform_anim.setDuration(300)
            self._waveform_anim.setStartValue(self._waveform_opacity)
            self._waveform_anim.setEndValue(1.0)
            self._waveform_anim.start()
        else:
            if self._waveform_anim is not None:
                self._waveform_anim.stop()

            self._waveform_anim = QPropertyAnimation(self, b"waveformOpacity")
            self._waveform_anim.setDuration(200)
            self._waveform_anim.setStartValue(self._waveform_opacity)
            self._waveform_anim.setEndValue(0.0)
            
            def on_fade_out_finished():
                self.show_waveform = False
                self._waveform_anim = None
                
            self._waveform_anim.finished.connect(on_fade_out_finished)
            self._waveform_anim.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get current theme colors
        tokens = theme.get_current_tokens()
        bg_control = QColor(tokens.get("bg_control", "#2d2d2d"))
        bg_selected = QColor(tokens.get("bg_selected", "#0078d4"))
        text_muted = QColor(tokens.get("text_muted", "#888888"))

        # Interactive handle color states
        if self.drag_state == "playhead":
            playhead_brush = QColor("#d6271a")  # Darker red when dragging
        elif self.hovered_handle == "playhead":
            playhead_brush = QColor("#ff5b52")  # Lighter red when hovered
        else:
            playhead_brush = QColor("#ff3b30")  # Normal red

        if self.drag_state == "in_point":
            in_brush = QColor("#005a9e")  # Darker blue
        elif self.hovered_handle == "in_point":
            in_brush = QColor("#1a8ae5")  # Lighter blue
        else:
            in_brush = QColor(tokens.get("handle_color", "#0078d4"))

        if self.drag_state == "out_point":
            out_brush = QColor("#005a9e")
        elif self.hovered_handle == "out_point":
            out_brush = QColor("#1a8ae5")
        else:
            out_brush = QColor(tokens.get("handle_color", "#0078d4"))

        width = self.width()
        start_x = 16
        end_x = width - 16
        track_w = end_x - start_x

        # --- ROW 1: SCRUBBER ROW (y: 0 to 28, center at y: 14) ---
        scrubber_pen = QPen(bg_control, 4)
        scrubber_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(scrubber_pen)
        painter.drawLine(start_x, 14, end_x, 14)

        if self.duration_sec > 0:
            playhead_ratio = self.playhead_sec / self.duration_sec
            playhead_x = start_x + int(playhead_ratio * track_w)
        else:
            playhead_x = start_x
        
        # Playhead triangle (pointing down, y: 4 to 10)
        triangle_polygon = QPolygon([
            QPoint(playhead_x - 5, 4),
            QPoint(playhead_x + 5, 4),
            QPoint(playhead_x, 10)
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(playhead_brush))
        painter.drawPolygon(triangle_polygon)

        # Playhead vertical line (y: 10 to 28)
        line_pen = QPen(playhead_brush, 2)
        painter.setPen(line_pen)
        painter.drawLine(playhead_x, 10, playhead_x, 28)

        # --- ROW 2: TRIM REGION ROW (y: 28 to 72, center at y: 50) ---
        trim_track_pen = QPen(bg_control, 8)
        trim_track_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(trim_track_pen)
        painter.drawLine(start_x, 50, end_x, 50)

        # Paint waveform display if toggled and available
        if self.show_waveform and self.waveform_samples:
            mid_y = 50.0
            height = 44.0
            num_samples = len(self.waveform_samples)
            spacing = 1.0
            bar_width = max(1.0, (track_w / num_samples) - spacing)
            
            # Select colors using theme
            primary_color = theme.get_token("handle_color")
            muted_color = theme.get_token("text_muted")
            peak_color = QColor(220, 53, 69, 217)  
            normal_color = QColor(primary_color.red(), primary_color.green(), primary_color.blue(), 178)
            quiet_color = QColor(muted_color.red(), muted_color.green(), muted_color.blue(), 115)

            for i, val in enumerate(self.waveform_samples):
                x = start_x + (i / num_samples) * track_w
                if val >= 0.85:
                    color = QColor(peak_color.red(), peak_color.green(), peak_color.blue(), int(peak_color.alpha() * self._waveform_opacity))
                elif val >= 0.5:
                    color = QColor(normal_color.red(), normal_color.green(), normal_color.blue(), int(normal_color.alpha() * self._waveform_opacity))
                else:
                    color = QColor(quiet_color.red(), quiet_color.green(), quiet_color.blue(), int(quiet_color.alpha() * self._waveform_opacity))

                bar_height = max(2.0, val * (height - 4))
                y_start = mid_y - (bar_height / 2.0)
                y_end = mid_y + (bar_height / 2.0)

                pen = QPen(color)
                pen.setWidthF(bar_width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                
                center_x = x + (bar_width / 2.0)
                painter.drawLine(int(center_x), int(y_start), int(center_x), int(y_end))

        if self.duration_sec > 0:
            in_ratio = self._trim_in / self.duration_sec
            out_ratio = self._trim_out / self.duration_sec
            in_x = start_x + int(in_ratio * track_w)
            out_x = start_x + int(out_ratio * track_w)
        else:
            in_x = start_x
            out_x = end_x

        # Highlight region (bg_selected, 30% opacity)
        highlight_color = QColor(bg_selected)
        highlight_color.setAlpha(76)
        painter.fillRect(QRect(in_x, 46, out_x - in_x, 8), QBrush(highlight_color))

        # Left handle (y: 38 to 62, centered at in_x, width 4px)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(in_brush))
        painter.drawRect(QRect(in_x - 2, 38, 4, 24))

        # Right handle (y: 38 to 62, centered at out_x, width 4px)
        painter.setBrush(QBrush(out_brush))
        painter.drawRect(QRect(out_x - 2, 38, 4, 24))

        # --- ROW 3: TIME LABELS ROW (y: 72 to 100) ---
        painter.setPen(text_muted)
        font = QFont("Segoe UI", 11)
        painter.setFont(font)

        if self.duration_sec > 0:
            labels = [format_timecode(i * self.duration_sec / 4) for i in range(5)]
            # Draw minor ticks (20 minor ticks total)
            minor_pen = QPen(text_muted, 1)
            painter.setPen(minor_pen)
            for i in range(21):
                if i % 5 != 0:
                    tick_x = start_x + int(i * track_w / 20)
                    painter.drawLine(tick_x, 72, tick_x, 74)
            painter.setPen(text_muted)  # Restore text pen
        else:
            labels = ["—", "—", "—", "—", "—"]

        for i, label in enumerate(labels):
            tick_x = start_x + int(i * track_w / 4)
            painter.drawLine(tick_x, 72, tick_x, 76)
            rect = QRect(tick_x - 25, 80, 50, 16)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        # --- FLOATING TIMECODE OVERLAY BADGES ---
        if self.duration_sec > 0:
            if self.drag_state == "playhead" or (self.drag_state is None and self.hovered_handle == "playhead"):
                self.draw_time_badge(painter, playhead_x, self.playhead_sec, 18)
            elif self.drag_state == "in_point" or (self.drag_state is None and self.hovered_handle == "in_point"):
                self.draw_time_badge(painter, in_x, self._trim_in, 24)
            elif self.drag_state == "out_point" or (self.drag_state is None and self.hovered_handle == "out_point"):
                self.draw_time_badge(painter, out_x, self._trim_out, 24)

    def draw_time_badge(self, painter: QPainter, x: int, seconds: float, y_offset: int) -> None:
        time_str = format_timecode(seconds)
        badge_w = 88
        badge_h = 18
        badge_x = max(badge_w // 2 + 4, min(x, self.width() - badge_w // 2 - 4))
        rect = QRect(badge_x - badge_w // 2, y_offset, badge_w, badge_h)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
        painter.drawRoundedRect(rect, 4, 4)
        
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Consolas", 9)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, time_str)

    def leaveEvent(self, event) -> None:
        self.hovered_handle = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        x = pos.x()
        y = pos.y()
        start_x = 16
        end_x = self.width() - 16
        track_w = end_x - start_x

        if self.duration_sec <= 0:
            return

        playhead_x = start_x + int((self.playhead_sec / self.duration_sec) * track_w)
        in_x = start_x + int((self._trim_in / self.duration_sec) * track_w)
        out_x = start_x + int((self._trim_out / self.duration_sec) * track_w)

        if 0 <= y <= 28:
            self.drag_state = "playhead"
            ratio = (x - start_x) / track_w
            ratio = max(0.0, min(ratio, 1.0))
            self.playhead_sec = ratio * self.duration_sec
            self.playheadChanged.emit(self.playhead_sec)
            self.update()
        elif 28 <= y <= 72:
            dist_in = abs(x - in_x)
            dist_out = abs(x - out_x)
            tolerance = 10
            
            if dist_in <= tolerance and dist_in <= dist_out:
                self.drag_state = "in_point"
            elif dist_out <= tolerance:
                self.drag_state = "out_point"
            else:
                self.drag_state = "playhead"
                ratio = (x - start_x) / track_w
                ratio = max(0.0, min(ratio, 1.0))
                self.playhead_sec = ratio * self.duration_sec
                self.playheadChanged.emit(self.playhead_sec)
                self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        x = pos.x()
        y = pos.y()
        start_x = 16
        end_x = self.width() - 16
        track_w = end_x - start_x

        if self.duration_sec <= 0:
            return

        if self.drag_state == "playhead":
            ratio = (x - start_x) / track_w
            ratio = max(0.0, min(ratio, 1.0))
            self.playhead_sec = ratio * self.duration_sec
            self.playheadChanged.emit(self.playhead_sec)
            self.update()
        elif self.drag_state == "in_point":
            ratio = (x - start_x) / track_w
            ratio = max(0.0, min(ratio, 1.0))
            sec = ratio * self.duration_sec
            if sec >= self._trim_out:
                sec = max(0.0, self._trim_out - 0.001)
            self._trim_in = sec
            self.inPointChanged.emit(self._trim_in)
            self.update()
        elif self.drag_state == "out_point":
            ratio = (x - start_x) / track_w
            ratio = max(0.0, min(ratio, 1.0))
            sec = ratio * self.duration_sec
            if sec <= self._trim_in:
                sec = min(self.duration_sec, self._trim_in + 0.001)
            self._trim_out = sec
            self.outPointChanged.emit(self._trim_out)
            self.update()
        else:
            # Hover detection
            in_ratio = self._trim_in / self.duration_sec
            out_ratio = self._trim_out / self.duration_sec
            in_x = start_x + int(in_ratio * track_w)
            out_x = start_x + int(out_ratio * track_w)

            in_row = (38 <= y <= 62)
            over_left = in_row and (abs(x - in_x) <= 8)
            over_right = in_row and (abs(x - out_x) <= 8)

            playhead_x = start_x + int((self.playhead_sec / self.duration_sec) * track_w)
            over_playhead = (0 <= y <= 28) and (abs(x - playhead_x) <= 8)

            old_hover = self.hovered_handle
            if over_left:
                self.hovered_handle = "in_point"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif over_right:
                self.hovered_handle = "out_point"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif over_playhead:
                self.hovered_handle = "playhead"
                self.setCursor(Qt.CursorShape.SplitHCursor)
            else:
                self.hovered_handle = None
                self.unsetCursor()

            if self.hovered_handle != old_hover:
                self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self.drag_state == "playhead":
            self.playheadReleased.emit(self.playhead_sec)
        elif self.drag_state in ("in_point", "out_point"):
            self.trimReleased.emit(self._trim_in, self._trim_out)
        self.drag_state = None
        self.update()



