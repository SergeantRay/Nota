from app.models import Session, SessionStatus


def test_session_defaults():
    s = Session()
    assert len(s.id) == 12
    assert s.status == SessionStatus.UPLOADED
    assert s.progress == 0.0
    assert s.error is None
    assert s.stem_paths == {}


def test_session_stem_paths():
    s = Session(stem_paths={"percussion": "/tmp/stems/percussion.wav"})
    assert "percussion" in s.stem_paths
