# Nota — Phased Implementation Plan

## Architecture Review Notes

Before breaking this into parts, a few observations on the original architecture:

1. **4→5 stem mapping is the riskiest part.** Demucs outputs 4 stems (drums, bass, other, vocals). Splitting "other" into tenor + alto/soprano via frequency bands (200-800Hz, 800-2500Hz) is crude and will bleed heavily on real music. Start with 4 stems and add the 5th as a stretch goal — or accept that "other" stays as one staff initially.

2. **MusicXML as the interchange format adds complexity.** VexFlow doesn't natively parse MusicXML — you'd need to build a parser or use the JSON output directly. Suggestion: use the JSON format for the VexFlow renderer too, and keep MusicXML as an export-only format for external editors.

3. **Async processing doesn't need Celery for MVP.** FastAPI's `BackgroundTasks` or a simple `asyncio.create_task` + polling endpoint is sufficient for a single-user or low-concurrency app. Add Celery/Redis only when you need horizontal scaling.

4. **Percussion detection needs a different path.** Basic Pitch won't detect unpitched percussion well. For MVP, use onset detection + spectral centroid classification (kick ≈ 50-100Hz, snare ≈ 200-400Hz, hi-hat ≈ 8-15kHz). This is a separate pipeline from pitched note detection.

5. **The frontend score state model mixes concerns.** `VoiceNote` has both `pitch` (MIDI) and `duration` (string label like "quarter"). Pick one representation for duration — fractional beats (e.g., `0.25` for 16th, `0.5` for 8th, `1.0` for quarter) is easier to compute against and convert to notation strings at render time.

---

## Revised Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend framework | FastAPI | Async, good docs, file upload built-in |
| Source separation | Demucs (htdemucs 6-source model) | 6-source variant can separate piano/guitar, giving a cleaner split |
| Pitch detection | Basic Pitch + librosa (onset) | Basic Pitch for pitched stems, librosa onset detection for percussion |
| Music theory | music21 | Key detection, quantization, MusicXML export |
| Frontend framework | React 19 + Vite + TypeScript | Fast, typed, ESM-native |
| Sheet rendering | VexFlow 5 | Latest, Canvas/SVG backends |
| Audio playback | Tone.js | Web Audio wrapper, Transport for sync |
| State management | Zustand | Lightweight, no boilerplate |
| Styling | Tailwind CSS | Utility-first, fast iteration |

---

## Phased Build Plan

Each part is one or more commits/PRs. Parts are ordered so each one adds a testable increment on top of the previous.

---

### Part 0 — Project Scaffolding

**Goal:** Monorepo with backend + frontend skeletons, both runnable, gitignored correctly.

**Files to create:**
```
NOVA-Ver2/
  .gitignore
  README.md
  backend/
    requirements.txt
    pyproject.toml
    app/
      __init__.py
      main.py              # FastAPI app with /health
      config.py            # Settings (sample rate, max file size, etc.)
    tests/
      __init__.py
      test_health.py
  frontend/
    package.json
    tsconfig.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
      index.css
    public/
      favicon.ico
```

**Checkpoint:** `GET /health` returns `{"status": "ok"}`, frontend shows "Nota" heading.

---

### Part 1 — Audio Upload + Validation

**Goal:** User can upload a WAV/MP3/FLAC file, backend validates and stores it, returns a session ID.

**Backend:**
- `POST /api/upload` — multipart file upload
  - Validate: file extension, MIME type, size < 100MB
  - Validate audio: use `librosa` to check duration (2s–30min), sample rate, channels
  - Store to `uploads/{session_id}/original.wav`
  - Return `{ session_id, fileName, duration, sampleRate, channels, status: "uploaded" }`
- `GET /api/session/{session_id}` — return session metadata
- `models.py` — `Session` dataclass with status enum
- `storage.py` — file I/O helpers (save upload, read/write session JSON)

**Frontend:**
- `UploadZone` component — drag-and-drop area, file picker
- File validation feedback (wrong format, too large, too short)
- Upload progress bar (fetch with `onUploadProgress`)
- On success: store `session_id` in Zustand, transition to "processing" state

**Checkpoint:** Upload a WAV, see `session_id` returned, file saved on disk.

---

### Part 2 — Source Separation (Demucs)

**Goal:** Backend runs Demucs on uploaded audio, outputs 4 stems as WAV files.

**Backend:**
- `pipeline/separator.py` — wraps Demucs
  - Load audio → run `htdemucs` (6-source: drums, bass, piano, guitar, vocals, other)
  - Map to our layers: drums→percussion, bass→bass, vocals→melody, piano+guitar+other→tenor/altoSoprano (combined for now)
  - Save each stem to `sessions/{id}/stems/{layer}.wav`
- `POST /api/session/{id}/process` — kicks off separation async
- `GET /api/session/{id}/status` — returns `{ status: "separating", progress: 0.0-1.0, stage: "demucs" }`
- Progress reporting: poll every 2s from frontend

**Key decisions:**
- Skip GPU detection for MVP — warn if CUDA unavailable
- If Demucs fails, return error with message, allow retry

**Checkpoint:** Upload audio → process → 4 WAV files in session directory.

---

### Part 3 — Pitch Detection

**Goal:** For each separated stem, detect notes (pitch, start, end, confidence).

**Backend:**
- `pipeline/pitch_detector.py`
  - For pitched stems (bass, tenor/altoSoprano, melody): use Basic Pitch
  - For percussion stem: use librosa onset detection + spectral centroid classification
  - Output format: `list[{pitch_midi, start_sec, end_sec, velocity, confidence}]`
- Extend process endpoint to run detection after separation
- Store results as `sessions/{id}/raw_notes/{layer}.json`

**Key decisions:**
- Basic Pitch confidence threshold: 0.3 for bass/tenor, 0.5 for melody
- Percussion: classify onsets into kick/snare/hi-hat/other by frequency band
- Run stems in parallel (they're independent)

**Checkpoint:** Process a song → JSON arrays of detected notes per layer.

---

### Part 4 — Musical Post-Processing

**Goal:** Clean up raw note data using music theory constraints.

**Backend:**
- `pipeline/post_processor.py`
  - Tempo detection: onset correlation, Krumhansl-Schmuckler for key
  - Beat tracking: map note onsets to beat grid
  - Time quantization: snap to nearest 16th note (configurable)
  - Key signature detection + enharmonic spelling
  - Voice separation: split overlapping notes into voice 1/voice 2 per staff
  - Remove low-confidence notes (< threshold)
- Store results as `sessions/{id}/quantized_notes/{layer}.json`

**Key decisions:**
- Quantization is the hardest sub-problem. Start with simple "round to grid" and flag low-confidence regions.
- Let user override detected tempo/key (frontend will add controls later).
- If key detection confidence < 50%, default to C major.

**Checkpoint:** Raw notes → cleaned, quantized, key-aware note lists.

---

### Part 5 — Score Assembly + Export

**Goal:** Build a music21 Score from processed notes and export MusicXML + JSON.

**Backend:**
- `pipeline/score_assembler.py`
  - Create 4 music21 Parts (percussion, bass, tenor/altoSoprano, melody)
  - Assign clefs, instruments, key/time signatures
  - Insert notes with correct durations, accidentals, ties
  - Export MusicXML to `sessions/{id}/score.musicxml`
- `formats/json_exporter.py`
  - Convert music21 Score → our JSON schema (for Tone.js + VexFlow)
  - Export to `sessions/{id}/score.json`
- `GET /api/session/{id}/result` — return full score data
  - Response: `{ tempo, timeSignature, keySignature, layers: {...}, duration, musicxml: "<xml string>" }`

**Key decisions:**
- The JSON format is the canonical frontend format. MusicXML is an export bonus.
- Percussion staff: use percussion clef, map MIDI 36→kick line, 38→snare line, 42/46→hi-hat positions.

**Checkpoint:** Full pipeline → MusicXML file + JSON score returned from API.

---

### Part 6 — Frontend Shell + Processing UI

**Goal:** Full UI shell with processing progress, sidebar controls (non-functional), and score area placeholder.

**Frontend:**
- Layout: `<AppShell>` with header, sidebar, main area (Tailwind grid)
- `<UploadZone>` — wire to `POST /api/upload` (from Part 1, now full flow)
- `<ProcessingStatus>` — poll `GET /api/session/{id}/status`, show stage name + progress bar
- `<LayerControls>` — 4 toggle rows (percussion/bass/tenor_altoSoprano/melody), non-functional buttons
- `<PlaybackControls>` — play/pause/stop buttons, tempo display, non-functional
- `stores/sessionStore.ts` — Zustand store for session state, layer visibility/mute, playback state
- `api/client.ts` — typed fetch wrappers for all endpoints

**Checkpoint:** Upload → watch progress bar → see session result (JSON visible in DevTools).

---

### Part 7 — Sheet Music Rendering (VexFlow)

**Goal:** Render the 4-staff score system from JSON data.

**Frontend:**
- `components/ScoreCanvas.tsx` — VexFlow Renderer (SVG backend)
- `rendering/scoreBuilder.ts` — converts our JSON note format → VexFlow StaveNotes
  - Handle: noteheads, accidentals, dots, ties, beams, rests
  - Handle: clefs (percussion, bass, treble), key/time signatures
  - Handle: measure wrapping (horizontal overflow → next system)
- `rendering/percussionMapper.ts` — maps MIDI pitch → percussion staff position + notehead style
- `components/CursorOverlay.tsx` — vertical red line (positioned but non-moving for now)
- Zoom controls (50%-200%) and horizontal scroll for long scores

**Key decisions:**
- Use SVG backend (not Canvas) for crisp rendering at all zoom levels.
- Render only visible layers (respect `layer.visible` from store).
- Performance: for scores > 100 measures, virtualize or paginate.

**Checkpoint:** Load a result → see a 4-staff score with notes rendered correctly.

---

### Part 8 — Playback (Tone.js)

**Goal:** Play back the score with per-layer mute/solo/volume and a moving cursor.

**Frontend:**
- `audio/ScorePlayer.ts` — wraps Tone.js
  - `Tone.Transport` for master clock
  - `Tone.Part` per layer for note scheduling
  - `Tone.Gain` per layer for mute/solo/volume
  - Instrument mapping: MembraneSynth (perc), FMSynth (bass), Synth (tenor/altoSoprano/melody)
- Wire `<LayerControls>` mute/solo/volume to `ScorePlayer` gain nodes
- Wire `<PlaybackControls>` play/pause/stop to `Tone.Transport`
- `CursorOverlay` — animate vertical line via `requestAnimationFrame` synced to `Tone.Transport.position`
- Tempo slider (0.5x–1.5x)
- Seek bar with time display

**Key decisions:**
- Use `Tone.Transport` for all scheduling — never `setTimeout`/`setInterval` for audio.
- Gain ramps (0.1s) on mute/unmute to prevent clicks.
- Default volume balance: percussion -6dB, bass -9dB, tenor/altoSoprano -12dB, melody 0dB.

**Checkpoint:** Hit play → hear the score, toggle layers on/off, see cursor move.

---

### Part 9 — Polish + Edge Cases

**Goal:** Production-quality UX, error handling, and responsive design.

**Frontend:**
- Loading skeletons for every async state
- Error states: upload failure, processing failure, empty result — each with retry action
- Empty state: "Upload audio to get started" with example/demo option
- Edge case: stems with zero detected notes → show "no notes detected" on staff, not blank
- Edge case: silence at start/end → trim or show rests
- Edge case: very short notes (< 32nd) → merge into longer note or flag
- Keyboard shortcuts: Space (play/pause), M (mute selected), S (solo selected), 1-4 (select layer)
- Responsive: sidebar collapses on tablet, score scrolls horizontally
- `<ProcessingStatus>` — show per-stage breakdown (separating → detecting → quantizing → assembling)
- Drag-and-drop visual feedback (highlight drop zone, show filename on drag)

**Backend:**
- Input validation edge cases: corrupted WAV header, zero-length audio, silent audio
- Timeout handling: kill process if > 10 min, return partial result
- Error recovery: if one stem fails, continue with remaining stems
- Log key processing parameters per session for debugging

**Checkpoint:** Full app — upload a song, see sheet music, play it back, toggle layers, works on tablet.

---

## Summary Table

| Part | Name | Backend | Frontend | Testable Deliverable |
|------|------|---------|----------|---------------------|
| 0 | Scaffolding | FastAPI + React skeleton | Vite + React shell | `/health` + "Nota" heading |
| 1 | Upload + Validation | Upload endpoint, session model | UploadZone, stores | Upload WAV → session_id |
| 2 | Source Separation | Demucs integration | ProcessingStatus polling | 4 stems on disk |
| 3 | Pitch Detection | Basic Pitch + librosa | — (status updates) | Raw notes JSON per layer |
| 4 | Post-Processing | Tempo/key/quantize | — (status updates) | Quantized notes JSON |
| 5 | Score Assembly | music21 Score → MusicXML + JSON | — | MusicXML + JSON from API |
| 6 | Frontend Shell | — | Full layout, controls, polling | Upload → see result in DevTools |
| 7 | Sheet Rendering | — | VexFlow 4-staff renderer | Score visible on screen |
| 8 | Playback | — | Tone.js player + cursor | Hear audio, toggle layers |
| 9 | Polish | Error handling, logging | Edge cases, responsive, kb shortcuts | Production-ready UX |

---

## Git Strategy

- One branch per part: `part-0-scaffolding`, `part-1-upload`, etc.
- Merge each into `main` after review.
- Each branch builds on the previous — merge order matters.
- Tag each merge: `v0.1.0-scaffolding`, `v0.2.0-upload`, etc.
- Part 0 should be the first PR — sets up CI, linting, and the monorepo structure.
