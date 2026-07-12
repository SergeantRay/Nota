import json
import shutil
from pathlib import Path

from app.config import settings
from app.models import Session, SessionStatus


def session_dir(session_id: str) -> Path:
    return settings.sessions_dir / session_id


def ensure_session_dir(session_id: str) -> Path:
    p = session_dir(session_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_upload(session: Session, src: Path) -> Path:
    ensure_session_dir(session.id)
    dest = session_dir(session.id) / f"original{suffix(src)}"
    shutil.copy2(src, dest)
    return dest


def write_session(session: Session) -> None:
    ensure_session_dir(session.id)
    path = session_dir(session.id) / "session.json"
    path.write_text(json.dumps(_serialize(session), indent=2))


def read_session(session_id: str) -> Session | None:
    path = session_dir(session_id) / "session.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return _deserialize(data)


def suffix(path: Path) -> str:
    return path.suffix.lower()


def _serialize(s: Session) -> dict:
    return {
        "id": s.id,
        "file_name": s.file_name,
        "original_path": str(s.original_path) if s.original_path else None,
        "duration_sec": s.duration_sec,
        "sample_rate": s.sample_rate,
        "channels": s.channels,
        "status": s.status.value,
        "progress": s.progress,
        "stage": s.stage,
        "error": s.error,
        "stem_paths": s.stem_paths,
    }


def _deserialize(d: dict) -> Session:
    original = d.get("original_path")
    return Session(
        id=d["id"],
        file_name=d.get("file_name", ""),
        original_path=Path(original) if original else None,
        duration_sec=d.get("duration_sec", 0.0),
        sample_rate=d.get("sample_rate", 0),
        channels=d.get("channels", 0),
        status=SessionStatus(d.get("status", "uploaded")),
        progress=d.get("progress", 0.0),
        stage=d.get("stage", ""),
        error=d.get("error"),
        stem_paths=d.get("stem_paths", {}),
    )
