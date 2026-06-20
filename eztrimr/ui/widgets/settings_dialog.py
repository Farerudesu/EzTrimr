from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QFormLayout,
    QTabWidget,
    QWidget,
    QCheckBox,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView
)
import config
from eztrimr.ui.icons import EZIcon


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Tab Widget for segments
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("settingsTabs")

        # --- Tab 1: General Settings ---
        general_widget = QWidget()
        general_layout = QFormLayout(general_widget)
        general_layout.setContentsMargins(12, 12, 12, 12)
        general_layout.setSpacing(10)
        general_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Theme Selector
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Dark Mode", "Light Mode"])
        general_layout.addRow("Theme:", self.theme_combo)

        # Default Export Path
        export_layout = QHBoxLayout()
        self.export_path_input = QLineEdit()
        self.export_path_input.setPlaceholderText("Use source folder")
        self.export_browse_btn = QPushButton("Browse...")
        export_layout.addWidget(self.export_path_input)
        export_layout.addWidget(self.export_browse_btn)
        general_layout.addRow("Export Path:", export_layout)

        # Checkboxes
        self.live_scrub_checkbox = QCheckBox("Live preview while scrubbing")
        self.waveform_checkbox = QCheckBox("Show waveform in timeline")
        general_layout.addRow("", self.live_scrub_checkbox)
        general_layout.addRow("", self.waveform_checkbox)

        # Add General Tab with settings icon
        self.tab_widget.addTab(general_widget, EZIcon.icon("settings", 14), "General")

        # --- Tab 2: Advanced Settings ---
        advanced_widget = QWidget()
        advanced_layout = QFormLayout(advanced_widget)
        advanced_layout.setContentsMargins(12, 12, 12, 12)
        advanced_layout.setSpacing(10)
        advanced_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # FFmpeg Path
        ffmpeg_layout = QHBoxLayout()
        self.ffmpeg_path_input = QLineEdit()
        self.ffmpeg_path_input.setText(config.FFMPEG_PATH)
        self.ffmpeg_browse_btn = QPushButton("Browse...")
        ffmpeg_layout.addWidget(self.ffmpeg_path_input)
        ffmpeg_layout.addWidget(self.ffmpeg_browse_btn)
        advanced_layout.addRow("FFmpeg Path:", ffmpeg_layout)

        # Default Audio Bitrate
        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems([
            "Auto (Match Source)",
            "128 kbps (Standard)",
            "192 kbps (High)",
            "256 kbps (Studio)",
            "320 kbps (Maximum)"
        ])
        advanced_layout.addRow("Audio Bitrate:", self.audio_bitrate_combo)

        # Log Level
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["Info", "Warning", "Error", "Debug"])
        advanced_layout.addRow("Log Level:", self.log_level_combo)

        self.tab_widget.addTab(advanced_widget, "Advanced")

        # --- Tab 3: Shortcuts Tab ---
        shortcuts_widget = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_widget)
        shortcuts_layout.setContentsMargins(12, 12, 12, 12)

        self.shortcuts_table = QTableWidget()
        self.shortcuts_table.setColumnCount(2)
        self.shortcuts_table.horizontalHeader().setVisible(False)
        self.shortcuts_table.verticalHeader().setVisible(False)
        self.shortcuts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.shortcuts_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.shortcuts_table.setShowGrid(False)
        self.shortcuts_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Width ratios (60% / 40%) using stretched column sizes
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Categories & shortcuts mapping
        shortcuts_data = [
            ("File", None),
            ("  Open file", "Ctrl+O"),
            ("  Export", "Ctrl+E"),
            ("  Export audio only", "Ctrl+Shift+E"),
            
            ("Timeline", None),
            ("  Set in-point", "I"),
            ("  Set out-point", "O"),
            ("  Step back 1s", "←"),
            ("  Step forward 1s", "→"),
            ("  Step back 5s", "Shift+←"),
            ("  Step forward 5s", "Shift+→"),
            ("  Go to start", "Home"),
            ("  Go to end", "End"),
            ("  Undo trim", "Ctrl+Z"),
            
            ("Audio", None),
            ("  Toggle mute", "Ctrl+M"),
            
            ("View", None),
            ("  Toggle waveform", "Ctrl+W"),
            ("  Keyboard ref.", "F1"),
            
            ("Queue", None),
            ("  Add to queue", "Ctrl+A"),
            ("  Remove selected", "Delete"),
            ("  Clear queue", "Ctrl+Shift+C"),
            
            ("General", None),
            ("  Cancel operation", "Escape"),
            ("  Quit", "Ctrl+Q"),
        ]

        self.shortcuts_table.setRowCount(len(shortcuts_data))
        from eztrimr.ui.theme import get_token
        bg_control_hex = get_token("bg_control").name()
        text_muted_hex = get_token("text_muted").name()
        text_primary_hex = get_token("text_primary").name()

        self.shortcuts_table.setAlternatingRowColors(True)
        self.shortcuts_table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                border: none;
            }
            QTableWidget::item {
                padding-left: 6px;
                border: none;
            }
        """)

        for row, (action, shortcut) in enumerate(shortcuts_data):
            self.shortcuts_table.setRowHeight(row, 28)
            if shortcut is None:
                # Category label row
                item = QTableWidgetItem(action.upper())
                item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                item.setForeground(QColor(text_muted_hex))
                item.setBackground(QColor(bg_control_hex))
                self.shortcuts_table.setItem(row, 0, item)
                self.shortcuts_table.setSpan(row, 0, 1, 2)
            else:
                # Action shortcut row
                item_action = QTableWidgetItem(action)
                item_action.setFont(QFont("Segoe UI", 10))
                item_action.setForeground(QColor(text_primary_hex))
                
                item_shortcut = QTableWidgetItem(shortcut)
                item_shortcut.setFont(QFont("Consolas", 10))
                item_shortcut.setForeground(QColor(text_muted_hex))
                item_shortcut.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                self.shortcuts_table.setItem(row, 0, item_action)
                self.shortcuts_table.setItem(row, 1, item_shortcut)

        shortcuts_layout.addWidget(self.shortcuts_table)

        # Add Shortcuts tab with keyboard icon
        self.tab_widget.addTab(shortcuts_widget, EZIcon.icon("keyboard", 14), "Shortcuts")

        layout.addWidget(self.tab_widget)
        layout.addSpacing(10)

        # Dialog Buttons (OK, Cancel)
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.setObjectName("exportButton")
        self.ok_button.setFixedWidth(80)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedWidth(80)

        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.ok_button)
        layout.addLayout(buttons_layout)

        # Connect slots
        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)
        
        self.export_browse_btn.clicked.connect(self.browse_export_path)
        self.ffmpeg_browse_btn.clicked.connect(self.browse_ffmpeg_path)

        self.load_settings()

    def browse_export_path(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Export Directory", self.export_path_input.text())
        if dir_path:
            self.export_path_input.setText(dir_path)

    def browse_ffmpeg_path(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Executable", self.ffmpeg_path_input.text(), "FFmpeg Executable (ffmpeg.exe);;All Files (*)")
        if file_path:
            self.ffmpeg_path_input.setText(file_path)

    def load_settings(self) -> None:
        settings = QSettings("EZTrimr", "EZTrimr")
        
        live_scrub = settings.value("preview/live_scrub", False)
        if isinstance(live_scrub, str):
            live_scrub = (live_scrub.lower() == "true")
        self.live_scrub_checkbox.setChecked(bool(live_scrub))
        
        show_waveform = settings.value("preview/show_waveform", False)
        if isinstance(show_waveform, str):
            show_waveform = (show_waveform.lower() == "true")
        self.waveform_checkbox.setChecked(bool(show_waveform))
        
        theme_val = settings.value("general/theme", "System Default")
        self.theme_combo.setCurrentText(theme_val)
        
        export_path = settings.value("general/export_path", "")
        self.export_path_input.setText(export_path)
        
        self.ffmpeg_path_input.setText(config.FFMPEG_PATH)
        
        a_bitrate = settings.value("advanced/audio_bitrate", "Auto (Match Source)")
        self.audio_bitrate_combo.setCurrentText(a_bitrate)
        
        log_lvl = settings.value("advanced/log_level", "Info")
        self.log_level_combo.setCurrentText(log_lvl)

    def save_settings(self) -> None:
        settings = QSettings("EZTrimr", "EZTrimr")
        settings.setValue("preview/live_scrub", self.live_scrub_checkbox.isChecked())
        settings.setValue("preview/show_waveform", self.waveform_checkbox.isChecked())
        settings.setValue("general/theme", self.theme_combo.currentText())
        settings.setValue("general/export_path", self.export_path_input.text())
        
        ffmpeg_path = self.ffmpeg_path_input.text()
        settings.setValue("advanced/ffmpeg_path", ffmpeg_path)
        config.FFMPEG_PATH = ffmpeg_path
        
        settings.setValue("advanced/audio_bitrate", self.audio_bitrate_combo.currentText())
        settings.setValue("advanced/log_level", self.log_level_combo.currentText())

    def on_ok_clicked(self) -> None:
        self.save_settings()
        self.accept()
