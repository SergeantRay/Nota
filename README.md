# Nota

Turn raw audio into accurate, layered sheet music.

Upload a song → Nota separates it into instrumental layers, transcribes each to notation, and renders a piano roll score with selective playback.

## How it works

1. **Source separation** — Demucs (htdemucs) splits audio into 4 stems: drums, bass, other, vocals
2. **Pitch detection** — Basic Pitch + librosa detect notes per layer
3. **Post-processing** — Tempo/key detection, 16th-note quantization, voice separation
4. **Score assembly** — music21 builds a score, exports MusicXML + JSON
5. **Rendering** — Canvas-based piano roll (time × pitch), color-coded by layer
6. **Playback** — Tone.js plays back per-layer with mute/solo controls

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Demucs, Basic Pitch, music21, librosa, torch
- **Frontend:** React 19, TypeScript, Vite, Tone.js, Zustand, Tailwind CSS

## Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- ~2GB free RAM for Demucs model

### Setup

```bash
# Backend
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

The backend runs on `http://localhost:8000`, frontend on `http://localhost:5173`.

### Running tests

```bash
cd backend
source .venv/bin/activate
pip install pytest httpx
python -m pytest tests/ -v
```
