import pytest
import numpy as np
from unittest.mock import patch

from app.pipeline.post_processor import (
    run_post_processing,
    _detect_tempo_from_onsets,
    _detect_key,
    _quantize_notes,
    _snap,
    _beat_duration_to_label,
    _midi_to_accidental,
    _separate_voices,
    DEFAULT_TEMPO,
    DEFAULT_KEY,
)


class TestTempoDetection:
    def test_returns_default_with_few_notes(self):
        tempo, conf = _detect_tempo_from_onsets([])
        assert tempo == DEFAULT_TEMPO
        assert conf == 0.1

    def test_detects_120_bpm(self):
        notes = []
        for beat in range(32):
            notes.append({"start_sec": beat * 0.5, "confidence": 0.9})
        tempo, conf = _detect_tempo_from_onsets(notes)
        assert 100 <= tempo <= 150


class TestKeyDetection:
    def test_returns_default_with_no_notes(self):
        key, conf = _detect_key([])
        assert key == DEFAULT_KEY

    def test_detects_c_major(self):
        c_major_pitches = [60, 62, 64, 65, 67, 69, 71, 72]  # C D E F G A B C
        notes = [{"pitch_midi": p, "confidence": 0.9} for p in c_major_pitches * 4]
        key, conf = _detect_key(notes)
        assert key == "C"


class TestQuantization:
    def test_snaps_to_grid(self):
        assert _snap(0.0, 0.125) == 0.0
        assert _snap(0.13, 0.125) == 0.125
        assert _snap(0.24, 0.125) == 0.25

    def test_beat_duration_labels(self):
        assert _beat_duration_to_label(1.0) == ("quarter", 0)
        assert _beat_duration_to_label(0.5) == ("eighth", 0)
        assert _beat_duration_to_label(2.0) == ("half", 0)
        assert _beat_duration_to_label(0.25) == ("16th", 0)
        assert _beat_duration_to_label(1.5) == ("quarter", 1)

    def test_quantize_notes_assigns_labels(self):
        notes = [
            {"pitch_midi": 60, "start_sec": 0.0, "end_sec": 0.48, "confidence": 0.9, "velocity": 80},
            {"pitch_midi": 64, "start_sec": 0.5, "end_sec": 1.0, "confidence": 0.9, "velocity": 80},
        ]
        result = _quantize_notes(notes, beat_dur=0.5, key_sig="C")
        assert len(result) == 2
        assert result[0]["duration_label"] in ("quarter", "eighth")
        assert result[0]["accidental"] is None

    def test_filters_low_confidence(self):
        notes = [
            {"pitch_midi": 60, "start_sec": 0.0, "end_sec": 0.5, "confidence": 0.1, "velocity": 80},
            {"pitch_midi": 64, "start_sec": 0.0, "end_sec": 0.5, "confidence": 0.9, "velocity": 80},
        ]
        result = _quantize_notes(notes, beat_dur=0.5, key_sig="C")
        assert len(result) == 1
        assert result[0]["pitch_midi"] == 64


class TestAccidentals:
    def test_c_major_all_natural(self):
        for midi in [60, 62, 64, 65, 67, 69, 71, 72]:
            assert _midi_to_accidental(midi, "C") is None

    def test_c_sharp_in_c_major_is_sharp(self):
        assert _midi_to_accidental(61, "C") == "#"

    def test_e_flat_in_f_major_is_flat(self):
        assert _midi_to_accidental(63, "F") == "b"


class TestVoiceSeparation:
    def test_no_overlap_single_voice(self):
        notes = [
            {"pitch_midi": 60, "start_beat": 0, "end_beat": 1, "voice": 1},
            {"pitch_midi": 64, "start_beat": 1, "end_beat": 2, "voice": 1},
        ]
        result = _separate_voices(notes)
        assert all(n["voice"] == 1 for n in result)

    def test_overlap_splits_voices(self):
        notes = [
            {"pitch_midi": 60, "start_beat": 0, "end_beat": 1, "voice": 1},
            {"pitch_midi": 72, "start_beat": 0, "end_beat": 1, "voice": 1},
        ]
        result = _separate_voices(notes)
        voices = {n["pitch_midi"]: n["voice"] for n in result}
        # lower pitch gets voice 2
        assert voices[60] == 2
        assert voices[72] == 1


class TestRunPostProcessing:
    def test_empty_raw_notes(self, tmp_path):
        result = run_post_processing({}, tmp_path)
        assert result["tempo"] == DEFAULT_TEMPO
        assert result["key_signature"] == DEFAULT_KEY
        assert result["quantized_notes"] == {}

    def test_full_flow(self, tmp_path):
        notes = []
        for beat in range(16):
            notes.append({
                "pitch_midi": 67 if beat % 2 == 0 else 64,
                "start_sec": beat * 0.5,
                "end_sec": (beat + 1) * 0.5,
                "confidence": 0.8,
                "velocity": 80,
            })
        raw = {"bass": notes, "percussion": []}
        result = run_post_processing(raw, tmp_path)
        assert "quantized_notes" in result
        assert 40 <= result["tempo"] <= 240
        assert result["key_signature"] is not None
        assert result["time_signature"] == [4, 4]
