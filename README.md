# EZTrimr

A simple, no-nonsense Windows desktop video editor for cut/trim, merge, transcode, and basic audio edits.

## Features

- Fast and lossless video trimming and cutting
- Merge multiple video or audio files together
- Transcode media with hardware acceleration support (Intel QSV, NVIDIA NVENC)
- Extract audio tracks from video files
- Remove audio streams from video files
- Responsive user interface that scales perfectly across 720p, 900p, and 1080p displays
- Portable version and Setup Installer available

## Requirements

- Windows 10/11
- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) on your PATH (`winget install Gyan.FFmpeg`)

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```
