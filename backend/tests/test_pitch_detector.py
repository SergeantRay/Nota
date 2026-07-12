import pytest
from unittest.mock import patch
import numpy as np

from app.pipeline.pitch_detector import (
    _merge_adjacent_notes,
    run_pitch_detection,
    DetectionError,
)


class TestMergeAdjacentNotes:
    def test_merges_same_pitch_within_gap(self):
        notes = [
            {"pitch_midi": 60, "start_sec": 0.0, "end_sec": 0.05, "confidence": 0.5},
            {"pitch_midi": 60, "start_sec": 0.06, "end_sec": 0.10, "confidence": 0.8},
        ]
        merged = _merge_adjacent_notes(notes, gap_ms=80)
        assert len(merged) == 1
        assert merged[0]["end_sec"] == 0.10
        assert merged[0]["confidence"] == 0.8

    def test_keeps_different_pitches_separate(self):
        notes = [
            {"pitch_midi": 60, "start_sec": 0.0, "end_sec": 0.05, "confidence": 0.5},
            {"pitch_midi": 64, "start_sec": 0.06, "end_sec": 0.10, "confidence": 0.8},
        ]
        merged = _merge_adjacent_notes(notes, gap_ms=80)
        assert len(merged) == 2

    def test_empty_list(self):
        assert _merge_adjacent_notes([]) == []


class TestRunPitchDetection:
    def test_detects_pitched_stem(self, tmp_path):
        stem = tmp_path / "bass.wav"
        import soundfile as sf
        y = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 22050))
        sf.write(str(stem), y, 22050)

        output = tmp_path / "output"
        result = run_pitch_detection({"bass": stem}, output)
        assert "bass" in result
        assert len(result["bass"]) > 0
        assert (output / "raw_notes" / "bass.json").exists()

    def test_falls_back_on_import_error(self, tmp_path):
        stem = tmp_path / "test.wav"
        import soundfile as sf
        y = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 22050))
        sf.write(str(stem), y, 22050)

        # The _detect_pitched function catches ImportError internally
        # and falls back to librosa, so we verify the fallback works
        with patch("app.pipeline.pitch_detector._basic_pitch_detect", side_effect=ImportError):
            result = run_pitch_detection({"melody": stem}, tmp_path / "out")
            assert "melody" in result
            assert isinstance(result["melody"], list)


class TestDetectionError:
    def test_wraps_exception(self, tmp_path):
        stem = tmp_path / "fake.wav"
        stem.write_bytes(b"")
        with patch("app.pipeline.pitch_detector._detect_pitched", side_effect=RuntimeError("boom")):
            with pytest.raises(DetectionError, match="Detection failed for bass"):
                run_pitch_detection({"bass": stem}, tmp_path)
