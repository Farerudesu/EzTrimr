import sys
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QSettings, pyqtProperty, QPoint
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect

DARK_TOKENS = {
    "bg_base": "#1e1e1e",
    "bg_panel": "#252525",
    "bg_control": "#2d2d2d",
    "bg_hover": "#3a3a3a",
    "bg_selected": "#0078d4",
    "text_primary": "#f0f0f0",
    "text_muted": "#888888",
    "border": "#3c3c3c",
    "timeline_bg": "#181818",
    "handle_color": "#0078d4",
}

LIGHT_TOKENS = {
    "bg_base": "#f3f3f3",
    "bg_panel": "#ffffff",
    "bg_control": "#e5e5e5",
    "bg_hover": "#d4d4d4",
    "bg_selected": "#0078d4",
    "text_primary": "#1a1a1a",
    "text_muted": "#666666",
    "border": "#d0d0d0",
    "timeline_bg": "#e0e0e0",
    "handle_color": "#0078d4",
}

_current_tokens = DARK_TOKENS


def get_current_tokens() -> dict:
    return _current_tokens


def get_token(name: str) -> QColor:
    return QColor(_current_tokens.get(name, "#000000"))



def generate_qss(tokens: dict) -> str:
    return f"""
        QMainWindow {{
            background-color: {tokens['bg_base']};
        }}
        
        /* Layout Panels */
        QWidget#leftPanel, QWidget#rightPanel {{
            background-color: {tokens['bg_panel']};
            border: none;
        }}
        
        /* Borders for panel separation */
        QFrame#leftPanelFrame {{
            background-color: {tokens['bg_panel']};
            border-right: 1px solid {tokens['border']};
            border-left: none;
            border-top: none;
            border-bottom: none;
        }}
        QFrame#rightPanelFrame {{
            background-color: {tokens['bg_panel']};
            border-left: 1px solid {tokens['border']};
            border-right: none;
            border-top: none;
            border-bottom: none;
        }}
        QFrame#timelinePanelFrame {{
            background-color: {tokens['timeline_bg']};
            border-top: 1px solid {tokens['border']};
            border-left: none;
            border-right: none;
            border-bottom: none;
        }}
        QFrame#toolbarFrame {{
            background-color: {tokens['bg_base']};
            border-bottom: 1px solid {tokens['border']};
            border-top: none;
            border-left: none;
            border-right: none;
        }}
        
        /* Text styling */
        QLabel {{
            color: {tokens['text_primary']};
            font-family: "Segoe UI";
            font-size: 13px;
        }}
        
        QLabel#appTitleLabel {{
            font-size: 14px;
            font-weight: 600;
            color: {tokens['text_primary']};
        }}
        
        QLabel#sectionHeader {{
            font-size: 11px;
            font-weight: bold;
            color: {tokens['text_muted']};
        }}
        
        QLabel#fileInfoLabel {{
            font-size: 12px;
            color: {tokens['text_muted']};
        }}
        
        QLabel#fileInfoValue {{
            font-size: 13px;
            color: {tokens['text_primary']};
            font-weight: 500;
        }}
        
        QLabel#emptyQueueLabel, QLabel#tabPlaceholderLabel {{
            font-size: 13px;
            color: {tokens['text_muted']};
        }}
        
        QLabel#timecodeLabel {{
            color: {tokens['text_muted']};
        }}
        
        QLabel#outputFormatLabel {{
            font-size: 12px;
            color: {tokens['text_muted']};
        }}
        
        QFrame#panelDivider {{
            background-color: {tokens['border']};
            max-height: 1px;
            min-height: 1px;
            border: none;
            margin-top: 12px;
            margin-bottom: 12px;
        }}
        
        QFrame#toolbarSeparator {{
            background-color: {tokens['border']};
            max-width: 1px;
            min-width: 1px;
            min-height: 20px;
            max-height: 20px;
            border: none;
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: transparent;
            color: {tokens['text_primary']};
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-family: "Segoe UI";
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {tokens['bg_hover']};
        }}
        QPushButton:pressed {{
            background-color: {tokens['bg_control']};
        }}
        QPushButton:disabled {{
            color: {tokens['text_muted']};
            background-color: transparent;
        }}
        
        QPushButton#clearQueueButton {{
            font-size: 12px;
            padding: 4px 8px;
        }}
        
        QPushButton#exportButton:enabled {{
            background-color: {tokens['bg_selected']};
            color: #ffffff;
        }}
        QPushButton#exportButton:enabled:hover {{
            background-color: #005a9e;
        }}
        
        QPushButton#previewAudioButton {{
            background-color: {tokens['bg_control']};
            color: {tokens['text_primary']};
            border: 1px solid {tokens['border']};
            border-radius: 4px;
            font-weight: 500;
        }}
        QPushButton#previewAudioButton:hover {{
            background-color: {tokens['bg_hover']};
        }}
        QPushButton#previewAudioButton:pressed {{
            background-color: {tokens['bg_base']};
        }}
        QPushButton#previewAudioButton:disabled {{
            background-color: {tokens['bg_control']};
            color: {tokens['text_muted']};
        }}
        
        QPushButton#playButton {{
            background-color: {tokens['bg_control']};
            color: {tokens['text_primary']};
            border: 1px solid {tokens['border']};
            border-radius: 4px;
            font-size: 11px;
            padding: 0px;
        }}
        QPushButton#playButton:hover {{
            background-color: {tokens['bg_hover']};
        }}
        QPushButton#playButton:pressed {{
            background-color: {tokens['bg_base']};
        }}
        QPushButton#playButton:disabled {{
            background-color: {tokens['bg_control']};
            color: {tokens['text_muted']};
        }}
        
        /* QListWidget */
        QListWidget {{
            background-color: {tokens['bg_control']};
            border: none;
            outline: 0;
            border-radius: 4px;
        }}
        QListWidget::item {{
            color: {tokens['text_primary']};
            padding: 4px 8px;
            border-radius: 2px;
        }}
        QListWidget::item:hover {{
            background-color: {tokens['bg_hover']};
        }}
        QListWidget::item:selected {{
            background-color: {tokens['bg_selected']};
            color: #ffffff;
        }}
        
        /* Tab Widget Flat Style */
        QTabWidget::pane {{
            border: 1px solid {tokens['border']};
            background-color: {tokens['bg_panel']};
            top: -1px;
        }}
        QTabBar::tab {{
            background-color: {tokens['bg_panel']};
            color: {tokens['text_muted']};
            padding: 8px 16px;
            font-size: 13px;
            font-family: "Segoe UI";
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:hover {{
            background-color: {tokens['bg_hover']};
        }}
        QTabBar::tab:selected {{
            color: {tokens['text_primary']};
            font-weight: bold;
            border-bottom: 2px solid {tokens['bg_selected']};
        }}
        
        /* Status Bar */
        QStatusBar {{
            background-color: {tokens['bg_base']};
            border-top: 1px solid {tokens['border']};
        }}
        QStatusBar::item {{
            border: none;
        }}
        QStatusBar QLabel {{
            font-size: 12px;
            color: {tokens['text_muted']};
        }}
        
        /* Progress Bar Flat Style */
        QProgressBar {{
            border: 1px solid {tokens['border']};
            background-color: {tokens['bg_control']};
            text-align: center;
            border-radius: 0px;
            font-family: "Segoe UI";
            font-size: 10px;
        }}
        QProgressBar::chunk {{
            background-color: {tokens['bg_selected']};
        }}
        
        /* Splitter */
        QSplitter::handle {{
            background-color: {tokens['border']};
        }}
        
        /* Menu Bar */
        QMenuBar {{
            background-color: {tokens['bg_base']};
            border-bottom: 1px solid {tokens['border']};
            color: {tokens['text_primary']};
            font-family: "Segoe UI";
            font-size: 13px;
        }}
        QMenuBar::item {{
            background-color: transparent;
            padding: 4px 8px;
        }}
        QMenuBar::item:selected {{
            background-color: {tokens['bg_hover']};
        }}
        
        /* QMenu */
        QMenu {{
            background-color: {tokens['bg_panel']};
            border: 1px solid {tokens['border']};
            color: {tokens['text_primary']};
            font-family: "Segoe UI";
        }}
        QMenu::item {{
            padding: 6px 20px 6px 20px;
        }}
        QMenu::item:selected {{
            background-color: {tokens['bg_selected']};
            color: #ffffff;
        }}
        
        /* QDialog */
        QDialog {{
            background-color: {tokens['bg_panel']};
        }}
        
        /* Settings Inputs */
        QLineEdit {{
            background-color: {tokens['bg_control']};
            border: 1px solid {tokens['border']};
            color: {tokens['text_primary']};
            padding: 4px 8px;
            border-radius: 4px;
            font-family: "Segoe UI";
        }}
        QComboBox {{
            background-color: {tokens['bg_control']};
            border: 1px solid {tokens['border']};
            color: {tokens['text_primary']};
            padding: 4px 8px;
            border-radius: 4px;
            font-family: "Segoe UI";
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {tokens['bg_control']};
            border: 1px solid {tokens['border']};
            color: {tokens['text_primary']};
            selection-background-color: {tokens['bg_selected']};
        }}
    """


def apply_theme(app: QApplication = None) -> None:
    global _current_tokens
    if app is None:
        app = QApplication.instance()
    if app is None:
        return

    is_dark = app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    _current_tokens = DARK_TOKENS if is_dark else LIGHT_TOKENS
    app.setStyleSheet(generate_qss(_current_tokens))


class QFlashHelper(QObject):
    def __init__(self, widget: QWidget) -> None:
        super().__init__()
        self.widget = widget
        self._color = QColor(0, 0, 0, 0)
        self.base_style = widget.styleSheet()
        
    @pyqtProperty(QColor)
    def flashColor(self) -> QColor:
        return self._color
        
    @flashColor.setter
    def flashColor(self, color: QColor) -> None:
        self._color = color
        if color.alpha() == 0:
            self.widget.setStyleSheet(self.base_style)
        else:
            rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha() / 255.0:.3f})"
            self.widget.setStyleSheet(f"{self.base_style}\nbackground-color: {rgba};")


class AnimationHelper:
    @staticmethod
    def fade_in(widget: QWidget, duration_ms: int = 180) -> QPropertyAnimation:
        settings = QSettings("EZTrimr", "EZTrimr")
        if settings.value("reduce_motion", False, type=bool):
            widget.show()
            return None
            
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            
        effect.setOpacity(0.0)
        widget.show()
        
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration_ms)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        if not hasattr(widget, "_anims"):
            widget._anims = []
        widget._anims.append(anim)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.finished.connect(lambda: widget._anims.remove(anim) if anim in getattr(widget, "_anims", []) else None)
        anim.start()
        return anim

    @staticmethod
    def fade_out(widget: QWidget, duration_ms: int = 180, then_hide: bool = True) -> QPropertyAnimation:
        settings = QSettings("EZTrimr", "EZTrimr")
        if settings.value("reduce_motion", False, type=bool):
            if then_hide:
                widget.hide()
            return None
            
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            
        effect.setOpacity(1.0)
        
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration_ms)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        if not hasattr(widget, "_anims"):
            widget._anims = []
        widget._anims.append(anim)
        
        def on_finished():
            if then_hide:
                widget.hide()
            widget.setGraphicsEffect(None)
            if anim in getattr(widget, "_anims", []):
                widget._anims.remove(anim)
                
        anim.finished.connect(on_finished)
        anim.start()
        return anim

    @staticmethod
    def slide_in(widget: QWidget, direction: str = "up", distance: int = 8, duration_ms: int = 200) -> QParallelAnimationGroup:
        settings = QSettings("EZTrimr", "EZTrimr")
        if settings.value("reduce_motion", False, type=bool):
            widget.show()
            return None
            
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            
        effect.setOpacity(0.0)
        widget.show()
        
        target_pos = widget.pos()
        if direction == "up":
            start_pos = target_pos + QPoint(0, distance)
        else:
            start_pos = target_pos - QPoint(0, distance)
            
        pos_anim = QPropertyAnimation(widget, b"pos")
        pos_anim.setDuration(duration_ms)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(target_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        opacity_anim = QPropertyAnimation(effect, b"opacity")
        opacity_anim.setDuration(duration_ms)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        group = QParallelAnimationGroup(widget)
        group.addAnimation(pos_anim)
        group.addAnimation(opacity_anim)
        
        if not hasattr(widget, "_anims"):
            widget._anims = []
        widget._anims.append(group)
        
        def cleanup():
            widget.setGraphicsEffect(None)
            if group in getattr(widget, "_anims", []):
                widget._anims.remove(group)
                
        group.finished.connect(cleanup)
        group.start()
        return group

    @staticmethod
    def color_flash(widget: QWidget, color: QColor, duration_ms: int = 600) -> QPropertyAnimation:
        settings = QSettings("EZTrimr", "EZTrimr")
        if settings.value("reduce_motion", False, type=bool):
            return None
            
        helper = QFlashHelper(widget)
        if not hasattr(widget, "_flash_helpers"):
            widget._flash_helpers = []
        widget._flash_helpers.append(helper)
        
        anim = QPropertyAnimation(helper, b"flashColor")
        anim.setDuration(duration_ms)
        anim.setStartValue(QColor(color.red(), color.green(), color.blue(), 150))
        anim.setEndValue(QColor(color.red(), color.green(), color.blue(), 0))
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        def cleanup():
            if helper in getattr(widget, "_flash_helpers", []):
                widget._flash_helpers.remove(helper)
                
        anim.finished.connect(cleanup)
        anim.start()
        return anim
