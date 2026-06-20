import os
import re
import subprocess
import json
from PyQt6.QtCore import QThread, pyqtSignal

# Regex to match time=HH:MM:SS.xx or time=HH:MM:SS
TIME_REGEX = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})(?:\.(\d{2,3}))?")


def parse_ffmpeg_time(line: str) -> float | None:
    """Parses progression duration from FFmpeg output lines (e.g., 'time=00:01:05.25').

    Returns total seconds as a float, or None if no match is found.
    """
    match = TIME_REGEX.search(line)
    if not match:
        return None

    h = int(match.group(1))
    m = int(match.group(2))
    s = int(match.group(3))
    
    ms_str = match.group(4)
    if ms_str:
        # Pad milliseconds to fractional seconds
        ms = float(f"0.{ms_str}")
    else:
        ms = 0.0

    return h * 3600 + m * 60 + s + ms


def probe_media_file(file_path: str, ffmpeg_path: str) -> dict | None:
    """Probes a media file using ffprobe and returns basic stream properties."""
    ffmpeg_dir = os.path.dirname(ffmpeg_path)
    ffprobe_path = os.path.join(ffmpeg_dir, "ffprobe.exe" if os.name == "nt" else "ffprobe")
    if not os.path.exists(ffprobe_path):
        ffprobe_path = "ffprobe"

    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        file_path
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
            startupinfo=startupinfo
        )
        if result.returncode == 0:
            data = json.loads(result.stdout.decode("utf-8", errors="replace"))
            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
            
            res = {}
            if video_stream:
                res["has_video"] = True
                res["width"] = int(video_stream.get("width", 0))
                res["height"] = int(video_stream.get("height", 0))
                res["video_codec"] = video_stream.get("codec_name", "")
                
                # Parse FPS
                r_fps = video_stream.get("r_frame_rate", "0/0")
                try:
                    from fractions import Fraction
                    frac = Fraction(r_fps)
                    res["fps"] = round(float(frac), 3)
                except Exception:
                    res["fps"] = 0.0
            else:
                res["has_video"] = False
                
            if audio_stream:
                res["has_audio"] = True
                res["audio_codec"] = audio_stream.get("codec_name", "")
                res["sample_rate"] = int(audio_stream.get("sample_rate", 0))
                res["channels"] = int(audio_stream.get("channels", 0))
            else:
                res["has_audio"] = False
                
            return res
    except Exception:
        pass
    return None


def check_merge_compatibility(file_paths: list[str], ffmpeg_path: str) -> tuple[bool, int, int]:
    """Probes all files to see if they are compatible for direct stream copying.

    Returns (is_compatible, target_width, target_height).
    If incompatible, target_width/height will be the dimensions of the first video.
    """
    if not file_paths:
        return True, 1920, 1080
        
    # For testing/mocking where files don't actually exist on disk
    if not all(os.path.exists(p) for p in file_paths):
        return True, 1920, 1080
        
    first_props = probe_media_file(file_paths[0], ffmpeg_path)
    if not first_props:
        return True, 1920, 1080
        
    first_width = first_props.get("width", 1920)
    first_height = first_props.get("height", 1080)
    
    is_compatible = True
    for path in file_paths[1:]:
        props = probe_media_file(path, ffmpeg_path)
        if not props:
            is_compatible = False
            break
            
        if first_props.get("has_video") != props.get("has_video"):
            is_compatible = False
            break
        if first_props.get("has_video"):
            if first_props.get("width") != props.get("width") or first_props.get("height") != props.get("height"):
                is_compatible = False
                break
            if first_props.get("video_codec") != props.get("video_codec"):
                is_compatible = False
                break
                
        if first_props.get("has_audio") != props.get("has_audio"):
            is_compatible = False
            break
        if first_props.get("has_audio"):
            if first_props.get("sample_rate") != props.get("sample_rate") or first_props.get("channels") != props.get("channels"):
                is_compatible = False
                break
            if first_props.get("audio_codec") != props.get("audio_codec"):
                is_compatible = False
                break
                
    return is_compatible, first_width, first_height


def build_trim_command(
    input_path: str,
    output_path: str,
    in_point: float,
    out_point: float,
    ffmpeg_path: str,
    has_video: bool = True,
    audio_mute: bool = False,
    audio_filter_chain: str = "",
    audio_extract_only: bool = False,
    audio_extract_format: str = "mp3",
    export_video_codec: str = "copy",
    export_video_resolution: str = "original",
    export_video_fps: str = "original",
    export_video_crf: int = 23,
    export_video_bitrate: str = "Auto",
    export_hw_accel: str = "None (CPU)"
) -> list[str]:
    """Generates the FFmpeg command to cut a video region, applying audio and video settings."""
    base_cmd = [
        ffmpeg_path,
        "-y",
        "-ss", f"{in_point:.3f}",
        "-to", f"{out_point:.3f}",
        "-i", input_path
    ]

    if audio_mute and not has_video:
        return base_cmd + ["-an", output_path]

    if audio_extract_only or not has_video:
        # Extract audio only or input is audio-only
        cmd = base_cmd + ["-vn"]
        if audio_filter_chain:
            cmd += ["-af", audio_filter_chain]
        
        # Audio format codec mapping
        fmt = audio_extract_format.lower()
        if not audio_extract_only:
            # Determine format from output file extension
            _, ext = os.path.splitext(output_path)
            fmt = ext.lstrip(".").lower()

        if fmt == "mp3":
            cmd += ["-c:a", "libmp3lame"]
        elif fmt == "wav":
            cmd += ["-c:a", "pcm_s16le"]
        elif fmt == "aac" or fmt == "m4a":
            cmd += ["-c:a", "aac"]
        elif fmt == "flac":
            cmd += ["-c:a", "flac"]
        elif fmt == "ogg":
            cmd += ["-c:a", "libvorbis"]
        else:
            if audio_filter_chain:
                cmd += ["-c:a", "aac"]
            else:
                cmd += ["-c:a", "copy"]
            
        cmd.append(output_path)
        return cmd

    # Determine if video needs re-encoding
    video_reencode = (
        export_video_codec != "copy"
        or export_video_resolution != "original"
        or export_video_fps != "original"
        or (export_video_bitrate != "Auto" and export_video_bitrate != "Auto (Match Source)")
        or export_hw_accel != "None (CPU)"
    )

    if not video_reencode:
        # Fast copy video stream
        if audio_mute:
            cmd = base_cmd + ["-c:v", "copy", "-an"]
        elif audio_filter_chain:
            cmd = base_cmd + ["-c:v", "copy", "-af", audio_filter_chain, "-c:a", "aac"]
        else:
            cmd = base_cmd + ["-c", "copy"]
        cmd.append(output_path)
    else:
        # Re-encode video
        v_codec = export_video_codec.lower()
        if v_codec == "copy":
            v_codec = "h264" # fallback
            
        hw_mode = export_hw_accel.lower()
        codec_name = "libx264"
        
        if "nvenc" in hw_mode:
            if v_codec == "h264":
                codec_name = "h264_nvenc"
            elif v_codec == "h265":
                codec_name = "hevc_nvenc"
            else:
                if v_codec == "vp9": codec_name = "libvpx-vp9"
                else: codec_name = "libx264"
        elif "qsv" in hw_mode:
            if v_codec == "h264":
                codec_name = "h264_qsv"
            elif v_codec == "h265":
                codec_name = "hevc_qsv"
            elif v_codec == "vp9":
                codec_name = "vp9_qsv"
            else:
                codec_name = "libx264"
        elif "amf" in hw_mode:
            if v_codec == "h264":
                codec_name = "h264_amf"
            elif v_codec == "h265":
                codec_name = "hevc_amf"
            else:
                if v_codec == "vp9": codec_name = "libvpx-vp9"
                else: codec_name = "libx264"
        else:
            if v_codec == "h264":
                codec_name = "libx264"
            elif v_codec == "h265":
                codec_name = "libx265"
            elif v_codec == "vp9":
                codec_name = "libvpx-vp9"

        # Rate control setup
        rate_control_args = []
        is_auto_bitrate = (export_video_bitrate in ("Auto", "Auto (Match Source)"))
        if not is_auto_bitrate:
            match = re.match(r"(\d+)\s*(?:Mbps|M)?", export_video_bitrate, re.IGNORECASE)
            if match:
                bitrate_val = match.group(1)
                rate_control_args = ["-b:v", f"{bitrate_val}M"]
            else:
                rate_control_args = ["-crf", str(export_video_crf)]
        else:
            if "nvenc" in codec_name:
                rate_control_args = ["-rc", "vbr", "-cq", str(export_video_crf)]
            elif "qsv" in codec_name:
                rate_control_args = ["-global_quality", str(export_video_crf)]
            elif "amf" in codec_name:
                rate_control_args = ["-rc", "cqp", "-qp_i", str(export_video_crf), "-qp_p", str(export_video_crf)]
            else:
                rate_control_args = ["-crf", str(export_video_crf)]
            
        cmd = base_cmd + ["-c:v", codec_name] + rate_control_args
        
        # Add resolution scaling
        v_filters = []
        if export_video_resolution != "original":
            if export_video_resolution == "1080p":
                v_filters.append("scale=-2:1080")
            elif export_video_resolution == "720p":
                v_filters.append("scale=-2:720")
            elif export_video_resolution == "480p":
                v_filters.append("scale=-2:480")
                
        if v_filters:
            cmd += ["-vf", ",".join(v_filters)]
            
        # Add FPS
        if export_video_fps != "original":
            cmd += ["-r", export_video_fps]
            
        # Audio
        if audio_mute:
            cmd += ["-an"]
        else:
            cmd += ["-c:a", "aac"]
            if audio_filter_chain:
                cmd += ["-af", audio_filter_chain]
                
        cmd.append(output_path)

    return cmd


def build_merge_command(
    input_paths: list[str],
    output_path: str,
    concat_file_path: str,
    ffmpeg_path: str,
    has_video: bool = True,
    audio_mute: bool = False,
    audio_filter_chain: str = "",
    audio_extract_only: bool = False,
    audio_extract_format: str = "mp3",
    export_video_codec: str = "copy",
    export_video_resolution: str = "original",
    export_video_fps: str = "original",
    export_video_crf: int = 23,
    export_video_bitrate: str = "Auto",
    export_hw_accel: str = "None (CPU)"
) -> list[str]:
    """Generates the FFmpeg merge command, using concat demuxer if compatible or concat filter if mismatched."""
    is_compatible, target_w, target_h = check_merge_compatibility(input_paths, ffmpeg_path)
    
    # Determine if video re-encoding is forced by settings or compatibility issues
    video_reencode = (
        not is_compatible
        or export_video_codec != "copy"
        or export_video_resolution != "original"
        or export_video_fps != "original"
        or (export_video_bitrate != "Auto" and export_video_bitrate != "Auto (Match Source)")
        or export_hw_accel != "None (CPU)"
    )

    if audio_extract_only:
        # If extracting audio only from multiple mismatched files, check if we need to transcode audio
        if not is_compatible:
            # Decode and concat using filter_complex for audio-only
            filter_complex = ""
            for i in range(len(input_paths)):
                filter_complex += f"[{i}:a]"
            filter_complex += f"concat=n={len(input_paths)}:v=0:a=1[a_out]"
            if audio_filter_chain:
                filter_complex += f"; [a_out]{audio_filter_chain}[af_out]"
                audio_map = "[af_out]"
            else:
                audio_map = "[a_out]"
                
            cmd = [ffmpeg_path, "-y"]
            for path in input_paths:
                cmd += ["-i", path]
            cmd += ["-vn", "-filter_complex", filter_complex, "-map", audio_map]
            
            fmt = audio_extract_format.lower()
            if fmt == "mp3": cmd += ["-c:a", "libmp3lame"]
            elif fmt == "wav": cmd += ["-c:a", "pcm_s16le"]
            elif fmt == "aac": cmd += ["-c:a", "aac"]
            elif fmt == "flac": cmd += ["-c:a", "flac"]
            elif fmt == "ogg": cmd += ["-c:a", "libvorbis"]
            else: cmd += ["-c:a", "aac"]
            
            cmd.append(output_path)
            return cmd
        else:
            # Fast concat audio using demuxer
            # Setup demuxer concat file
            with open(concat_file_path, "w", encoding="utf-8") as concat_file:
                for path in input_paths:
                    escaped_path = path.replace("\\", "/").replace("'", "'\\''")
                    concat_file.write(f"file '{escaped_path}'\n")

            cmd = [
                ffmpeg_path,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file_path,
                "-vn"
            ]
            
            if audio_filter_chain:
                cmd += ["-af", audio_filter_chain]
                
            fmt = audio_extract_format.lower()
            if fmt == "mp3": cmd += ["-c:a", "libmp3lame"]
            elif fmt == "wav": cmd += ["-c:a", "pcm_s16le"]
            elif fmt == "aac": cmd += ["-c:a", "aac"]
            elif fmt == "flac": cmd += ["-c:a", "flac"]
            elif fmt == "ogg": cmd += ["-c:a", "libvorbis"]
            else:
                if audio_filter_chain:
                    cmd += ["-c:a", "aac"]
                else:
                    cmd += ["-c:a", "copy"]
            
            cmd.append(output_path)
            return cmd

    if not video_reencode:
        # 1. FAST CONCAT USING DEMUXER
        with open(concat_file_path, "w", encoding="utf-8") as concat_file:
            for path in input_paths:
                escaped_path = path.replace("\\", "/").replace("'", "'\\''")
                concat_file.write(f"file '{escaped_path}'\n")

        cmd = [
            ffmpeg_path,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file_path
        ]
        
        if audio_mute:
            cmd += ["-c:v", "copy", "-an", output_path]
        elif audio_filter_chain:
            cmd += ["-c:v", "copy", "-af", audio_filter_chain, "-c:a", "aac", output_path]
        else:
            cmd += ["-c", "copy", output_path]
            
        return cmd
    else:
        # 2. CONCAT USING FILTER_COMPLEX (RE-ENCODE)
        # Compute target dimensions
        if export_video_resolution == "1080p":
            W, H = 1920, 1080
        elif export_video_resolution == "720p":
            W, H = 1280, 720
        elif export_video_resolution == "480p":
            W, H = 854, 480
        else:
            W = target_w if target_w % 2 == 0 else target_w + 1
            H = target_h if target_h % 2 == 0 else target_h + 1

        filter_complex = ""
        for i in range(len(input_paths)):
            filter_complex += f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]; "
            
        for i in range(len(input_paths)):
            filter_complex += f"[v{i}][{i}:a]"
            
        filter_complex += f"concat=n={len(input_paths)}:v=1:a=1[v_out][a_out]"
        
        if audio_filter_chain:
            filter_complex += f"; [a_out]{audio_filter_chain}[af_out]"
            audio_map = "[af_out]"
        else:
            audio_map = "[a_out]"

        cmd = [ffmpeg_path, "-y"]
        for path in input_paths:
            cmd += ["-i", path]
            
        cmd += ["-filter_complex", filter_complex, "-map", "[v_out]"]
        
        if audio_mute:
            cmd += ["-an"]
        else:
            cmd += ["-map", audio_map, "-c:a", "aac"]

        # Codec settings
        v_codec = export_video_codec.lower()
        if v_codec == "copy":
            v_codec = "h264" # fallback
            
        hw_mode = export_hw_accel.lower()
        codec_name = "libx264"
        
        if "nvenc" in hw_mode:
            if v_codec == "h264":
                codec_name = "h264_nvenc"
            elif v_codec == "h265":
                codec_name = "hevc_nvenc"
            else:
                if v_codec == "vp9": codec_name = "libvpx-vp9"
                else: codec_name = "libx264"
        elif "qsv" in hw_mode:
            if v_codec == "h264":
                codec_name = "h264_qsv"
            elif v_codec == "h265":
                codec_name = "hevc_qsv"
            elif v_codec == "vp9":
                codec_name = "vp9_qsv"
            else:
                codec_name = "libx264"
        elif "amf" in hw_mode:
            if v_codec == "h264":
                codec_name = "h264_amf"
            elif v_codec == "h265":
                codec_name = "hevc_amf"
            else:
                if v_codec == "vp9": codec_name = "libvpx-vp9"
                else: codec_name = "libx264"
        else:
            if v_codec == "h264":
                codec_name = "libx264"
            elif v_codec == "h265":
                codec_name = "libx265"
            elif v_codec == "vp9":
                codec_name = "libvpx-vp9"

        # Rate control setup
        rate_control_args = []
        is_auto_bitrate = (export_video_bitrate in ("Auto", "Auto (Match Source)"))
        if not is_auto_bitrate:
            match = re.match(r"(\d+)\s*(?:Mbps|M)?", export_video_bitrate, re.IGNORECASE)
            if match:
                bitrate_val = match.group(1)
                rate_control_args = ["-b:v", f"{bitrate_val}M"]
            else:
                rate_control_args = ["-crf", str(export_video_crf)]
        else:
            if "nvenc" in codec_name:
                rate_control_args = ["-rc", "vbr", "-cq", str(export_video_crf)]
            elif "qsv" in codec_name:
                rate_control_args = ["-global_quality", str(export_video_crf)]
            elif "amf" in codec_name:
                rate_control_args = ["-rc", "cqp", "-qp_i", str(export_video_crf), "-qp_p", str(export_video_crf)]
            else:
                rate_control_args = ["-crf", str(export_video_crf)]
        
        cmd += ["-c:v", codec_name] + rate_control_args
        
        if export_video_fps != "original":
            cmd += ["-r", export_video_fps]
            
        cmd.append(output_path)
        return cmd




class FFmpegWorker(QThread):
    progressChanged = pyqtSignal(int)
    statusChanged = pyqtSignal(str)
    finishedSuccessfully = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        command: list[str],
        expected_duration_seconds: float | None = None,
        output_path: str | None = None,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.command = command
        self.expected_duration_seconds = expected_duration_seconds
        self.output_path = output_path

    def run(self) -> None:
        try:
            # Popen to capture stderr line by line
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,  # Unbuffered raw reads
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
        except FileNotFoundError:
            self.failed.emit("FFmpeg executable was not found. Please verify config.py path.")
            return
        except Exception as e:
            self.failed.emit(f"Failed to start FFmpeg: {str(e)}")
            return

        stderr_log = []
        buffer = b""

        # Read stderr output chunk by chunk to parse progress in real-time
        while True:
            chunk = process.stderr.read(256)
            if not chunk:
                break
            buffer += chunk

            # Process lines split by \r (carriage return) or \n
            while b"\r" in buffer or b"\n" in buffer:
                idx_r = buffer.find(b"\r")
                idx_n = buffer.find(b"\n")

                if idx_r != -1 and (idx_n == -1 or idx_r < idx_n):
                    line_bytes = buffer[:idx_r]
                    buffer = buffer[idx_r + 1:]
                else:
                    line_bytes = buffer[:idx_n]
                    buffer = buffer[idx_n + 1:]

                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    stderr_log.append(line)
                    t = parse_ffmpeg_time(line)
                    if t is not None and self.expected_duration_seconds:
                        progress = int((t / self.expected_duration_seconds) * 100)
                        progress = max(0, min(progress, 99))
                        self.progressChanged.emit(progress)

        process.wait()

        if process.returncode == 0:
            self.progressChanged.emit(100)
            self.finishedSuccessfully.emit(self.output_path or "")
        else:
            err_text = "\n".join(stderr_log[-20:])  # Grab last 20 log lines for context
            self.failed.emit(err_text or f"FFmpeg process failed with exit code: {process.returncode}")
