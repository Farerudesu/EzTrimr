from fractions import Fraction


def format_timecode(seconds: float) -> str:
    """Returns 'H:MM:SS' format, e.g., 154.3 -> '0:02:34'."""
    if seconds is None or seconds < 0:
        seconds = 0.0
    total_seconds = int(seconds)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


def format_duration_ms(seconds: float) -> str:
    """Returns 'H:MM:SS.mmm' format, e.g., 154.312 -> '0:02:34.312'."""
    if seconds is None or seconds < 0:
        seconds = 0.0
    total_seconds = int(seconds)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    ms = int(round((seconds - total_seconds) * 1000))
    if ms >= 1000:
        total_seconds += 1
        ms -= 1000
        # Recompute h, m, s
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
    return f"{h}:{m:02d}:{s:02d}.{ms:03d}"


def format_file_size(size_bytes: int) -> str:
    """Returns 'X KB', 'X.X MB', or 'X.XX GB'."""
    if size_bytes is None or size_bytes < 0:
        size_bytes = 0
    kb = size_bytes / 1024
    mb = kb / 1024
    gb = mb / 1024

    if mb < 1.0:
        return f"{int(round(kb))} KB"
    elif gb < 1.0:
        return f"{mb:.1f} MB"
    else:
        return f"{gb:.2f} GB"


def parse_fps(r_frame_rate: str) -> float:
    """Safely parses a frame rate string using Fraction and returns a float rounded to 3 decimal places."""
    if not r_frame_rate:
        return 0.0
    try:
        frac = Fraction(r_frame_rate)
        return round(float(frac), 3)
    except Exception:
        return 0.0


def codec_display_name(codec: str) -> str:
    """Maps codec strings to human-readable names or returns upper-cased fallback."""
    if not codec:
        return ""
    mapping = {
        "h264": "H.264",
        "hevc": "H.265",
        "vp9": "VP9",
        "av1": "AV1",
        "mpeg4": "MPEG-4"
    }
    return mapping.get(codec.lower(), codec.upper())
