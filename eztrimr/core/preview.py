import os
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal


def extract_frame_bytes(
    input_path: str,
    timestamp_seconds: float,
    ffmpeg_path: str
) -> bytes:
    """Extracts a single frame from the input file at a given timestamp using FFmpeg and returns the JPEG bytes."""
    # Attempt scaled extraction first (much faster)
    cmd_scaled = [
        ffmpeg_path,
        "-ss", f"{timestamp_seconds:.3f}",
        "-i", input_path,
        "-vf", "scale=640:-2:flags=fast_bilinear",
        "-frames:v", "1",
        "-q:v", "2",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "pipe:1"
    ]

    try:
        result = subprocess.run(
            cmd_scaled,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception:
        pass

    # Fallback to original full-resolution extraction if scaling fails
    cmd_full = [
        ffmpeg_path,
        "-ss", f"{timestamp_seconds:.3f}",
        "-i", input_path,
        "-frames:v", "1",
        "-q:v", "2",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "pipe:1"
    ]

    try:
        result = subprocess.run(
            cmd_full,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
    except FileNotFoundError:
        raise RuntimeError("FFmpeg executable was not found.")

    if result.returncode != 0:
        stderr_msg = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(stderr_msg)

    return result.stdout


class PreviewFrameWorker(QThread):
    success = pyqtSignal(bytes)
    failure = pyqtSignal(str)

    def __init__(
        self,
        input_path: str,
        timestamp_seconds: float,
        ffmpeg_path: str,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.input_path = input_path
        self.timestamp_seconds = timestamp_seconds
        self.ffmpeg_path = ffmpeg_path

    def run(self) -> None:
        try:
            jpeg_bytes = extract_frame_bytes(
                self.input_path,
                self.timestamp_seconds,
                self.ffmpeg_path
            )
            if jpeg_bytes:
                self.success.emit(jpeg_bytes)
            else:
                self.failure.emit("Preview image bytes could not be retrieved.")
        except Exception as e:
            self.failure.emit(str(e))
