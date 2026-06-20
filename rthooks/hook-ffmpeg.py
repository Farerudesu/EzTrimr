import sys
import os

if getattr(sys, "frozen", False):
    _base = sys._MEIPASS
    suffix = ".exe" if sys.platform == "win32" else ""
    os.environ["EZTRIMR_FFMPEG"]  = os.path.join(_base, f"ffmpeg{suffix}")
    os.environ["EZTRIMR_FFPROBE"] = os.path.join(_base, f"ffprobe{suffix}")
