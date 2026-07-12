from enum import Enum
from uuid import uuid4
from dataclasses import dataclass, field
from pathlib import Path

# Our 4 output layers
LAYERS = ("percussion", "bass", "other", "melody")


class SessionStatus(str, Enum):
    UPLOADED = "uploaded"
    PREPROCESSING = "preprocessing"
    SEPARATING = "separating"
    DETECTING = "detecting"
    POSTPROCESSING = "postprocessing"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    file_name: str = ""
    original_path: Path | None = None
    duration_sec: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    status: SessionStatus = SessionStatus.UPLOADED
    progress: float = 0.0
    stage: str = ""
    error: str | None = None
    stem_paths: dict[str, str] = field(default_factory=dict)
    raw_notes: dict[str, list] = field(default_factory=dict)
