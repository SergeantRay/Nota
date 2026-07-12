import json
import pytest
from pathlib import Path
from unittest.mock import patch

from app.pipeline.score_assembler import (
    assemble_score,
    AssemblyError,
    STAFF_CONFIG,
    _build_part,
    _export_json,
    _notes_to_stream,
)


class TestStaffConfig:
    def test_all_layers_have_config(self):
        for layer in ["percussion", "bass", "other", "melody"]:
            assert layer in STAFF_CONFIG
            assert "clef" in STAFF_CONFIG[layer]
            assert "midi_program" in STAFF_CONFIG[layer]

    def test_percussion_uses_percussion_clef(self):
        assert STAFF_CONFIG["percussion"]["clef"] == "percussion"


class TestExportJson:
    def test_empty_notes_produces_structure(self):
        result = _export_json({}, 120, "C")
        assert result["tempo"] == 120
        assert result["timeSignature"] == [4, 4]
        assert result["keySignature"] == "C"
        assert set(result["layers"].keys()) == {"percussion", "bass", "other", "melody"}
        for layer_id, layer_data in result["layers"].items():
            assert layer_data["notes"] == []
            assert layer_data["clef"] == STAFF_CONFIG[layer_id]["clef"]

    def test_converts_beat_times_to_seconds(self):
        notes = [
            {
                "pitch_midi": 60,
                "start_beat": 0.0,
                "end_beat": 1.0,
                "velocity": 80,
                "duration_label": "quarter",
                "dots": 0,
                "voice": 1,
                "accidental": None,
            }
        ]
        result = _export_json({"bass": notes}, 120, "C")
        bass_notes = result["layers"]["bass"]["notes"]
        assert len(bass_notes) == 1
        assert bass_notes[0]["startTime"] == pytest.approx(0.0)
        assert bass_notes[0]["endTime"] == pytest.approx(0.5)  # 1 beat at 120 BPM = 0.5s

    def test_preserves_accidental(self):
        notes = [
            {
                "pitch_midi": 61,
                "start_beat": 0.0,
                "end_beat": 0.5,
                "velocity": 80,
                "duration_label": "eighth",
                "dots": 0,
                "voice": 1,
                "accidental": "#",
            }
        ]
        result = _export_json({"melody": notes}, 100, "C")
        melody_note = result["layers"]["melody"]["notes"][0]
        assert melody_note["accidental"] == "#"


class TestAssembleScore:
    def test_produces_musicxml_and_json(self, tmp_path):
        quantized = {
            "bass": [
                {
                    "pitch_midi": 60,
                    "start_beat": 0.0,
                    "end_beat": 1.0,
                    "velocity": 80,
                    "duration_label": "quarter",
                    "dots": 0,
                    "voice": 1,
                    "accidental": None,
                },
                {
                    "pitch_midi": 64,
                    "start_beat": 1.0,
                    "end_beat": 2.0,
                    "velocity": 80,
                    "duration_label": "quarter",
                    "dots": 0,
                    "voice": 1,
                    "accidental": None,
                },
            ]
        }
        result = assemble_score(quantized, 120, "C", tmp_path)

        mxml_path = Path(result["musicxml_path"])
        assert mxml_path.exists()
        assert mxml_path.suffix == ".musicxml"
        assert mxml_path.read_text() != ""

        json_path = Path(result["json_path"])
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["tempo"] == 120
        assert len(data["layers"]["bass"]["notes"]) == 2

    def test_empty_layers_produce_rests(self, tmp_path):
        result = assemble_score({}, 120, "C", tmp_path)
        mxml_path = Path(result["musicxml_path"])
        assert mxml_path.exists()
        # Should still produce valid MusicXML
        content = mxml_path.read_text()
        assert "<rest>" in content or "<rest " in content or "Rest" in content

    def test_handles_percussion_with_unpitched(self, tmp_path):
        quantized = {
            "percussion": [
                {
                    "pitch_midi": 36,
                    "start_beat": 0.0,
                    "end_beat": 0.5,
                    "velocity": 100,
                    "duration_label": "eighth",
                    "dots": 0,
                    "voice": 1,
                    "accidental": None,
                    "instrument": "kick",
                }
            ]
        }
        result = assemble_score(quantized, 120, "C", tmp_path)
        mxml_path = Path(result["musicxml_path"])
        content = mxml_path.read_text()
        assert "unpitched" in content.lower()

    def test_dotted_notes(self, tmp_path):
        quantized = {
            "melody": [
                {
                    "pitch_midi": 72,
                    "start_beat": 0.0,
                    "end_beat": 1.5,
                    "velocity": 80,
                    "duration_label": "quarter",
                    "dots": 1,
                    "voice": 1,
                    "accidental": None,
                }
            ]
        }
        result = assemble_score(quantized, 120, "C", tmp_path)
        json_data = result["score_data"]
        note = json_data["layers"]["melody"]["notes"][0]
        assert note["dots"] == 1
        assert note["duration"] == "quarter"

    def test_reports_progress(self, tmp_path):
        stages = []

        def cb(progress, stage):
            stages.append((progress, stage))

        quantized = {"bass": []}
        assemble_score(quantized, 120, "C", tmp_path, on_progress=cb)

        assert len(stages) >= 2
        stage_names = [s for _, s in stages]
        assert "assembling:building_score" in stage_names
        assert "assembling:complete" in stage_names
