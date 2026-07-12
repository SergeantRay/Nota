import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from app.config import settings
from app.models import Session, SessionStatus
from app.storage import save_upload, write_session, read_session, ensure_session_dir, session_dir
from app.audio import validate_audio, AudioValidationError

router = APIRouter(prefix="/api", tags=["api"])

# In-memory registry of active background tasks for status polling
_active_tasks: dict[str, asyncio.Task] = {}


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
    return _session_response(session)


@router.post("/session/{session_id}/process")
async def process_session(session_id: str, background_tasks: BackgroundTasks):
    session = read_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    if session.original_path is None:
        raise HTTPException(400, "No audio file uploaded for this session")

    if session_id in _active_tasks and not _active_tasks[session_id].done():
        return {
            "session_id": session_id,
            "status": session.status.value,
            "message": "Processing already in progress",
        }

    session.status = SessionStatus.SEPARATING
    session.progress = 0.0
    session.stage = "separating:starting"
    session.error = None
    write_session(session)

    task = asyncio.create_task(_run_separation_task(session_id))
    _active_tasks[session_id] = task

    return {
        "session_id": session_id,
        "status": "separating",
        "message": "Source separation started",
    }


@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    session = read_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return _session_response(session)


async def _run_separation_task(session_id: str):
    from app.pipeline import run_separation, SeparationError

    session = read_session(session_id)
    if session is None or session.original_path is None:
        return

    def on_progress(progress: float, stage: str):
        s = read_session(session_id)
        if s:
            s.progress = progress
            s.stage = stage
            write_session(s)

    try:
        output_dir = ensure_session_dir(session_id)
        stem_paths = await asyncio.to_thread(
            run_separation,
            str(session.original_path),
            output_dir,
            on_progress,
        )

        session = read_session(session_id)
        if session:
            session.status = SessionStatus.COMPLETE
            session.progress = 1.0
            session.stage = "separating:complete"
            session.stem_paths = {k: str(v) for k, v in stem_paths.items()}
            write_session(session)
    except SeparationError as e:
        session = read_session(session_id)
        if session:
            session.status = SessionStatus.ERROR
            session.error = str(e)
            write_session(session)


def _session_response(session: Session) -> dict:
    return {
        "session_id": session.id,
        "file_name": session.file_name,
        "duration_sec": session.duration_sec,
        "sample_rate": session.sample_rate,
        "channels": session.channels,
        "status": session.status.value,
        "progress": session.progress,
        "stage": session.stage,
        "error": session.error,
        "stem_paths": session.stem_paths,
    }
