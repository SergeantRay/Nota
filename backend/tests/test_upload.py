import pytest
from pathlib import Path
from app.audio import validate_audio, AudioValidationError


def test_rejects_unknown_format(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("not audio")
    with pytest.raises(AudioValidationError, match="Unsupported"):
        validate_audio(f)


def test_rejects_empty_file(tmp_path):
    f = tmp_path / "test.wav"
    f.write_bytes(b"")
    with pytest.raises(AudioValidationError):
        validate_audio(f)
