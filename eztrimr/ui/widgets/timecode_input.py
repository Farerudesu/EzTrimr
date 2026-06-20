from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit
from eztrimr.core.timecode import seconds_to_timecode, timecode_to_seconds, clamp_seconds


class TimecodeInput(QWidget):
    timeChanged = pyqtSignal(float)

    def __init__(self, label_text: str, parent=None) -> None:
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Label
        self.label = QLabel(label_text)
        self.label.setObjectName("timecodeWidgetLabel")
        layout.addWidget(self.label)

        # Line Edit
        self.line_edit = QLineEdit()
        self.line_edit.setObjectName("timecodeWidgetEdit")
        self.line_edit.setPlaceholderText("00:00:00.000")
        # Ensure it fits "00:00:00.000" comfortably
        self.line_edit.setMinimumWidth(95)
        self.line_edit.setMaximumWidth(120)
        layout.addWidget(self.line_edit)

        self.current_seconds = 0.0
        self.min_seconds = 0.0
        self.max_seconds = 0.0

        # Signals
        self.line_edit.editingFinished.connect(self._on_editing_finished)

    def set_range(self, min_val: float, max_val: float) -> None:
        self.min_seconds = min_val
        self.max_seconds = max_val

    def set_seconds(self, seconds: float) -> None:
        self.current_seconds = seconds
        time_str = seconds_to_timecode(seconds)
        # Block signals temporarily to prevent editingFinished feedback loop
        self.line_edit.blockSignals(True)
        self.line_edit.setText(time_str)
        self.line_edit.blockSignals(True)
        self.line_edit.blockSignals(False)

    def seconds(self) -> float:
        return self.current_seconds

    def _on_editing_finished(self) -> None:
        text = self.line_edit.text()
        try:
            sec = timecode_to_seconds(text)
            # Clamp value
            clamped = clamp_seconds(sec, self.min_seconds, self.max_seconds)
            self.current_seconds = clamped
            
            # Update the text format (in case the user entered MM:SS or similar)
            self.set_seconds(clamped)
            self.timeChanged.emit(clamped)
        except ValueError:
            from eztrimr.ui.theme import AnimationHelper
            from PyQt6.QtGui import QColor
            AnimationHelper.color_flash(self.line_edit, QColor("#ff4d4d"), 1500)
            self.set_seconds(self.current_seconds)
