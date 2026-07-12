import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np


@pytest.fixture
def fake_audio(tmp_path):
    """Create a minimal WAV file for testing."""
    p = tmp_path / "test.wav"
    import wave
    import struct

    sr, duration = 44100, 1
    n = sr * duration
    with wave.open(str(p), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sr)
        for _ in range(n):
            wav.writeframes(struct.pack("<hh", 0, 0))
    return p


class TestSeparationLogic:
    def test_layer_mapping(self):
        from app.pipeline import STEM_TO_LAYER, COMBINED_STEMS, DEMUCS_STEMS

        mapped = set(STEM_TO_LAYER) | set(COMBINED_STEMS)
        assert mapped == set(DEMUCS_STEMS)

        assert STEM_TO_LAYER["drums"] == "percussion"
        assert STEM_TO_LAYER["bass"] == "bass"
        assert STEM_TO_LAYER["vocals"] == "melody"
        assert set(COMBINED_STEMS) == {"piano", "guitar", "other"}

    def test_detect_device(self):
        from app.pipeline import _detect_device

        device = _detect_device()
        assert device in ("cuda", "mps", "cpu")

    def test_check_demucs_available_returns_tuple(self):
        from app.pipeline import check_demucs_available

        available, method = check_demucs_available()
        assert isinstance(available, bool)
        assert isinstance(method, str)


class TestSeparationWithMocks:
    def test_run_via_subprocess_mocked(self, tmp_path, fake_audio):
        import torch
        import torchaudio

        stems_dir = tmp_path / "stems"
        stems_dir.mkdir()

        # Create fake stem WAVs as Demucs would
        wav = torch.zeros(2, 44100)
        for name in ["drums", "bass", "piano", "guitar", "vocals", "other"]:
            torchaudio.save(str(stems_dir / f"{name}.wav"), wav, 44100)

        from app.pipeline import _save_stems

        sources = torch.zeros(6, 2, 44100)
        result = _save_stems(sources, 44100, stems_dir)

        assert set(result.keys()) == {"percussion", "bass", "melody", "other"}
        for layer in result:
            assert result[layer].exists()

    def test_combine_other_stems(self, tmp_path):
        import torch
        import torchaudio

        stems_dir = tmp_path / "stems"
        stems_dir.mkdir()

        sr = 44100
        # Use amplitude < 1/3 so sum stays < 1.0 (int16 WAV clips at ±1.0)
        for name in ["piano", "guitar", "other"]:
            wav = torch.full((2, sr), 0.3)
            torchaudio.save(str(stems_dir / f"{name}.wav"), wav, sr)

        out_dir = tmp_path / "output"
        out_dir.mkdir()

        from app.pipeline import _combine_other_stems

        result = _combine_other_stems(stems_dir, out_dir)
        assert result is not None
        assert result.exists()

        combined, _ = torchaudio.load(str(result))
        val = float(combined.abs().max())
        assert abs(val - 0.9) < 0.1, f"Expected ~0.9, got {val}"


class TestSeparationError:
    def test_separation_error(self):
        from app.pipeline import SeparationError

        e = SeparationError("test")
        assert str(e) == "test"
        assert isinstance(e, Exception)
