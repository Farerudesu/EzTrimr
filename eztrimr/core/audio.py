import os
import math
import subprocess
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal
from pydub import AudioSegment
import config

# Add ffmpeg directory to PATH so subprocesses can find it
ffmpeg_dir = os.path.dirname(config.FFMPEG_PATH)
if ffmpeg_dir and ffmpeg_dir not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_dir + os.path.pathsep + os.environ["PATH"]

# Set pydub converter path
AudioSegment.converter = config.FFMPEG_PATH


class AudioAnalyser(QThread):
    analysis_done = pyqtSignal(float, float, list)  # peak_dbfs, rms_dbfs, waveform_samples
    analysis_failed = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        temp_wav_path = None
        try:
            # Create a temp WAV file path
            temp_fd, temp_wav_path = tempfile.mkstemp(suffix="_downsampled.wav")
            os.close(temp_fd)

            # Limit analysis to 30 minutes (1800 seconds) in FFmpeg itself
            duration_limit = 1800.0
            
            # Extract downsampled audio (8000Hz, mono)
            cmd = [
                config.FFMPEG_PATH,
                "-y",
                "-i", self.file_path,
                "-vn",
                "-ac", "1",
                "-ar", "8000",
                "-acodec", "pcm_s16le",
                "-to", f"{duration_limit}",
                temp_wav_path
            ]
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
            
            # Now load the downsampled WAV into pydub (blazing fast!)
            audio = AudioSegment.from_wav(temp_wav_path)

            # Compute peak (max_dBFS) and RMS (dBFS) clamped to [-60.0, 0.0]
            peak_dbfs = max(-60.0, min(0.0, audio.max_dBFS))
            rms_dbfs = max(-60.0, min(0.0, audio.dBFS))

            # Compute 300 normalized chunk RMS amplitudes for the waveform view.
            num_samples = 300
            chunk_len = len(audio) / num_samples
            waveform_samples = []
            
            for i in range(num_samples):
                start_ms = int(i * chunk_len)
                end_ms = int((i + 1) * chunk_len)
                chunk = audio[start_ms:end_ms]
                dbfs = max(-60.0, min(0.0, chunk.dBFS))
                # Normalize [-60.0, 0.0] to [0.0, 1.0]
                norm_val = (dbfs + 60.0) / 60.0
                waveform_samples.append(norm_val)

            self.analysis_done.emit(peak_dbfs, rms_dbfs, waveform_samples)
        except Exception as e:
            self.analysis_failed.emit(str(e))
        finally:
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except Exception:
                    pass


class AudioPreviewThread(QThread):
    preview_ready = pyqtSignal(str)  # temp file path
    preview_failed = pyqtSignal(str)

    def __init__(self, file_path: str, seek_sec: float, duration_sec: float, volume_db: float, normalize: bool):
        super().__init__()
        self.file_path = file_path
        self.seek_sec = seek_sec
        self.duration_sec = duration_sec
        self.volume_db = volume_db
        self.normalize = normalize

    def run(self):
        temp_in_path = None
        try:
            start_sec = max(0.0, min(self.seek_sec, self.duration_sec))
            end_sec = min(start_sec + 3.0, self.duration_sec)
            
            if end_sec <= start_sec:
                end_sec = min(self.duration_sec, start_sec + 0.1)

            # Create a temp WAV file path
            temp_fd, temp_in_path = tempfile.mkstemp(suffix=".wav")
            os.close(temp_fd)
            
            # Extract 3 seconds using ffmpeg first (extremely fast compared to loading the whole file)
            cmd = [
                config.FFMPEG_PATH,
                "-y",
                "-ss", f"{start_sec:.3f}",
                "-t", f"{end_sec - start_sec:.3f}",
                "-i", self.file_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                temp_in_path
            ]
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
            
            # Now load the 3-second WAV into pydub
            audio = AudioSegment.from_wav(temp_in_path)
            
            # Apply volume/gain
            if self.volume_db != 0.0:
                audio = audio.apply_gain(self.volume_db)

            # Apply simplified normalization
            if self.normalize:
                target_dbfs = -23.0
                change_in_dbfs = target_dbfs - audio.dBFS
                if not math.isinf(change_in_dbfs) and not math.isnan(change_in_dbfs):
                    change_in_dbfs = max(-30.0, min(30.0, change_in_dbfs))
                    audio = audio.apply_gain(change_in_dbfs)

            # Export to a temp .wav file (blazing fast compared to mp3 subprocess transcoding)
            temp_out_fd, temp_out_path = tempfile.mkstemp(suffix=".wav")
            os.close(temp_out_fd)
            
            audio.export(temp_out_path, format="wav")
            self.preview_ready.emit(temp_out_path)
            
        except Exception as e:
            self.preview_failed.emit(str(e))
        finally:
            if temp_in_path and os.path.exists(temp_in_path):
                try:
                    os.remove(temp_in_path)
                except Exception:
                    pass
