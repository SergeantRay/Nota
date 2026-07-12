"""
Score assembly: build a music21 Score from quantized notes and export MusicXML + JSON.

Uses music21 for correct notation handling (clefs, key/time signatures, accidentals,
stem directions, beaming, rests, percussion mapping).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from music21 import clef, duration, instrument, key, meter, note, stream, tempo


class AssemblyError(Exception):
    pass


# Layer → clef + instrument mapping
STAFF_CONFIG = {
    "percussion": {
        "clef": "percussion",
        "instrument_name": "Drums",
        "midi_program": 0,
    },
    "bass": {
        "clef": "bass",
        "instrument_name": "Bass",
        "midi_program": 34,
    },
    "other": {
        "clef": "treble",
        "instrument_name": "Tenor / Alto",
        "midi_program": 53,
    },
    "melody": {
        "clef": "treble",
        "instrument_name": "Melody",
        "midi_program": 80,
    },
}


def assemble_score(
    quantized_notes: dict[str, list[dict]],
    tempo_bpm: int,
    key_signature: str,
    output_dir: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict:
    """Build a music21 Score, export MusicXML, and return JSON data for the frontend."""
    output_dir = Path(output_dir)

    _report(on_progress, 0.99, "assembling:building_score")

    score = stream.Score()

    for layer in ["percussion", "bass", "other", "melody"]:
        notes = quantized_notes.get(layer, [])
        part = _build_part(layer, notes, tempo_bpm, key_signature)
        score.append(part)

    # Export MusicXML
    mxml_path = output_dir / "score.musicxml"
    score.write("musicxml", str(mxml_path))
    _report(on_progress, 0.995, "assembling:musicxml_exported")

    # Export JSON for frontend
    json_data = _export_json(quantized_notes, tempo_bpm, key_signature)
    json_path = output_dir / "score.json"
    json_path.write_text(json.dumps(json_data, indent=2))
    _report(on_progress, 1.0, "assembling:complete")

    return {
        "musicxml_path": str(mxml_path),
        "json_path": str(json_path),
        "score_data": json_data,
    }


def _build_part(
    layer: str,
    notes: list[dict],
    tempo_bpm: int,
    key_signature: str,
) -> stream.Part:
    config = STAFF_CONFIG[layer]
    p = stream.Part()

    p.append(tempo.MetronomeMark(number=tempo_bpm))

    ks = key.Key(key_signature)
    p.append(ks)

    p.append(meter.TimeSignature("4/4"))

    if layer == "percussion":
        p.append(clef.PercussionClef())
    elif config["clef"] == "bass":
        p.append(clef.BassClef())
    else:
        p.append(clef.TrebleClef())

    if not notes:
        # Add rests to fill space
        r = note.Rest()
        r.duration = duration.Duration("whole")
        p.append(r)
        return p

    # Group notes by voice
    voice_1_notes = [n for n in notes if n.get("voice", 1) == 1]
    voice_2_notes = [n for n in notes if n.get("voice", 1) == 2]

    voice_1_stream = _notes_to_stream(voice_1_notes, layer)
    p.append(voice_1_stream)

    if voice_2_notes:
        voice_2_stream = _notes_to_stream(voice_2_notes, layer)
        p.append(voice_2_stream)

    return p


def _notes_to_stream(
    notes: list[dict],
    layer: str,
) -> stream.Voice:
    v = stream.Voice()
    for n in notes:
        if layer == "percussion":
            nn = note.Unpitched()
        elif n.get("accidental") == "#":
            nn = note.Note(n["pitch_midi"])
            nn.pitch.accidental = "#"
        elif n.get("accidental") == "b":
            nn = note.Note(n["pitch_midi"])
            nn.pitch.accidental = "-"
        else:
            nn = note.Note(n["pitch_midi"])

        dur_label = n.get("duration_label", "quarter")
        dots = n.get("dots", 0)
        dur = duration.Duration(dur_label)
        dur.dots = dots
        nn.duration = dur

        v.append(nn)
    return v


def _export_json(
    quantized_notes: dict[str, list[dict]],
    tempo_bpm: int,
    key_signature: str,
) -> dict:
    """Convert quantized notes to frontend-friendly JSON matching the architecture doc schema."""
    layers: dict[str, dict] = {}

    for layer_id in ["percussion", "bass", "other", "melody"]:
        config = STAFF_CONFIG[layer_id]
        notes = quantized_notes.get(layer_id, [])

        layer_notes = []
        for n in notes:
            layer_notes.append({
                "pitch": n.get("pitch_midi", 60),
                "startTime": round(n.get("start_beat", 0) * (60.0 / tempo_bpm), 3),
                "endTime": round(n.get("end_beat", 0) * (60.0 / tempo_bpm), 3),
                "velocity": n.get("velocity", 80),
                "duration": n.get("duration_label", "quarter"),
                "dots": n.get("dots", 0),
                "accidental": n.get("accidental"),
                "voice": n.get("voice", 1),
                "instrument": n.get("instrument"),
            })

        layers[layer_id] = {
            "notes": layer_notes,
            "midiProgram": config["midi_program"],
            "clef": config["clef"],
            "instrumentName": config["instrument_name"],
        }

    return {
        "tempo": tempo_bpm,
        "timeSignature": [4, 4],
        "keySignature": key_signature,
        "layers": layers,
    }


def _report(cb, progress, stage):
    if cb:
        cb(progress, stage)
