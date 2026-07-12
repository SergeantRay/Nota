"""
Musical post-processing: tempo detection, key detection, time quantization,
enharmonic spelling, and voice separation.

Input: raw_notes dict (from pitch_detector.py)
Output: quantized_notes dict with musically coherent note data
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np


class PostProcessingError(Exception):
    pass


# Krumhansl-Schmuckler key profiles (major and minor)
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_KEY_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# Enharmonic equivalents for each key (prefer sharps vs flats)
_SHARP_KEYS = {"C", "G", "D", "A", "E", "B", "F#", "C#", "Am", "Em", "Bm", "F#m", "C#m", "G#m"}
_FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm"}

_MAJOR_KEYS = {i: f"{_KEY_NAMES[i]}" for i in range(12)}
_MINOR_KEYS_REL = {i: f"{_KEY_NAMES[(i + 3) % 12]}" for i in range(12)}  # relative minor
_MINOR_KEYS_NAME = {i: f"{_KEY_NAMES[i]}m" for i in range(12)}

DEFAULT_TEMPO = 120
DEFAULT_KEY = "C"


def run_post_processing(
    raw_notes: dict[str, list[dict]],
    output_dir: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict:
    """Clean up raw note data using music theory constraints.

    Returns dict with keys: quantized_notes, tempo, key_signature, time_signature.
    """
    output_dir = Path(output_dir)

    _report(on_progress, 0.87, "postprocessing:starting")

    # Collect all pitched notes for global tempo/key analysis
    all_notes: list[dict] = []
    for layer, notes in raw_notes.items():
        if layer == "percussion":
            continue
        all_notes.extend(notes)

    if not all_notes:
        return _empty_result(output_dir)

    # 1. Tempo detection from inter-onset intervals
    tempo, confidence = _detect_tempo_from_onsets(all_notes)
    _report(on_progress, 0.89, "postprocessing:tempo_detected")

    # 2. Key signature detection
    key_sig, key_confidence = _detect_key(all_notes)
    _report(on_progress, 0.91, "postprocessing:key_detected")

    # 3. Quantize timing per layer
    beat_dur = 60.0 / tempo  # seconds per quarter note
    quantized: dict[str, list[dict]] = {}
    for layer, notes in raw_notes.items():
        if layer == "percussion":
            quantized[layer] = _quantize_percussion(notes, beat_dur)
        else:
            quantized[layer] = _quantize_notes(notes, beat_dur, key_sig)

    _report(on_progress, 0.95, "postprocessing:quantized")

    # 4. Voice separation for overlapping notes within a layer
    for layer in quantized:
        quantized[layer] = _separate_voices(quantized[layer])

    _report(on_progress, 0.97, "postprocessing:voices_separated")

    # Persist
    q_dir = output_dir / "quantized_notes"
    q_dir.mkdir(parents=True, exist_ok=True)
    for layer, notes in quantized.items():
        (q_dir / f"{layer}.json").write_text(json.dumps(notes, indent=2))

    result = {
        "quantized_notes": quantized,
        "tempo": tempo,
        "tempo_confidence": confidence,
        "key_signature": key_sig,
        "key_confidence": key_confidence,
        "time_signature": [4, 4],
    }

    (output_dir / "post_processing.json").write_text(json.dumps(result, indent=2))
    _report(on_progress, 0.99, "postprocessing:complete")

    return result


# ---------------------------------------------------------------------------
# Tempo detection
# ---------------------------------------------------------------------------

def _detect_tempo_from_onsets(notes: list[dict]) -> tuple[int, float]:
    """Estimate BPM from inter-onset intervals (IOIs)."""
    onsets = sorted(n["start_sec"] for n in notes if n.get("confidence", 0) > 0.3)
    if len(onsets) < 4:
        return DEFAULT_TEMPO, 0.1

    iois = np.diff(onsets)
    # Remove very short (<50ms) and very long (>4s) gaps
    iois = iois[(iois > 0.05) & (iois < 4.0)]
    if len(iois) < 3:
        return DEFAULT_TEMPO, 0.1

    # Try candidate tempos from 40-240 BPM and pick one that best explains the IOIs
    best_score = -1
    best_tempo = DEFAULT_TEMPO
    for candidate in range(40, 241):
        beat_sec = 60.0 / candidate
        # For each IOI, compute how well it fits this tempo
        # An IOI of k*beat_sec is a perfect fit
        ratios = iois / beat_sec
        # Quantize each ratio to nearest integer subdivision
        nearest = np.round(ratios)
        # Score: sum of gaussians centered at integers
        errors = np.abs(ratios - nearest)
        score = float(np.sum(np.exp(-errors * errors * 10)))
        if score > best_score:
            best_score = score
            best_tempo = candidate

    # Normalize confidence
    confidence = round(min(best_score / max(len(iois), 1), 1.0), 3)
    return best_tempo, confidence


# ---------------------------------------------------------------------------
# Key detection
# ---------------------------------------------------------------------------

def _detect_key(notes: list[dict]) -> tuple[str, float]:
    """Detect key using Krumhansl-Schmuckler key-finding algorithm."""
    # Build pitch histogram (MIDI pitch → weight)
    histogram = np.zeros(12)
    total_weight = 0.0
    for n in notes:
        midi = n.get("pitch_midi", 60)
        weight = n.get("confidence", 0.5)
        if weight <= 0:
            continue
        histogram[midi % 12] += weight
        total_weight += weight

    if total_weight < 0.5:
        return DEFAULT_KEY, 0.1

    histogram = histogram / (total_weight + 1e-9)

    # Correlate with major and minor profiles
    major_scores = np.array([np.correlate(np.roll(histogram, -i), _MAJOR_PROFILE)[0] for i in range(12)])
    minor_scores = np.array([np.correlate(np.roll(histogram, -i), _MINOR_PROFILE)[0] for i in range(12)])

    major_idx = int(np.argmax(major_scores))
    minor_idx = int(np.argmax(minor_scores))

    if major_scores[major_idx] >= minor_scores[minor_idx]:
        key_name = _MAJOR_KEYS[major_idx]
    else:
        key_name = _MINOR_KEYS_NAME[minor_idx]

    best_score = max(major_scores[major_idx], minor_scores[minor_idx])
    # Scale confidence: typical correlation range is 0.6–1.0
    confidence = round(min(max((best_score - 0.5) / 0.5, 0.0), 1.0), 3)

    return key_name, confidence


# ---------------------------------------------------------------------------
# Time quantization
# ---------------------------------------------------------------------------

def _quantize_notes(notes: list[dict], beat_dur: float, key_sig: str) -> list[dict]:
    """Snap note onsets/offsets to 16th-note grid, assign duration labels."""
    if not notes:
        return []

    sixteenth = beat_dur / 4.0
    quantized: list[dict] = []

    for n in notes:
        conf = n.get("confidence", 0.5)
        if conf < 0.2:
            continue

        onset = _snap(n["start_sec"], sixteenth)
        offset = _snap(n["end_sec"], sixteenth)
        if offset <= onset:
            offset = onset + sixteenth  # minimum 16th note

        dur_beats = (offset - onset) / beat_dur
        dur_label, dots = _beat_duration_to_label(dur_beats)

        midi = n["pitch_midi"]
        accidental = _midi_to_accidental(midi, key_sig)

        quantized.append({
            "pitch_midi": midi,
            "start_beat": round(onset / beat_dur, 4),
            "end_beat": round(offset / beat_dur, 4),
            "duration_beats": round(dur_beats, 4),
            "duration_label": dur_label,
            "dots": dots,
            "accidental": accidental,
            "velocity": n.get("velocity", 80),
            "confidence": conf,
            "voice": 1,
        })

    return sorted(quantized, key=lambda n: (n["start_beat"], n["pitch_midi"]))


def _quantize_percussion(notes: list[dict], beat_dur: float) -> list[dict]:
    """Quantize percussion notes (no key signature concerns)."""
    if not notes:
        return []

    sixteenth = beat_dur / 4.0
    quantized: list[dict] = []

    for n in notes:
        conf = n.get("confidence", 0.5)
        if conf < 0.15:
            continue

        onset = _snap(n["start_sec"], sixteenth)
        dur_label = "quarter" if n.get("instrument", "").startswith("kick") else "eighth"
        dur_beats = 1.0 if dur_label == "quarter" else 0.5

        quantized.append({
            "pitch_midi": n["pitch_midi"],
            "start_beat": round(onset / beat_dur, 4),
            "end_beat": round(onset / beat_dur + dur_beats, 4),
            "duration_beats": dur_beats,
            "duration_label": dur_label,
            "dots": 0,
            "accidental": None,
            "velocity": n.get("velocity", 100),
            "confidence": conf,
            "instrument": n.get("instrument", "other"),
            "voice": 1,
        })

    return sorted(quantized, key=lambda n: n["start_beat"])


def _snap(t: float, grid: float) -> float:
    """Snap time to nearest grid step."""
    return round(round(t / grid) * grid, 6)


def _beat_duration_to_label(beats: float) -> tuple[str, int]:
    """Convert fractional beats to duration label + dots."""
    # Map to standard durations: whole(4), half(2), quarter(1), eighth(0.5), 16th(0.25)
    # Dotted: multiply by 1.5
    beats = abs(beats)
    candidates = [
        (4.0, "whole", 0),
        (3.0, "half", 1),
        (2.0, "half", 0),
        (1.5, "quarter", 1),
        (1.0, "quarter", 0),
        (0.75, "eighth", 1),
        (0.5, "eighth", 0),
        (0.375, "16th", 1),
        (0.25, "16th", 0),
    ]
    best = min(candidates, key=lambda c: abs(c[0] - beats))
    return best[1], best[2]


# ---------------------------------------------------------------------------
# Enharmonic spelling
# ---------------------------------------------------------------------------

def _midi_to_accidental(midi: int, key_sig: str) -> str | None:
    """Determine accidental display for a MIDI pitch in a given key."""
    base_name = _KEY_NAMES[midi % 12]

    # In C major, all naturals — no accidental
    if key_sig in _SHARP_KEYS:
        # Sharp keys: black keys are sharps
        sharps = {1, 3, 6, 8, 10}
        if (midi % 12) in sharps:
            return "#"
    elif key_sig in _FLAT_KEYS:
        # Flat keys: black keys are flats
        flats = {1, 3, 6, 8, 10}
        if (midi % 12) in flats:
            return "b"
    else:
        # Default to sharps for ambiguous keys
        sharps = {1, 3, 6, 8, 10}
        if (midi % 12) in sharps:
            return "#"

    return None


# ---------------------------------------------------------------------------
# Voice separation
# ---------------------------------------------------------------------------

def _separate_voices(notes: list[dict]) -> list[dict]:
    """Assign overlapping notes to voice 1 (up-stem) or voice 2 (down-stem)."""
    if len(notes) < 2:
        return notes

    result = list(notes)
    for i, n1 in enumerate(result):
        if n1.get("voice") and n1["voice"] != 1:
            continue
        for j, n2 in enumerate(result):
            if i >= j:
                continue
            if n2.get("voice") and n2["voice"] != 1:
                continue
            # Check overlap
            if n1["start_beat"] < n2["end_beat"] and n2["start_beat"] < n1["end_beat"]:
                # Overlapping — assign lower pitch to voice 2
                if n1["pitch_midi"] > n2["pitch_midi"]:
                    result[j]["voice"] = 2
                elif n1["pitch_midi"] < n2["pitch_midi"]:
                    result[i]["voice"] = 2

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_result(output_dir: Path) -> dict:
    result = {
        "quantized_notes": {},
        "tempo": DEFAULT_TEMPO,
        "tempo_confidence": 0.0,
        "key_signature": DEFAULT_KEY,
        "key_confidence": 0.0,
        "time_signature": [4, 4],
    }
    output_dir = Path(output_dir)
    (output_dir / "post_processing.json").write_text(json.dumps(result, indent=2))
    return result


def _report(cb, progress, stage):
    if cb:
        cb(progress, stage)
