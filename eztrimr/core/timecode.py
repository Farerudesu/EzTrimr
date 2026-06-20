def seconds_to_timecode(seconds: float) -> str:
    """Converts seconds to HH:MM:SS.mmm format."""
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
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def timecode_to_seconds(value: str) -> float:
    """Parses HH:MM:SS, HH:MM:SS.mmm, MM:SS, or SS formats into float seconds.

    Raises ValueError on malformed inputs.
    """
    value = value.strip()
    if not value:
        raise ValueError("Timecode cannot be empty.")

    # Parse milliseconds if present
    parts_ms = value.split(".")
    ms = 0
    if len(parts_ms) == 2:
        ms_str = parts_ms[1]
        if not ms_str.isdigit():
            raise ValueError("Milliseconds must be numeric.")
        # Pad/truncate to 3 digits
        if len(ms_str) > 3:
            ms_str = ms_str[:3]
        else:
            ms_str = ms_str.ljust(3, '0')
        ms = int(ms_str)
        time_part = parts_ms[0]
    elif len(parts_ms) == 1:
        time_part = parts_ms[0]
    else:
        raise ValueError("Invalid timecode format (multiple decimal points).")

    # Parse time segments
    parts = time_part.split(":")
    try:
        if len(parts) == 1:
            s = int(parts[0])
            h, m = 0, 0
        elif len(parts) == 2:
            m = int(parts[0])
            s = int(parts[1])
            h = 0
        elif len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2])
        else:
            raise ValueError("Too many segments separated by colons.")
    except ValueError:
        raise ValueError("Timecode segments must be integers.")

    if h < 0 or m < 0 or s < 0 or m >= 60 or s >= 60:
        raise ValueError("Timecode segments (minutes/seconds) must be between 0 and 59.")

    return h * 3600 + m * 60 + s + ms / 1000.0


def clamp_seconds(value: float, minimum: float, maximum: float) -> float:
    """Clamps a seconds value between a minimum and maximum limit."""
    return max(minimum, min(value, maximum))


def format_duration_short(seconds: float) -> str:
    """Formats seconds into user-facing short format, e.g., '1h 1m 1s' or '1m 1s'."""
    if seconds is None or seconds < 0:
        seconds = 0.0
    total_seconds = int(round(seconds))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60

    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0 or h > 0:
        parts.append(f"{m}m")
    if s > 0 or not parts:
        parts.append(f"{s}s")
    return " ".join(parts)
