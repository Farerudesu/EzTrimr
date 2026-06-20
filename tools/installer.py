import os
import sys
import shutil
import zipfile
import re
import subprocess
import tempfile
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QProgressBar,
    QStackedWidget,
    QWidget,
    QFileDialog,
    QMessageBox,
    QTextEdit
)

# Constants
VERSION = "1.0.0"
APP_NAME = "EZTrimr"
DEFAULT_INSTALL_SUBDIR = f"Programs\\{APP_NAME}"

# Helper to find portable zip
def find_portable_zip():
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        zip_path = os.path.join(base_dir, "EZTrimr-portable.zip")
        if os.path.exists(zip_path):
            return zip_path
    local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "EZTrimr-portable.zip")
    if os.path.exists(local_path):
        return local_path
    return "EZTrimr-portable.zip"


class ZipExtractorThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, zip_path, dest_dir):
        super().__init__()
        self.zip_path = zip_path
        self.dest_dir = dest_dir

    def run(self):
        try:
            if not os.path.exists(self.dest_dir):
                os.makedirs(self.dest_dir, exist_ok=True)

            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                total_files = len(file_list)
                if total_files == 0:
                    self.finished.emit(False, "Zip archive is empty.")
                    return

                for idx, file in enumerate(file_list):
                    # Extract single file
                    zip_ref.extract(file, self.dest_dir)
                    percent = int(((idx + 1) / total_files) * 100)
                    self.progress.emit(percent)
                    self.log.emit(f"Extracted: {file}")

            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class InstallerWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Setup")
        self.setFixedSize(520, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Style Sheet
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QLabel#title {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
            }
            QLabel#subtitle {
                font-size: 13px;
                color: #aaaaaa;
            }
            QLineEdit {
                background-color: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #4a90e2;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #4c4c4c;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 80px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2b2b2b;
            }
            QPushButton#actionButton {
                background-color: #4a90e2;
                border: none;
                font-weight: bold;
            }
            QPushButton#actionButton:hover {
                background-color: #357abd;
            }
            QPushButton#actionButton:pressed {
                background-color: #1a4f80;
            }
            QProgressBar {
                background-color: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4a90e2;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #121212;
                border: 1px solid #2d2d2d;
                border-radius: 4px;
                font-family: "Consolas", monospace;
                font-size: 11px;
                color: #88c0d0;
            }
        """)

        # Main layouts
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)

        # Content stack
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # Setup pages
        self.init_page_welcome()
        self.init_page_folder()
        self.init_page_options()
        self.init_page_progress()
        self.init_page_finished()

        # Bottom navigation row
        self.nav_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_back = QPushButton("< Back")
        self.btn_next = QPushButton("Next >")
        self.btn_next.setObjectName("actionButton")

        self.nav_layout.addWidget(self.btn_cancel)
        self.nav_layout.addStretch()
        self.nav_layout.addWidget(self.btn_back)
        self.nav_layout.addWidget(self.btn_next)
        self.layout.addLayout(self.nav_layout)

        # Connect navigation
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_back.clicked.connect(self.on_back)
        self.btn_next.clicked.connect(self.on_next)

        # Default state
        self.update_nav_buttons()

    def update_nav_buttons(self):
        idx = self.stack.currentIndex()
        self.btn_back.setVisible(idx > 0 and idx < 3)
        self.btn_cancel.setVisible(idx < 4)
        
        if idx == 2:
            self.btn_next.setText("Install")
        elif idx == 4:
            self.btn_next.setText("Finish")
            self.btn_back.setVisible(False)
            self.btn_cancel.setVisible(False)
        else:
            self.btn_next.setText("Next >")

        self.btn_next.setEnabled(True)

    def on_back(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self.update_nav_buttons()

    def on_next(self):
        idx = self.stack.currentIndex()
        if idx == 1:
            # Validate target path
            path = self.txt_path.text().strip()
            if not path:
                QMessageBox.warning(self, "Invalid Path", "Please specify a folder to install to.")
                return
            self.install_dir = path
            self.stack.setCurrentIndex(idx + 1)
            self.update_nav_buttons()
        elif idx == 2:
            # Proceed to install
            self.stack.setCurrentIndex(idx + 1)
            self.update_nav_buttons()
            self.start_installation()
        elif idx == 4:
            # Close installer and optionally launch app
            if self.chk_launch.isChecked():
                exe_path = os.path.join(self.install_dir, "EZTrimr.exe")
                if os.path.exists(exe_path):
                    subprocess.Popen([exe_path], cwd=self.install_dir)
            self.accept()
        else:
            self.stack.setCurrentIndex(idx + 1)
            self.update_nav_buttons()

    # --- Pages Initializers ---
    def init_page_welcome(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel(f"Welcome to the {APP_NAME} Setup Wizard")
        title.setObjectName("title")
        lay.addWidget(title)

        desc = QLabel(
            f"This wizard will install {APP_NAME} version {VERSION} on your computer.\n\n"
            "EZTrimr is a dynamic, hardware-accelerated video cutter and audio processor. "
            "It is recommended that you close all other applications before continuing.\n\n"
            "Click Next to continue, or Cancel to exit Setup."
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)
        lay.addStretch()
        self.stack.addWidget(page)

    def init_page_folder(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("Select Destination Location")
        title.setObjectName("title")
        lay.addWidget(title)

        sub = QLabel("Where should EZTrimr be installed?")
        sub.setObjectName("subtitle")
        lay.addWidget(sub)

        desc = QLabel(
            "Setup will install EZTrimr in the following folder. "
            "To install in a different folder, click Browse and select another folder.\n"
            "Installing to your local profile does not require administrator rights."
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)

        path_lay = QHBoxLayout()
        self.txt_path = QLineEdit()
        # Default user path: AppData/Local/Programs/EZTrimr
        default_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), DEFAULT_INSTALL_SUBDIR)
        self.txt_path.setText(default_path)
        
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.on_browse)
        path_lay.addWidget(self.txt_path)
        path_lay.addWidget(btn_browse)
        lay.addLayout(path_lay)
        
        lay.addStretch()
        self.stack.addWidget(page)

    def on_browse(self):
        curr = self.txt_path.text()
        folder = QFileDialog.getExistingDirectory(self, "Select Installation Folder", curr)
        if folder:
            self.txt_path.setText(os.path.normpath(folder))

    def init_page_options(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("Select Additional Tasks")
        title.setObjectName("title")
        lay.addWidget(title)

        sub = QLabel("Which shortcuts should be created?")
        sub.setObjectName("subtitle")
        lay.addWidget(sub)

        self.chk_desktop = QCheckBox("Create a desktop shortcut")
        self.chk_desktop.setChecked(True)
        lay.addWidget(self.chk_desktop)

        self.chk_startmenu = QCheckBox("Create shortcuts in the Start Menu programs folder")
        self.chk_startmenu.setChecked(True)
        lay.addWidget(self.chk_startmenu)

        lay.addStretch()
        self.stack.addWidget(page)

    def init_page_progress(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        title = QLabel("Installing...")
        title.setObjectName("title")
        lay.addWidget(title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        lay.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Extracting files...")
        lay.addWidget(self.lbl_status)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        lay.addWidget(self.log_view)

        self.stack.addWidget(page)

    def init_page_finished(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        title = QLabel("Setup Completed Successfully!")
        title.setObjectName("title")
        lay.addWidget(title)

        desc = QLabel(
            "EZTrimr has been successfully installed on your computer.\n\n"
            "Click Finish to exit the Setup Wizard."
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)

        self.chk_launch = QCheckBox("Launch EZTrimr now")
        self.chk_launch.setChecked(True)
        lay.addWidget(self.chk_launch)

        lay.addStretch()
        self.stack.addWidget(page)

    # --- Installation Pipeline ---
    def start_installation(self):
        self.btn_back.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_cancel.setEnabled(False)

        zip_path = find_portable_zip()
        if not os.path.exists(zip_path):
            QMessageBox.critical(self, "Setup Error", f"Installation source zip not found:\n{zip_path}")
            self.reject()
            return

        self.thread = ZipExtractorThread(zip_path, self.install_dir)
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.log.connect(self.log_view.append)
        self.thread.finished.connect(self.on_installation_done)
        self.thread.start()

    def on_installation_done(self, success, error_msg):
        if not success:
            QMessageBox.critical(self, "Installation Failed", f"An error occurred during extraction:\n{error_msg}")
            self.reject()
            return

        # Perform shortcut creations & Registry updates
        try:
            self.lbl_status.setText("Creating shortcuts and registering uninstaller...")
            self.log_view.append("Finalizing configuration...")

            exe_path = os.path.normpath(os.path.join(self.install_dir, "EZTrimr.exe"))
            
            # 1. Desktop shortcut
            if self.chk_desktop.isChecked():
                desktop_dir = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
                shortcut_path = os.path.join(desktop_dir, f"{APP_NAME}.lnk")
                self.create_win_shortcut(exe_path, shortcut_path, self.install_dir, exe_path)
                self.log_view.append("Desktop shortcut created.")

            # 2. Start Menu shortcut
            if self.chk_startmenu.isChecked():
                start_menu_programs = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
                shortcut_path = os.path.join(start_menu_programs, f"{APP_NAME}.lnk")
                self.create_win_shortcut(exe_path, shortcut_path, self.install_dir, exe_path)
                self.log_view.append("Start Menu shortcut created.")

            # 3. Register Uninstaller in HKCU
            self.register_uninstaller(self.install_dir)
            self.log_view.append("Uninstaller registered in Windows settings.")

            self.lbl_status.setText("Finished.")
            QTimer.singleShot(800, self.go_to_finished_page)
        except Exception as e:
            QMessageBox.warning(self, "Setup Finalization Warning", f"Could not create shortcuts or register uninstall:\n{str(e)}")
            self.go_to_finished_page()

    def go_to_finished_page(self):
        self.stack.setCurrentIndex(4)
        self.update_nav_buttons()

    def create_win_shortcut(self, target_path, shortcut_path, working_dir, icon_path):
        # Native PowerShell shortcut creation (zero dependencies, works out of the box)
        ps_cmd = f'''
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path.replace('\\', '\\\\')}")
        $Shortcut.TargetPath = "{target_path.replace('\\', '\\\\')}"
        $Shortcut.WorkingDirectory = "{working_dir.replace('\\', '\\\\')}"
        if ("{icon_path}") {{
            $Shortcut.IconLocation = "{icon_path.replace('\\', '\\\\')}"
        }}
        $Shortcut.Save()
        '''
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, creationflags=0x08000000)

    def register_uninstaller(self, install_dir):
        import winreg
        try:
            # We register in HKCU (Current User) so no admin privileges are required
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\EZTrimr"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            
            # This installer executable will serve as uninstaller if run with --uninstall
            setup_exe = os.path.normpath(sys.argv[0])
            # If running as script, use python setup command helper
            if not setup_exe.lower().endswith(".exe"):
                setup_exe = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            else:
                setup_exe = f'"{setup_exe}"'

            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f"{setup_exe} --uninstall")
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, os.path.join(install_dir, "EZTrimr.exe"))
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "EZTrimr")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
            winreg.CloseKey(key)
        except Exception as e:
            raise e


def run_uninstallation():
    # Show confirmation box
    app = QApplication(sys.argv)
    
    reply = QMessageBox.question(
        None,
        f"Uninstall {APP_NAME}",
        f"Are you sure you want to completely uninstall {APP_NAME} and all of its components?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No
    )
    
    if reply == QMessageBox.StandardButton.Yes:
        try:
            import winreg
            # 1. Look up install location from Registry
            install_dir = ""
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\EZTrimr"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                install_dir, _ = winreg.QueryValueEx(key, "InstallLocation")
                winreg.CloseKey(key)
            except WindowsError:
                pass

            # If not in registry, fall back to default LocalAppData programs path
            if not install_dir:
                install_dir = os.path.normpath(os.path.join(os.environ.get("LOCALAPPDATA", ""), DEFAULT_INSTALL_SUBDIR))

            # 2. Delete Shortcuts
            # Desktop
            desktop_dir = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
            desktop_lnk = os.path.join(desktop_dir, f"{APP_NAME}.lnk")
            if os.path.exists(desktop_lnk):
                os.remove(desktop_lnk)

            # Start Menu
            start_menu_programs = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
            startmenu_lnk = os.path.join(start_menu_programs, f"{APP_NAME}.lnk")
            if os.path.exists(startmenu_lnk):
                os.remove(startmenu_lnk)

            # 3. Clean up Registry
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            except WindowsError:
                pass

            # 4. Delete install folder files
            # Since the uninstaller might be running out of this folder (if they launched it directly),
            # we write a tiny batch helper script in the %TEMP% directory that waits for this process to close,
            # recursively deletes the install folder, and then deletes itself.
            if os.path.exists(install_dir):
                helper_path = os.path.join(tempfile.gettempdir(), "eztrimr_uninstall_helper.bat")
                
                # Batch helper content
                bat_content = f'''@echo off
:loop
tasklist | find /i "{os.path.basename(sys.argv[0])}" >nul
if %errorlevel% equ 0 (
    timeout /t 1 /nobreak >nul
    goto loop
)
if exist "{install_dir}" (
    rmdir /s /q "{install_dir}"
)
del "%~f0"
'''
                with open(helper_path, "w", encoding="utf-8") as f:
                    f.write(bat_content)

                # Spawn helper detached
                subprocess.Popen([helper_path], shell=True, creationflags=0x00000008) # DETACHED_PROCESS

            QMessageBox.information(None, "Uninstall Complete", f"{APP_NAME} has been uninstalled successfully.")
        except Exception as e:
            QMessageBox.critical(None, "Uninstall Error", f"Failed to complete uninstallation:\n{str(e)}")
            sys.exit(1)
    sys.exit(0)


def main():
    if "--uninstall" in sys.argv:
        run_uninstallation()
        return

    app = QApplication(sys.argv)
    wizard = InstallerWindow()
    wizard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
