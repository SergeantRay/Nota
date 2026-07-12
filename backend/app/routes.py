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
    from app.pipeline.pitch_detector import run_pitch_detection, DetectionError
    from app.pipeline.post_processor import run_post_processing, PostProcessingError
    from app.pipeline.score_assembler import assemble_score, AssemblyError

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

        # Step 1: Source separation
        stem_paths = await asyncio.to_thread(
            run_separation,
            str(session.original_path),
            output_dir,
            on_progress,
        )

        session = read_session(session_id)
        if session:
            session.stem_paths = {k: str(v) for k, v in stem_paths.items()}
            write_session(session)

        # Step 2: Pitch detection
        on_progress(0.90, "detecting:starting")
        session = read_session(session_id)
        if session:
            session.status = SessionStatus.DETECTING
            write_session(session)

        raw_notes = await asyncio.to_thread(
            run_pitch_detection,
            stem_paths,
            output_dir,
            on_progress,
        )

        session = read_session(session_id)
        if session:
            session.status = SessionStatus.COMPLETE
            session.progress = 1.0
            session.stage = "detecting:complete"
            session.raw_notes = raw_notes
            write_session(session)

        # Step 3: Post-processing
        on_progress(0.995, "postprocessing:starting")
        session = read_session(session_id)
        if session:
            session.status = SessionStatus.POSTPROCESSING
            write_session(session)

        pp_result = await asyncio.to_thread(
            run_post_processing,
            raw_notes,
            output_dir,
            on_progress,
        )

        session = read_session(session_id)
        if session:
            session.status = SessionStatus.COMPLETE
            session.progress = 1.0
            session.stage = "postprocessing:complete"
            session.quantized_notes = pp_result.get("quantized_notes", {})
            session.tempo = pp_result.get("tempo", 120)
            session.key_signature = pp_result.get("key_signature", "C")
            write_session(session)

        # Step 4: Score assembly
        on_progress(1.0, "assembling:starting")
        session = read_session(session_id)
        if session:
            session.status = SessionStatus.ASSEMBLING
            write_session(session)

        asm_result = await asyncio.to_thread(
            assemble_score,
            session.quantized_notes,
            session.tempo,
            session.key_signature,
            output_dir,
            on_progress,
        )

        session = read_session(session_id)
        if session:
            session.status = SessionStatus.COMPLETE
            session.progress = 1.0
            session.stage = "assembling:complete"
            session.musicxml_path = asm_result.get("musicxml_path", "")
            session.score_json = asm_result.get("score_data")
            write_session(session)

    except SeparationError as e:
        session = read_session(session_id)
        if session:
            session.status = SessionStatus.ERROR
            session.error = str(e)
            write_session(session)
    except DetectionError as e:
        session = read_session(session_id)
        if session:
            session.status = SessionStatus.ERROR
            session.error = str(e)
            write_session(session)
    except PostProcessingError as e:
        session = read_session(session_id)
        if session:
            session.status = SessionStatus.ERROR
            session.error = str(e)
            write_session(session)
    except AssemblyError as e:
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
        "raw_notes": session.raw_notes,
        "tempo": session.tempo,
        "key_signature": session.key_signature,
        "score_json": session.score_json,
    }
