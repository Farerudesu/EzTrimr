import json
import os
import subprocess
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal
import config


class MediaLoader(QThread):
    probe_done = pyqtSignal(dict)
    thumbnail_done = pyqtSignal(str)
    load_failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, file_path: str, parent=None) -> None:
        super().__init__(parent)
        self.file_path = file_path

    def run(self) -> None:
        # --- STEP A: FFPROBE ---
        self.progress.emit("Analyzing media file...")
        
        # Build FFprobe command
        cmd = [
            config.FFPROBE_PATH,
            "-v", "error",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            self.file_path
        ]

        try:
            # Run ffprobe process without using shell=True to handle unicode paths safely
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
        except FileNotFoundError:
            self.load_failed.emit(
                "FFmpeg is not installed or not found in PATH. "
                "Please install FFmpeg and restart EZTrimr."
            )
            return
        except Exception as e:
            os.makedirs("logs", exist_ok=True)
            with open("logs/eztrimr.log", "a", encoding="utf-8") as f:
                f.write(f"FFprobe process execution failed: {str(e)}\n")
            self.load_failed.emit(f"Failed to start FFprobe process: {str(e)}")
            return

        if result.returncode != 0:
            os.makedirs("logs", exist_ok=True)
            with open("logs/eztrimr.log", "a", encoding="utf-8") as f:
                f.write(
                    f"FFprobe failed for {self.file_path}. "
                    f"Exit code: {result.returncode}. "
                    f"Stderr: {result.stderr.decode('utf-8', errors='replace')}\n"
                )
            self.load_failed.emit(
                "FFprobe could not read this file. It may be "
                "corrupted or in an unsupported container."
            )
            return

        if not result.stdout or result.stdout.strip() == b"":
            os.makedirs("logs", exist_ok=True)
            with open("logs/eztrimr.log", "a", encoding="utf-8") as f:
                f.write(f"FFprobe returned no stdout data for {self.file_path}.\n")
            self.load_failed.emit(
                f"FFprobe returned no data. Check your FFmpeg "
                f"installation at: {config.FFPROBE_PATH}"
            )
            return

        try:
            probe_data = json.loads(result.stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            self.load_failed.emit("FFprobe output was malformed. Try a different file.")
            return

        # Validate streams in probe output
        streams = probe_data.get("streams", [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        if not has_video and not has_audio:
            self.load_failed.emit("This file contains no recognisable media streams.")
            return

        # Check duration
        duration_sec = 0.0
        fmt = probe_data.get("format", {})
        if "duration" in fmt:
            try:
                duration_sec = float(fmt["duration"])
            except ValueError:
                pass

        if duration_sec <= 0.0:
            # Fallback to streams
            for s in streams:
                if "duration" in s:
                    try:
                        duration_sec = float(s["duration"])
                        break
                    except ValueError:
                        pass

        if duration_sec <= 0.0:
            self.load_failed.emit(
                "Could not determine file duration. The file may "
                "be empty or unfinished."
            )
            return

        # Successfully parsed metadata
        self.probe_done.emit(probe_data)

        # --- STEP B: FIRST FRAME EXTRACTION (FFMPEG) ---
        if not has_video:
            # Audio-only file: skip thumbnail extraction
            self.thumbnail_done.emit("")
            return

        self.progress.emit("Generating video thumbnail...")
        temp_path = tempfile.mktemp(suffix=".jpg", prefix="eztrimr_thumb_")

        # Build FFmpeg command: ffmpeg -y -ss 0 -i "in" -frames:v 1 -q:v 2 "out"
        ffmpeg_cmd = [
            config.FFMPEG_PATH,
            "-y",
            "-ss", "0",
            "-i", self.file_path,
            "-frames:v", "1",
            "-q:v", "2",
            temp_path
        ]

        try:
            result_ffmpeg = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            if result_ffmpeg.returncode == 0 and os.path.exists(temp_path):
                self.thumbnail_done.emit(temp_path)
            else:
                # Log extraction failure and emit empty thumbnail silently
                os.makedirs("logs", exist_ok=True)
                with open("logs/eztrimr.log", "a", encoding="utf-8") as log_file:
                    log_file.write(
                        f"FFmpeg thumbnail extraction failed for {self.file_path}. "
                        f"Exit code: {result_ffmpeg.returncode}. "
                        f"Error output: {result_ffmpeg.stderr.decode('utf-8', errors='replace')}\n"
                    )
                self.thumbnail_done.emit("")
        except Exception as e:
            # Log exception silently
            os.makedirs("logs", exist_ok=True)
            with open("logs/eztrimr.log", "a", encoding="utf-8") as log_file:
                log_file.write(f"Exception during thumbnail extraction: {str(e)}\n")
            self.thumbnail_done.emit("")
