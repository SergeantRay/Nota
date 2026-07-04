from pathlib import Path
import wave
import struct

from app.config import settings


class AudioValidationError(ValueError):
    pass


def _read_wav_info(file_path: Path) -> dict:
    """Read WAV header info without heavy dependencies."""
    try:
        with wave.open(str(file_path), "rb") as wav:
            sr = wav.getframerate()
            channels = wav.getnchannels()
            frames = wav.getnframes()
            sample_width = wav.getsampwidth()
            duration = frames / sr if sr > 0 else 0

            if sr not in (8000, 11025, 16000, 22050, 44100, 48000, 96000):
                pass  # we accept non-standard rates but flag them

            return {
                "duration_sec": round(duration, 2),
                "sample_rate": sr,
                "channels": channels,
                "bit_depth": sample_width * 8,
            }
    except Exception as e:
        raise AudioValidationError(f"Could not read WAV file: {e}")


def validate_audio(file_path: Path) -> dict:
    ext = file_path.suffix.lower()
    if ext not in settings.allowed_extensions:
        raise AudioValidationError(
            f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(settings.allowed_extensions))}"
        )

    file_size = file_path.stat().st_size
    if file_size > settings.max_file_size_bytes:
        raise AudioValidationError(
            f"File too large ({file_size / 1024 / 1024:.1f} MB). Max: {settings.max_file_size_bytes / 1024 / 1024:.0f} MB"
        )

    if file_size == 0:
        raise AudioValidationError("File is empty")

    if ext == ".wav":
        return _read_wav_info(file_path)
    else:
        return _estimate_from_size(file_path, file_size)


def _estimate_from_size(file_path: Path, file_size: int) -> dict:
    """Rough estimate for non-WAV formats until librosa is available."""
    ext = file_path.suffix.lower()
    typical_bitrates = {".mp3": 192000, ".flac": 768000}
    bitrate = typical_bitrates.get(ext, 192000)
    duration = (file_size * 8) / bitrate

    if duration < settings.min_duration_sec:
        raise AudioValidationError(
            f"Audio too short (estimated {duration:.1f}s). Minimum: {settings.min_duration_sec}s"
        )
    if duration > settings.max_duration_sec:
        raise AudioValidationError(
            f"Audio too long (estimated {duration / 60:.1f}min). Maximum: {settings.max_duration_sec / 60:.0f}min"
        )

    return {
        "duration_sec": round(duration, 2),
        "sample_rate": settings.target_sample_rate,
        "channels": 2,
    }
