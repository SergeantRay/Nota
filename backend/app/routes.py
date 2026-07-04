import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models import Session
from app.storage import save_upload, write_session, read_session
from app.audio import validate_audio, AudioValidationError

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    if file.filename is None:
        raise HTTPException(400, "No filename provided")

    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        info = validate_audio(tmp_path)
    except AudioValidationError as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, str(e))

    session = Session(
        file_name=file.filename,
        duration_sec=info["duration_sec"],
        sample_rate=info["sample_rate"],
        channels=info["channels"],
    )

    session.original_path = save_upload(session, tmp_path)
    write_session(session)
    tmp_path.unlink(missing_ok=True)

    return {
        "session_id": session.id,
        "file_name": session.file_name,
        "duration_sec": session.duration_sec,
        "sample_rate": session.sample_rate,
        "channels": session.channels,
        "status": session.status.value,
    }


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    session = read_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session.id,
        "file_name": session.file_name,
        "duration_sec": session.duration_sec,
        "sample_rate": session.sample_rate,
        "channels": session.channels,
        "status": session.status.value,
        "progress": session.progress,
        "error": session.error,
    }
