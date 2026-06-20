from dataclasses import dataclass, field
from enum import Enum
from PyQt6.QtCore import QSettings
from eztrimr.core import utils


class PreviewState(Enum):
    EMPTY = "empty"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"
    AUDIO = "audio"


@dataclass
class AppState:
    # Phase 4 new fields
    loaded_file_path: str | None = None
    probe_data: dict = field(default_factory=dict)
    duration_seconds: float = 0.0
    in_point_seconds: float = 0.0
    out_point_seconds: float = 0.0
    playhead_seconds: float = 0.0
    preview_state: PreviewState = PreviewState.EMPTY
    is_dirty: bool = False
    merge_files: list[str] = field(default_factory=list)
    live_scrub_preview: bool = False

    # Phase 5 audio fields
    peak_dbfs: float = 0.0
    rms_dbfs: float = 0.0
    waveform_samples: list[float] = field(default_factory=list)
    audio_volume_db: float = 0.0
    audio_normalize: bool = False
    audio_mute: bool = False
    audio_extract_only: bool = False
    audio_extract_format: str = "mp3"
    show_waveform: bool = False

    # Phase 6 video fields
    export_video_format: str = "mp4"
    export_video_codec: str = "copy"
    export_video_crf: int = 23
    export_video_resolution: str = "original"
    export_video_fps: str = "original"
    export_video_bitrate: str = "Auto"
    export_hw_accel: str = "None (CPU)"
    last_trim_in: float | None = None
    last_trim_out: float | None = None

    # Previous fields to preserve
    file_size_bytes: int = 0
    has_video: bool = False
    video_codec: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    audio_codec: str = ""
    sample_rate: int = 0
    channels: int = 0
    audio_bitrate_kbps: int = 0
    thumbnail_path: str = ""
    is_loaded: bool = False

    def __post_init__(self) -> None:
        # Load live_scrub_preview from QSettings
        settings = QSettings("EZTrimr", "EZTrimr")
        val = settings.value("preview/live_scrub", False)
        if isinstance(val, str):
            self.live_scrub_preview = (val.lower() == "true")
        elif val is not None:
            try:
                self.live_scrub_preview = bool(int(val))
            except (ValueError, TypeError):
                self.live_scrub_preview = bool(val)
        else:
            self.live_scrub_preview = False

        # Load show_waveform from QSettings
        val_wf = settings.value("preview/show_waveform", False)
        if isinstance(val_wf, str):
            self.show_waveform = (val_wf.lower() == "true")
        elif val_wf is not None:
            try:
                self.show_waveform = bool(int(val_wf))
            except (ValueError, TypeError):
                self.show_waveform = bool(val_wf)
        else:
            self.show_waveform = False

        # Load video bitrate and hw acceleration from QSettings
        val_br = settings.value("advanced/video_bitrate", "Auto")
        self.export_video_bitrate = str(val_br)

        val_hw = settings.value("advanced/hw_accel", "None (CPU)")
        self.export_hw_accel = str(val_hw)

    @property
    def audio_filter_chain(self) -> str:
        """Formats FFmpeg volume/loudnorm filters. Mute returns \"\"."""
        if self.audio_mute:
            return ""
        filters = []
        if self.audio_volume_db != 0.0:
            filters.append(f"volume={self.audio_volume_db}dB")
        if self.audio_normalize:
            filters.append("loudnorm=I=-23:TP=-1:LRA=11:print_format=none")
        return ",".join(filters)

    @property
    def video_requires_reencode(self) -> bool:
        """Returns True if any video setting differs from original/copy."""
        return (
            self.export_video_codec != "copy"
            or self.export_video_resolution != "original"
            or self.export_video_fps != "original"
        )

    # Backwards compatibility properties
    @property
    def file_path(self) -> str:
        return self.loaded_file_path or ""

    @file_path.setter
    def file_path(self, val: str) -> None:
        self.loaded_file_path = val

    @property
    def file_name(self) -> str:
        import os
        return os.path.basename(self.loaded_file_path) if self.loaded_file_path else ""

    @property
    def duration_sec(self) -> float:
        return self.duration_seconds

    @duration_sec.setter
    def duration_sec(self, val: float) -> None:
        self.duration_seconds = val

    @property
    def trim_in(self) -> float:
        return self.in_point_seconds

    @trim_in.setter
    def trim_in(self, val: float) -> None:
        self.in_point_seconds = val

    @property
    def trim_out(self) -> float:
        return self.out_point_seconds

    @trim_out.setter
    def trim_out(self, val: float) -> None:
        self.out_point_seconds = val

    # Helper Methods
    def reset(self) -> 'AppState':
        """Compatibility reset method."""
        self.reset_media_state()
        self.clear_merge_files()
        self.audio_volume_db = 0.0
        self.audio_normalize = False
        self.audio_mute = False
        self.audio_extract_only = False
        self.audio_extract_format = "mp3"
        self.export_video_format = "mp4"
        self.export_video_codec = "copy"
        self.export_video_crf = 23
        self.export_video_resolution = "original"
        self.export_video_fps = "original"
        self.export_video_bitrate = "Auto"
        self.export_hw_accel = "None (CPU)"
        return self

    def reset_media_state(self) -> None:
        self.loaded_file_path = None
        self.probe_data = {}
        self.duration_seconds = 0.0
        self.in_point_seconds = 0.0
        self.out_point_seconds = 0.0
        self.playhead_seconds = 0.0
        self.preview_state = PreviewState.EMPTY
        self.is_dirty = False
        self.last_trim_in = None
        self.last_trim_out = None
        
        # Reset audio analysis results
        self.peak_dbfs = 0.0
        self.rms_dbfs = 0.0
        self.waveform_samples = []

        # Reset previous fields
        self.file_size_bytes = 0
        self.has_video = False
        self.video_codec = ""
        self.width = 0
        self.height = 0
        self.fps = 0.0
        self.has_audio = False
        self.audio_codec = ""
        self.sample_rate = 0
        self.channels = 0
        self.audio_bitrate_kbps = 0
        self.thumbnail_path = ""
        self.is_loaded = False

    def set_loaded_media(self, path: str, probe_data: dict, duration: float) -> None:
        self.loaded_file_path = path
        self.probe_data = probe_data
        self.duration_seconds = duration
        self.in_point_seconds = 0.0
        self.out_point_seconds = duration
        self.playhead_seconds = 0.0
        self.preview_state = PreviewState.LOADED
        self.is_dirty = False
        self.is_loaded = True

    def set_trim_points(self, in_point: float, out_point: float) -> None:
        # Clamp values
        in_point = max(0.0, min(in_point, self.duration_seconds))
        out_point = max(0.0, min(out_point, self.duration_seconds))
        
        # Ensure in_point < out_point
        if in_point >= out_point:
            if in_point == self.duration_seconds:
                in_point = max(0.0, out_point - 0.001)
            else:
                out_point = min(self.duration_seconds, in_point + 0.001)

        self.in_point_seconds = in_point
        self.out_point_seconds = out_point
        self.is_dirty = True

    def set_playhead(self, seconds: float) -> None:
        self.playhead_seconds = max(0.0, min(seconds, self.duration_seconds))

    def add_merge_file(self, path: str) -> None:
        if path not in self.merge_files:
            self.merge_files.append(path)
            self.is_dirty = True

    def remove_merge_file(self, path: str) -> None:
        if path in self.merge_files:
            self.merge_files.remove(path)
            self.is_dirty = True

    def clear_merge_files(self) -> None:
        self.merge_files.clear()
        self.is_dirty = True

    def formatted_duration(self) -> str:
        """Returns the duration formatted as 'H:MM:SS.mmm'."""
        return utils.format_duration_ms(self.duration_seconds)

    def formatted_size(self) -> str:
        """Returns the file size formatted as 'X.X MB' or 'X.XX GB'."""
        return utils.format_file_size(self.file_size_bytes)

    def resolution_str(self) -> str:
        """Returns 'width × height @ fps fps' or 'Audio only'."""
        if self.has_video:
            return f"{self.width} × {self.height} @ {self.fps} fps"
        return "Audio only"


# Global application state instance
app_state = AppState()
