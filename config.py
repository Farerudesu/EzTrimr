import shutil
import sys
from pathlib import Path

APP_NAME = "EZTrimr"
APP_VERSION = "0.1.0"

WINDOW_MIN_WIDTH = 960
WINDOW_MIN_HEIGHT = 600


VERSION = "1.0.0"
BUILD = "release"


def _find_ffmpeg(binary: str) -> str:
    import os
    
    # 0. Check QSettings first (if user located it manually)
    try:
        from PyQt6.QtCore import QSettings
        settings = QSettings("EZTrimr", "EZTrimr")
        saved_path = settings.value(f"advanced/{binary}_path", "")
        if saved_path and os.path.isfile(saved_path):
            return str(saved_path)
    except Exception:
        pass

    env_key = f"EZTRIMR_{binary.upper()}"
    env_val = os.environ.get(env_key)
    if env_val and os.path.isfile(env_val):
        return env_val

    filename = f"{binary}.exe" if sys.platform == "win32" else binary

    # 1. Check next to the running executable (sys.argv[0])
    try:
        argv_dir = Path(sys.argv[0]).parent.resolve()
        argv_path = argv_dir / filename
        if argv_path.is_file():
            return str(argv_path)
    except Exception:
        pass

    # 2. Same directory as config.py / main.py (running as script)
    local_dir = Path(__file__).parent.resolve()
    local_path = local_dir / filename
    if local_path.is_file():
        return str(local_path)

    # 3. Check PyInstaller _MEIPASS folder
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_path = Path(sys._MEIPASS) / filename
        if meipass_path.is_file():
            return str(meipass_path)

    # 4. shutil.which(binary) — system PATH
    found = shutil.which(binary)
    if found:
        return found

    # 5. Hardcoded fallback: "C:/ffmpeg/bin/{binary}.exe"
    fallback_path = Path(f"C:/ffmpeg/bin/{filename}")
    if fallback_path.is_file():
        return str(fallback_path)

    # Default fallback
    return binary


FFMPEG_PATH = _find_ffmpeg("ffmpeg")
FFPROBE_PATH = _find_ffmpeg("ffprobe")


def _check_gpu_encoder_support(ffmpeg_path: str, encoder: str) -> bool:
    import subprocess
    import os
    cmd = [
        ffmpeg_path,
        "-y",
        "-f", "lavfi",
        "-i", "color=c=black:s=64x64:d=0.1",
        "-c:v", encoder,
        "-f", "null",
        "-"
    ]
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            timeout=2.0
        )
        return result.returncode == 0
    except Exception:
        return False


NVENC_SUPPORTED = _check_gpu_encoder_support(FFMPEG_PATH, "h264_nvenc")
QSV_SUPPORTED = _check_gpu_encoder_support(FFMPEG_PATH, "h264_qsv")
AMF_SUPPORTED = _check_gpu_encoder_support(FFMPEG_PATH, "h264_amf")

