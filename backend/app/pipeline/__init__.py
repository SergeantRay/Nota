from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from app.config import settings

# Demucs 4-source model stem names (default htdemucs)
DEMUCS_STEMS = ["drums", "bass", "other", "vocals"]

# Map Demucs stems to our layers
STEM_TO_LAYER: dict[str, str] = {
    "drums": "percussion",
    "bass": "bass",
    "vocals": "melody",
}

# The "other" stem from Demucs maps directly to our "other" layer
# (htdemucs 4-source model combines piano/guitar/other into a single "other" stem)


class SeparationError(Exception):
    pass


def run_separation(
    input_path: Path,
    output_dir: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict[str, Path]:
    """Run Demucs source separation and save stems.

    Tries the Python API first, falls back to subprocess.
    Returns a dict mapping layer name -> stem WAV path.
    """
    device = _detect_device()
    if device == "cpu":
        _report(on_progress, 0.05, "separating:cpu_warning")

    _report(on_progress, 0.1, "separating:running_demucs")

    try:
        return _run_via_api(input_path, output_dir, device, on_progress)
    except ImportError:
        return _run_via_subprocess(input_path, output_dir, device, on_progress)


def _detect_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _run_via_api(
    input_path: Path,
    output_dir: Path,
    device: str,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict[str, Path]:
    import torch
    import torchaudio
    from demucs import apply, pretrained

    model = pretrained.get_model("htdemucs")
    model.to(device)

    wav, sr = torchaudio.load(str(input_path))
    if sr != model.samplerate:
        wav = torchaudio.functional.resample(wav, sr, model.samplerate)

    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    wav = wav.unsqueeze(0).to(device)

    _report(on_progress, 0.2, "separating:model_loaded")

    with torch.no_grad():
        sources = apply.apply_model(
            model, wav, device=device, shifts=1, split=True, overlap=0.25, progress=True
        )[0]

    _report(on_progress, 0.7, "separating:saving_stems")

    stems_dir = output_dir / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)

    return _save_stems(sources, model.samplerate, stems_dir)


def _run_via_subprocess(
    input_path: Path,
    output_dir: Path,
    device: str,
    on_progress: Callable[[float, str], None] | None = None,
) -> dict[str, Path]:
    demucs_exe = shutil.which("demucs") or shutil.which("python3") or sys.executable

    cmd: list[str]
    if demucs_exe.endswith("demucs") or "demucs" in str(demucs_exe):
        cmd = [demucs_exe]
    else:
        cmd = [demucs_exe, "-m", "demucs"]

    device_flag = _subprocess_device_flag(device)
    cmd += [
        "-n", "htdemucs",
        "-o", str(output_dir),
    ]
    if device_flag:
        cmd.extend(device_flag)
    cmd.append(str(input_path))

    _report(on_progress, 0.15, "separating:running_demucs_subprocess")

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=getattr(settings, "demucs_timeout_sec", 600),
        )
    except subprocess.CalledProcessError as e:
        raise SeparationError(f"Demucs failed: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise SeparationError(f"Demucs timed out after {e.timeout}s") from e

    _report(on_progress, 0.8, "separating:collecting_output")

    input_stem = input_path.stem
    demucs_out = output_dir / "htdemucs" / input_stem

    if not demucs_out.exists():
        raise SeparationError(
            f"Demucs output directory not found at {demucs_out}. "
            f"Expected Demucs to create output there."
        )

    stems_dir = output_dir / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)

    layer_paths: dict[str, Path] = {}
    for stem_name in DEMUCS_STEMS:
        stem_path = demucs_out / f"{stem_name}.wav"
        if not stem_path.exists():
            continue
        layer = STEM_TO_LAYER.get(stem_name)
        if layer:
            dest = stems_dir / f"{layer}.wav"
            shutil.copy2(stem_path, dest)
            layer_paths[layer] = dest

    combined = _combine_other_stems(demucs_out, stems_dir)
    if combined:
        layer_paths["other"] = combined

    _report(on_progress, 0.95, "separating:done")
    return layer_paths


def _save_stems(sources, sr: int, stems_dir: Path) -> dict[str, Path]:
    """Save tensor sources as WAV files and return layer->path map."""
    import torch
    import torchaudio

    layer_paths: dict[str, Path] = {}

    for i, stem_name in enumerate(DEMUCS_STEMS):
        source = sources[i].cpu()
        layer = STEM_TO_LAYER.get(stem_name)
        if layer:
            dest = stems_dir / f"{layer}.wav"
            torchaudio.save(str(dest), source, sr)
            layer_paths[layer] = dest
        elif stem_name == "other":
            dest = stems_dir / "other.wav"
            torchaudio.save(str(dest), source, sr)
            layer_paths["other"] = dest

    return layer_paths


def _combine_other_stems(demucs_out: Path, stems_dir: Path) -> Path | None:
    """Copy the 'other' stem directly to our output (4-source model already combines them)."""
    import shutil

    stem_path = demucs_out / "other.wav"
    if stem_path.exists():
        dest = stems_dir / "other.wav"
        shutil.copy2(stem_path, dest)
        return dest
    return None


def _subprocess_device_flag(device: str) -> list[str]:
    if device == "cuda":
        return ["-d", "cuda"]
    elif device == "mps":
        return ["-d", "mps"]
    return []


def _report(
    cb: Callable[[float, str], None] | None,
    progress: float,
    stage: str,
) -> None:
    if cb:
        cb(progress, stage)


def check_demucs_available() -> tuple[bool, str]:
    """Return (available, method) — method is 'api', 'subprocess', or error msg."""
    try:
        import demucs  # noqa: F401
        return True, "api"
    except ImportError:
        pass
    if shutil.which("demucs"):
        return True, "subprocess"
    return False, "Demucs is not installed. Install with: pip install demucs"
