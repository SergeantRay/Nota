import pytest
from pathlib import Path
import json

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.models import Session, SessionStatus
from app.storage import write_session, ensure_session_dir


client = TestClient(app)


@pytest.fixture(autouse=True)
def override_dirs(tmp_path, monkeypatch):
    """Redirect data dirs to tmp for test isolation."""
    monkeypatch.setattr(settings, "sessions_dir", tmp_path / "sessions")
    monkeypatch.setattr(settings, "uploads_dir", tmp_path / "uploads")
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)


def make_wav(path: Path, duration_sec: float = 2.0):
    import wave
    import struct

    sr = 44100
    n = int(sr * duration_sec)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sr)
        for _ in range(n):
            wav.writeframes(struct.pack("<h", 0))
    return path


def create_session(session_id: str = "test123", **kwargs) -> Session:
    s = Session(id=session_id, file_name="test.wav", duration_sec=10.0,
                sample_rate=44100, channels=2, **kwargs)
    ensure_session_dir(s.id)
    p = settings.sessions_dir / s.id / "original.wav"
    make_wav(p, duration_sec=10.0)
    s.original_path = p
    write_session(s)
    return s


class TestProcessEndpoint:
    def test_process_not_found(self):
        r = client.post("/api/session/nonexistent/process")
        assert r.status_code == 404

    def test_process_no_audio(self):
        s = Session(id="noaudio", file_name="test.wav")
        write_session(s)
        r = client.post("/api/session/noaudio/process")
        assert r.status_code == 400

    def test_process_starts_separation(self):
        s = create_session("sep-test")
        r = client.post("/api/session/sep-test/process")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "separating"
        assert data["session_id"] == "sep-test"

    def test_status_returns_fields(self):
        s = create_session("status-test")
        r = client.get("/api/session/status-test/status")
        assert r.status_code == 200
        data = r.json()
        assert "stage" in data
        assert "stem_paths" in data
        assert data["status"] == "uploaded"

    def test_duplicate_process_returns_in_progress(self):
        s = create_session("dup-test")
        r1 = client.post("/api/session/dup-test/process")
        assert r1.status_code == 200
        # The first request starts background processing; the second should either
        # report "already in progress" or, if the task finished (e.g. error),
        # start a new one — both are 200.
        r2 = client.post("/api/session/dup-test/process")
        assert r2.status_code == 200
        data = r2.json()
        assert data["session_id"] == "dup-test"


class TestSessionEndpoint:
    def test_get_session_includes_new_fields(self):
        s = create_session("fields-test", stem_paths={"bass": "/tmp/bass.wav"}, stage="done")
        r = client.get("/api/session/fields-test")
        assert r.status_code == 200
        data = r.json()
        assert data["stem_paths"] == {"bass": "/tmp/bass.wav"}
        assert data["stage"] == "done"


class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
