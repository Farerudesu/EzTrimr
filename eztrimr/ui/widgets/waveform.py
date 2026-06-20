from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt
from eztrimr.ui import theme


class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = []
        self.setFixedHeight(44)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_samples(self, samples: list[float]):
        self.samples = samples
        self.update()

    def paintEvent(self, event):
        if not self.samples:
            return

        painter = QPainter(self)
        # Antialiasing makes the bars render smoothly
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        mid_y = height / 2.0

        # Retrieve dynamic colors from theme
        primary_color = theme.get_token("handle_color")
        muted_color = theme.get_token("text_muted")
        
        # Color definitions:
        # 1. Peaks (>= 0.85): Red at 85% opacity
        peak_color = QColor(220, 53, 69, 217)  
        # 2. Normal (>= 0.5 and < 0.85): Theme primary/handle color at 70% opacity
        normal_color = QColor(primary_color.red(), primary_color.green(), primary_color.blue(), 178)
        # 3. Quiet (< 0.5): Theme muted text color at 45% opacity
        quiet_color = QColor(muted_color.red(), muted_color.green(), muted_color.blue(), 115)

        num_samples = len(self.samples)
        # Calculate optimal width for each bar
        spacing = 1.0
        bar_width = max(1.0, (width / num_samples) - spacing)
        
        for i, val in enumerate(self.samples):
            # Calculate horizontal position
            x = (i / num_samples) * width
            
            # Select color based on amplitude value
            if val >= 0.85:
                color = peak_color
            elif val >= 0.5:
                color = normal_color
            else:
                color = quiet_color

            # Draw vertical line centered around mid_y
            bar_height = max(2.0, val * (height - 4))
            y_start = mid_y - (bar_height / 2.0)
            y_end = mid_y + (bar_height / 2.0)

            pen = QPen(color)
            pen.setWidthF(bar_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            
            # Draw line at center of bar width
            center_x = x + (bar_width / 2.0)
            painter.drawLine(int(center_x), int(y_start), int(center_x), int(y_end))
