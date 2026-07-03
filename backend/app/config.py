import os
from pathlib import Path


class Settings:
    app_name: str = "Nota"
    debug: bool = True

    # Audio constraints
    max_file_size_bytes: int = 100 * 1024 * 1024  # 100 MB
    min_duration_sec: float = 2.0
    max_duration_sec: float = 30 * 60  # 30 minutes
    target_sample_rate: int = 44100
    allowed_extensions: set[str] = {".wav", ".mp3", ".flac"}

    # Paths
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    uploads_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    sessions_dir: Path = Path(__file__).resolve().parent.parent / "sessions"

    def __init__(self):
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
