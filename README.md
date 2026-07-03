# Nota

Turn raw audio into accurate, layered sheet music.

Upload a song → Nota separates it into instrumental layers, transcribes each to notation, and renders a multi-staff score with selective playback.

## Tech Stack

- **Backend:** Python, FastAPI, Demucs, Basic Pitch, music21, librosa
- **Frontend:** React 19, TypeScript, Vite, VexFlow 5, Tone.js, Zustand, Tailwind CSS

## Development

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the full phased build plan.

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
