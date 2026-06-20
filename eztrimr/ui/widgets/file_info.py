import os
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QDragEnterEvent, QDragMoveEvent, QDropEvent, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QFrame
)
from eztrimr.core.state import app_state
from eztrimr.core.utils import codec_display_name


class MergeQueueListWidget(QListWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                app_state.add_merge_file(path)
            
            p = self.parent()
            while p and not hasattr(p, "refresh_queue"):
                p = p.parent()
            if p:
                p.refresh_queue()
        else:
            super().dropEvent(event)


class FileInfoPanel(QWidget):
    queueChanged = pyqtSignal()
    mergeExportRequested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("leftPanel")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)

        # --- Section 1: FILE INFO ---
        self.file_info_header = QLabel("FILE INFO")
        self.file_info_header.setObjectName("sectionHeader")
        main_layout.addWidget(self.file_info_header)
        main_layout.addSpacing(12)

        # 4 rows: Name, Duration, Resolution, Format
        info_rows = [
            ("Name:", "—"),
            ("Duration:", "—"),
            ("Resolution:", "—"),
            ("Format:", "—")
        ]
        
        self.info_labels = {}
        self.info_row_widgets = []
        for label_text, default_val in info_rows:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            lbl = QLabel(label_text)
            lbl.setObjectName("fileInfoLabel")
            
            val = QLabel(default_val)
            val.setObjectName("fileInfoValue")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            
            row_layout.addWidget(lbl)
            row_layout.addWidget(val)
            
            self.info_labels[label_text.replace(":", "").lower()] = val
            self.info_row_widgets.append((lbl, val))
            
            main_layout.addLayout(row_layout)
            main_layout.addSpacing(8)

        main_layout.addSpacing(4)

        divider = QFrame()
        divider.setObjectName("panelDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(divider)
        main_layout.addSpacing(12)

        # --- Section 2: MERGE QUEUE ---
        self.merge_queue_header = QLabel("MERGE QUEUE")
        self.merge_queue_header.setObjectName("sectionHeader")
        main_layout.addWidget(self.merge_queue_header)
        main_layout.addSpacing(12)

        # Queue List Container
        self.queue_container_layout = QVBoxLayout()
        self.queue_container_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_container_layout.setSpacing(0)

        self.queue_list = MergeQueueListWidget()
        self.queue_list.setObjectName("queueList")
        self.queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self._show_context_menu)
        self.queue_container_layout.addWidget(self.queue_list)

        # Redesigned Empty State
        self.empty_label = QLabel()
        self.empty_label.setObjectName("emptyQueueLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.queue_container_layout.addWidget(self.empty_label)

        main_layout.addLayout(self.queue_container_layout)
        main_layout.addSpacing(8)

        # Queue Control Buttons Row
        self.queue_controls_layout = QHBoxLayout()
        self.queue_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_controls_layout.setSpacing(4)
        
        self.add_file_button = QPushButton("Add")
        self.add_file_button.setObjectName("queueControlBtn")
        self.add_file_button.setToolTip("Add file to merge queue  [Ctrl+A]")

        self.move_up_button = QPushButton()
        self.move_up_button.setObjectName("queueControlBtn")
        self.move_up_button.setToolTip("Move selected item up")
        
        self.move_down_button = QPushButton()
        self.move_down_button.setObjectName("queueControlBtn")
        self.move_down_button.setToolTip("Move selected item down")
        
        self.remove_button = QPushButton()
        self.remove_button.setObjectName("queueControlBtn")
        self.remove_button.setToolTip("Remove selected item  [Delete]")
        
        self.clear_queue_button = QPushButton("Clear")
        self.clear_queue_button.setObjectName("clearQueueButton")
        self.clear_queue_button.setToolTip("Clear all items  [Ctrl+Shift+C]")
        
        self.queue_controls_layout.addWidget(self.add_file_button)
        self.queue_controls_layout.addWidget(self.move_up_button)
        self.queue_controls_layout.addWidget(self.move_down_button)
        self.queue_controls_layout.addWidget(self.remove_button)
        self.queue_controls_layout.addStretch()
        self.queue_controls_layout.addWidget(self.clear_queue_button)
        
        main_layout.addLayout(self.queue_controls_layout)
        main_layout.addSpacing(12)

        self.merge_export_button = QPushButton("Merge & Export")
        self.merge_export_button.setObjectName("mergeExportButton")
        self.merge_export_button.setToolTip("Export merged files  [Ctrl+E]")
        main_layout.addWidget(self.merge_export_button)

        main_layout.addStretch()

        # Wire handlers
        self.add_file_button.clicked.connect(self.add_files_dialog)
        self.move_up_button.clicked.connect(self.move_up)
        self.move_down_button.clicked.connect(self.move_down)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_queue_button.clicked.connect(self.clear_queue)
        self.merge_export_button.clicked.connect(self.mergeExportRequested.emit)

        self.queue_list.currentRowChanged.connect(self.update_button_states)
        
        # Load empty state and icons
        self.refresh_empty_state_label()
        self.init_icons()
        self.set_queue_empty(True)
        self.update_button_states()

    def init_icons(self) -> None:
        from eztrimr.ui.icons import EZIcon
        self.move_up_button.setIcon(EZIcon.icon("arrow-up", 14))
        self.move_down_button.setIcon(EZIcon.icon("arrow-down", 14))
        self.remove_button.setIcon(EZIcon.icon("trash", 14))
        self.clear_queue_button.setIcon(EZIcon.icon("close", 14))

    def refresh_empty_state_label(self) -> None:
        from eztrimr.ui.icons import EZIcon
        from eztrimr.ui.theme import get_token
        color = get_token("text_muted")
        muted_hex = color.name()
        faded_hex = QColor(color.red(), color.green(), color.blue(), int(255 * 0.5)).name()
        
        self.empty_label.setText(
            f"<div align='center'>"
            f"{EZIcon.to_base64_img('plus', 32, color)}<br/><br/>"
            f"<span style='font-size: 13px; font-weight: bold; color: {muted_hex};'>No files in queue</span><br/>"
            f"<span style='font-size: 11px; color: {faded_hex};'>Add files to merge them together</span>"
            f"</div>"
        )

    def animate_info_entrance(self) -> None:
        from eztrimr.ui.theme import AnimationHelper
        for idx, (lbl, val) in enumerate(self.info_row_widgets):
            delay = idx * 50
            QTimer.singleShot(delay, lambda l=lbl, v=val: (
                AnimationHelper.slide_in(l, "up", 8, 200),
                AnimationHelper.slide_in(v, "up", 8, 200)
            ))

    def set_queue_empty(self, is_empty: bool) -> None:
        if is_empty:
            self.queue_list.hide()
            self.empty_label.show()
            self.move_up_button.hide()
            self.move_down_button.hide()
            self.remove_button.hide()
            self.clear_queue_button.hide()
        else:
            self.queue_list.show()
            self.empty_label.hide()
            self.move_up_button.show()
            self.move_down_button.show()
            self.remove_button.show()
            self.clear_queue_button.show()

    def refresh_queue(self) -> None:
        curr_row = self.queue_list.currentRow()
        self.queue_list.clear()
        
        for idx, path in enumerate(app_state.merge_files, 1):
            self.queue_list.addItem(f"{idx:02d}. {os.path.basename(path)}")
        
        is_empty = (len(app_state.merge_files) == 0)
        self.set_queue_empty(is_empty)
        
        if not is_empty:
            if curr_row >= len(app_state.merge_files):
                curr_row = len(app_state.merge_files) - 1
            self.queue_list.setCurrentRow(curr_row)
        
        self.update_button_states()
        self.queueChanged.emit()

    def move_up(self) -> None:
        row = self.queue_list.currentRow()
        if row > 0:
            files = app_state.merge_files
            files[row], files[row - 1] = files[row - 1], files[row]
            app_state.is_dirty = True
            self.refresh_queue()
            self.queue_list.setCurrentRow(row - 1)

    def move_down(self) -> None:
        row = self.queue_list.currentRow()
        if 0 <= row < len(app_state.merge_files) - 1:
            files = app_state.merge_files
            files[row], files[row + 1] = files[row + 1], files[row]
            app_state.is_dirty = True
            self.refresh_queue()
            self.queue_list.setCurrentRow(row + 1)

    def remove_selected(self) -> None:
        row = self.queue_list.currentRow()
        if 0 <= row < len(app_state.merge_files):
            path = app_state.merge_files[row]
            app_state.remove_merge_file(path)
            self.refresh_queue()

    def clear_queue(self) -> None:
        from PyQt6.QtWidgets import QMessageBox
        # Add confirmation guard
        reply = QMessageBox.question(
            self,
            "Clear Merge Queue",
            "Are you sure you want to clear all items from the merge queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            app_state.clear_merge_files()
            self.refresh_queue()

    def add_files_dialog(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Add Media Files to Merge Queue")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters([
            "All files (*.*)",
            "Common video (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v)",
            "Common audio (*.mp3 *.wav *.aac *.flac *.ogg *.m4a *.opus)",
        ])
        dialog.selectNameFilter("All files (*.*)")
        
        # Restore last-used folder
        settings = QSettings("EZTrimr", "EZTrimr") if 'QSettings' in globals() else QSettings("EZTrimr", "EZTrimr")
        from PyQt6.QtCore import QSettings
        settings = QSettings("EZTrimr", "EZTrimr")
        folder = settings.value("last_folder", "")
        if folder:
            dialog.setDirectory(folder)
            
        if dialog.exec():
            files = dialog.selectedFiles()
            for path in files:
                app_state.add_merge_file(path)
                settings.setValue("last_folder", os.path.dirname(path))
            self.refresh_queue()

    def update_button_states(self) -> None:
        row = self.queue_list.currentRow()
        has_selection = (row != -1)
        num_items = len(app_state.merge_files)
        
        self.move_up_button.setEnabled(has_selection and row > 0)
        self.move_down_button.setEnabled(has_selection and row < num_items - 1)
        self.remove_button.setEnabled(has_selection)
        self.clear_queue_button.setEnabled(num_items > 0)
        self.merge_export_button.setEnabled(num_items > 0)

    def _show_context_menu(self, pos) -> None:
        from PyQt6.QtWidgets import QMenu
        item = self.queue_list.itemAt(pos)
        if not item:
            return
        
        menu = QMenu(self)
        
        up_action = menu.addAction("Move Up")
        down_action = menu.addAction("Move Down")
        menu.addSeparator()
        remove_action = menu.addAction("Remove")
        
        row = self.queue_list.row(item)
        up_action.setEnabled(row > 0)
        down_action.setEnabled(row < len(app_state.merge_files) - 1)
        
        action = menu.exec(self.queue_list.mapToGlobal(pos))
        if action == up_action:
            self.move_up()
        elif action == down_action:
            self.move_down()
        elif action == remove_action:
            self.remove_selected()

    def update_info(self) -> None:
        name = app_state.file_name
        if len(name) > 24:
            truncated_name = name[:21] + "…"
        else:
            truncated_name = name
        
        self.info_labels["name"].setText(truncated_name)
        self.info_labels["name"].setToolTip(app_state.file_path)
        
        font = self.info_labels["name"].font()
        font.setWeight(QFont.Weight.Medium)
        self.info_labels["name"].setFont(font)

        self.info_labels["duration"].setText(app_state.formatted_duration())
        self.info_labels["resolution"].setText(app_state.resolution_str())

        v_codec = codec_display_name(app_state.video_codec)
        a_codec = codec_display_name(app_state.audio_codec)
        size_str = app_state.formatted_size()

        if app_state.has_video:
            if app_state.has_audio:
                format_val = f"{v_codec} / {a_codec} — {size_str}"
            else:
                format_val = f"{v_codec} — {size_str}"
        else:
            if app_state.has_audio:
                format_val = f"{a_codec} — {size_str}"
            else:
                format_val = size_str
        self.info_labels["format"].setText(format_val)

    def reset_info(self) -> None:
        self.info_labels["name"].setText("—")
        self.info_labels["name"].setToolTip("")
        
        font = self.info_labels["name"].font()
        font.setWeight(QFont.Weight.Normal)
        self.info_labels["name"].setFont(font)
        
        self.info_labels["duration"].setText("—")
        self.info_labels["resolution"].setText("—")
        self.info_labels["format"].setText("—")
