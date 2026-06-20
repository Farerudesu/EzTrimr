import sys
import os
import shutil

from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt6.QtGui import QIcon, QDesktopServices
from PyQt6.QtCore import QUrl, QSettings

from eztrimr.ui.main_window import MainWindow
from eztrimr.ui.theme import apply_theme
import config


def check_ffmpeg_path() -> None:
    while True:
        path = config.FFMPEG_PATH
        # Check if FFMPEG_PATH points to a file or resolves in path
        if path and (os.path.isfile(path) or shutil.which(path)):
            break

        # FFmpeg not found, prompt user
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("FFmpeg not found")
        msg.setText(
            "EZTrimr requires FFmpeg to work.\n\n"
            "Download it from ffmpeg.org and place ffmpeg.exe and ffprobe.exe "
            "in the same folder as EZTrimr.exe, or add them to your system PATH."
        )
        
        btn_open = msg.addButton("Open ffmpeg.org", QMessageBox.ButtonRole.ActionRole)
        btn_locate = msg.addButton("Locate manually...", QMessageBox.ButtonRole.ActionRole)
        btn_quit = msg.addButton("Quit App", QMessageBox.ButtonRole.DestructiveRole)
        
        msg.exec()
        
        clicked = msg.clickedButton()
        if clicked == btn_open:
            QDesktopServices.openUrl(QUrl("https://ffmpeg.org/download.html"))
        elif clicked == btn_locate:
            file_path, _ = QFileDialog.getOpenFileName(
                None, "Locate FFmpeg executable (ffmpeg.exe)", "", "FFmpeg (ffmpeg.exe ffmpeg);;All Files (*)"
            )
            if file_path:
                settings = QSettings("EZTrimr", "EZTrimr")
                settings.setValue("advanced/ffmpeg_path", file_path)
                config.FFMPEG_PATH = file_path
                
                dirname = os.path.dirname(file_path)
                suffix = ".exe" if os.name == "nt" else ""
                ffprobe_candidate = os.path.join(dirname, f"ffprobe{suffix}")
                if os.path.isfile(ffprobe_candidate):
                    config.FFPROBE_PATH = ffprobe_candidate
                    settings.setValue("advanced/ffprobe_path", ffprobe_candidate)
        else:
            sys.exit(1)


def main() -> int:
    app = QApplication(sys.argv)
    
    # Set app window icon relative to the executable/script directory
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    icon_path = os.path.join(base_dir, "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    # Check for FFmpeg presence before launching the UI
    check_ffmpeg_path()
    
    # Apply system-aware dark/light theme at launch
    apply_theme(app)
    
    # Dynamically update the theme if system colors change at runtime
    app.paletteChanged.connect(lambda palette: apply_theme(app))
    
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
