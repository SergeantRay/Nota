"""
Pitch / onset detection for separated stems.

- Pitched stems (bass, other, melody): basic-pitch (polyphonic MIDI output)
- Percussion stem: librosa onset detection + frequency-band classification

Output format per note:
    {pitch_midi, start_sec, end_sec, velocity, confidence}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

PITCHED_LAYERS = ("bass", "other", "melody")
PERCUSSION_LAYER = "percussion"


class DetectionError(Exception):
    pass


def run_pitch_detection(
    stem_paths: dict[str, Path],
    output_dir: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict[str, list[dict]]:
    """Run pitch/onset detection on every stem and return layer->notes dict."""

    output_dir = Path(output_dir)

    layer_notes: dict[str, list[dict]] = {}
    entries = [(k, v) for k, v in stem_paths.items() if Path(v).exists()]
    total = max(len(entries), 1)

    for idx, (layer, stem_path) in enumerate(entries):
        pct = 0.30 + 0.55 * (idx / total)
        stage = f"detecting:{layer}"
        _report(on_progress, pct, stage)

        try:
            if layer == PERCUSSION_LAYER:
                notes = _detect_percussion_onsets(Path(stem_path))
            else:
                notes = _detect_pitched(Path(stem_path))
        except Exception as e:
            raise DetectionError(f"Detection failed for {layer}: {e}") from e

        layer_notes[layer] = notes

    # persist raw notes
    raw_dir = output_dir / "raw_notes"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for layer, notes in layer_notes.items():
        (raw_dir / f"{layer}.json").write_text(json.dumps(notes, indent=2))

    _report(on_progress, 0.85, "detecting:done")
    return layer_notes


# ---------------------------------------------------------------------------
# Pitched-stem detection (basic-pitch)
# ---------------------------------------------------------------------------

def _detect_pitched(stem_path: Path) -> list[dict]:
    try:
        return _basic_pitch_detect(stem_path)
    except ImportError:
        return _librosa_pitched_fallback(stem_path)


def _basic_pitch_detect(stem_path: Path) -> list[dict]:
    import tensorflow as tf  # noqa: F401 — silence tf logging if possible
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    model_output, midi_data, note_events = predict(
        str(stem_path),
        model_path=ICASSP_2022_MODEL_PATH,
    )
    return [
        {
            "pitch_midi": int(note[1]),
            "start_sec": round(float(note[3]), 3),
            "end_sec": round(float(note[4]), 3),
            "velocity": int(note[2]),
            "confidence": round(float(note[5]), 3) if len(note) > 5 else 0.5,
        }
        for note in note_events
    ]


def _librosa_pitched_fallback(stem_path: Path) -> list[dict]:
    """Simple monophonic pitch detection via librosa piptrack."""
    import librosa
    import numpy as np

    y, sr = librosa.load(str(stem_path), sr=22050, mono=True)
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)

    notes: list[dict] = []
    note_id = 0
    for t in range(pitches.shape[1]):
        mag_idx = magnitudes[:, t].argmax()
        pitch_hz = pitches[mag_idx, t]
        if pitch_hz <= 0 or magnitudes[mag_idx, t] < 0.3:
            continue
        midi = int(round(librosa.hz_to_midi(pitch_hz)))
        if midi < 21 or midi > 108:
            continue
        start_sec = t * (len(y) / sr) / pitches.shape[1]
        notes.append({
            "pitch_midi": midi,
            "start_sec": round(start_sec, 3),
            "end_sec": round(start_sec + 0.1, 3),
            "velocity": 80,
            "confidence": round(float(magnitudes[mag_idx, t]), 3),
        })
        note_id += 1

    return _merge_adjacent_notes(notes)


def _merge_adjacent_notes(notes: list[dict], gap_ms: int = 80) -> list[dict]:
    """Merge consecutive notes at same pitch that are close in time."""
    if not notes:
        return []
    gap = gap_ms / 1000.0
    merged = [notes[0]]
    for n in notes[1:]:
        prev = merged[-1]
        if (
            n["pitch_midi"] == prev["pitch_midi"]
            and n["start_sec"] - prev["end_sec"] < gap
        ):
            prev["end_sec"] = n["end_sec"]
            prev["confidence"] = max(prev["confidence"], n["confidence"])
        else:
            merged.append(n)
    return merged


# ---------------------------------------------------------------------------
# Percussion detection (onset + frequency-band classifier)
# ---------------------------------------------------------------------------

PERCUSSION_CLASSES = {
    (30, 60): ("kick", 36),
    (60, 90): ("kick_low", 36),
    (150, 350): ("snare", 38),
    (3000, 8000): ("hihat_closed", 42),
    (8000, 15000): ("hihat_open", 46),
    (1000, 3000): ("tom", 45),
}


def _detect_percussion_onsets(stem_path: Path) -> list[dict]:
    import librosa
    import numpy as np

    y, sr = librosa.load(str(stem_path), sr=22050, mono=True)

    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr, units="frames", backtrack=True
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    stft = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)

    notes: list[dict] = []
    for i, onset_sec in enumerate(onset_times):
        frame = onset_frames[i]
        if frame >= stft.shape[1]:
            continue
        spectrum = stft[:, frame]

        best_class = "other"
        best_midi = 36
        best_energy = 0.0

        for (lo, hi), (label, midi) in PERCUSSION_CLASSES.items():
            band = spectrum[(freqs >= lo) & (freqs < hi)]
            energy = float(np.sum(band))
            if energy > best_energy:
                best_energy = energy
                best_class = label
                best_midi = midi

        end_sec = onset_times[i + 1] - 0.01 if i + 1 < len(onset_times) else onset_sec + 0.15
        conf = min(best_energy / (float(np.sum(spectrum)) + 1e-9) * 2, 1.0)

        notes.append({
            "pitch_midi": best_midi,
            "start_sec": round(float(onset_sec), 3),
            "end_sec": round(float(end_sec), 3),
            "velocity": 100,
            "confidence": round(conf, 3),
            "instrument": best_class,
        })

    return notes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report(cb, progress, stage):
    if cb:
        cb(progress, stage)
