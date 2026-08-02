const LAYER_COLORS: Record<string, string> = {
  melody: "#f97316",
  other: "#22d3ee",
  bass: "#a78bfa",
  percussion: "#fbbf24",
};

const WHITE_KEYS = [0, 2, 4, 5, 7, 9, 11];
const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

interface Note {
  pitch: number;
  startTime: number;
  endTime: number;
  velocity: number;
  duration: string;
  dots: number;
  accidental: string | null;
  voice: number;
  instrument: string | null;
}

interface LayerInfo {
  notes: Note[];
  midiProgram: number;
  clef: string;
  instrumentName: string;
}

export interface ScoreRenderData {
  tempo: number;
  timeSignature: [number, number];
  keySignature: string;
  layers: Record<string, LayerInfo>;
}

const PADDING = { top: 10, right: 20, bottom: 40, left: 50 };
const MIN_MIDI = 21; // A0 — piano low
const MAX_MIDI = 108; // C8 — piano high

export function renderPianoRoll(
  canvas: HTMLCanvasElement,
  scoreData: ScoreRenderData,
  visibleLayers: Record<string, boolean>,
  activeLayer: string | null,
  onNoteClick?: (layer: string, noteIdx: number) => void,
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width;
  const h = rect.height;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + "px";
  canvas.style.height = h + "px";
  ctx.scale(dpr, dpr);

  const activeLayers = Object.entries(scoreData.layers).filter(
    ([id]) => visibleLayers[id],
  );
  if (activeLayers.length === 0) {
    ctx.fillStyle = "#6b7280";
    ctx.font = "13px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("No layers visible — enable layers in the sidebar", w / 2, h / 2);
    return;
  }

  const plotLeft = PADDING.left;
  const plotRight = w - PADDING.right;
  const plotTop = PADDING.top;
  const plotBottom = h - PADDING.bottom;
  const plotW = plotRight - plotLeft;
  const plotH = plotBottom - plotTop;

  // Find total duration
  let maxTime = 0;
  for (const [, layer] of activeLayers) {
    if (layer.notes.length > 0) {
      const last = layer.notes[layer.notes.length - 1];
      maxTime = Math.max(maxTime, last.endTime);
    }
  }
  if (maxTime === 0) maxTime = 1;

  const timeToX = (t: number) => plotLeft + (t / maxTime) * plotW;
  const midiToY = (m: number) => plotTop + (1 - (m - MIN_MIDI) / (MAX_MIDI - MIN_MIDI)) * plotH;

  // Background
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(plotLeft, plotTop, plotW, plotH);

  // White/grey key lanes
  for (let m = MIN_MIDI; m <= MAX_MIDI; m++) {
    const y = midiToY(m);
    const isWhite = WHITE_KEYS.includes(m % 12);
    ctx.strokeStyle = isWhite ? "rgba(148,163,184,0.06)" : "rgba(148,163,184,0.03)";
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(plotLeft, y);
    ctx.lineTo(plotRight, y);
    ctx.stroke();
  }

  // Octave C markers
  for (let m = MIN_MIDI; m <= MAX_MIDI; m++) {
    if (m % 12 === 0) {
      const y = midiToY(m);
      ctx.strokeStyle = "rgba(148,163,184,0.15)";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(plotLeft, y);
      ctx.lineTo(plotRight, y);
      ctx.stroke();
    }
  }

  // Bar lines
  const beatDur = 60 / scoreData.tempo;
  const barDur = beatDur * scoreData.timeSignature[0];
  let highlightNext = -1;
  let highlightLayer: string | null = null;

  const drawNote = (
    x: number,
    y: number,
    noteW: number,
    noteH: number,
    color: string,
    velocity: number,
    layer: string,
    noteIdx: number,
  ) => {
    const alpha = 0.4 + velocity * 0.6;
    const isHighlighted = activeLayer !== null && activeLayer !== layer;
    ctx.fillStyle = color + Math.round((isHighlighted ? alpha * 0.15 : alpha) * 255)
      .toString(16)
      .padStart(2, "0");

    // Pill shape
    const r = Math.min(noteH / 2, 3);
    const rx = x;
    const ry = y;
    const rw = Math.max(noteW, 2);
    const rh = noteH;

    ctx.beginPath();
    ctx.moveTo(rx + r, ry);
    ctx.lineTo(rx + rw - r, ry);
    ctx.arcTo(rx + rw, ry, rx + rw, ry + r, r);
    ctx.lineTo(rx + rw, ry + rh - r);
    ctx.arcTo(rx + rw, ry + rh, rx + rw - r, ry + rh, r);
    ctx.lineTo(rx + r, ry + rh);
    ctx.arcTo(rx, ry + rh, rx, ry + rh - r, r);
    ctx.lineTo(rx, ry + r);
    ctx.arcTo(rx, ry, rx + r, ry, r);
    ctx.closePath();
    ctx.fill();

    // Border for non-highlighted active layer
    if (!isHighlighted && noteW > 3) {
      ctx.strokeStyle = color + "60";
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }

    if (
      onNoteClick &&
      noteW > 4 &&
      !isHighlighted &&
      ctx.isPointInPath(highlightNext, highlightNext)
    ) {
      highlightNext = -1;
      highlightLayer = layer;
    }
  };

  // Draw notes
  for (const [layerId, layer] of activeLayers) {
    const color = LAYER_COLORS[layerId] || "#94a3b8";
    for (let i = 0; i < layer.notes.length; i++) {
      const n = layer.notes[i];
      const x = timeToX(n.startTime);
      const noteW = Math.max(timeToX(n.endTime) - x, 2);
      const midi = Math.min(Math.max(n.pitch, MIN_MIDI), MAX_MIDI);
      const y = midiToY(midi) - 3;
      const noteH = 6;
      drawNote(x, y, noteW, noteH, color, n.velocity / 127, layerId, i);
    }
  }

  // Y-axis labels (every octave C)
  ctx.fillStyle = "#94a3b8";
  ctx.font = "9px sans-serif";
  ctx.textAlign = "right";
  for (let m = MIN_MIDI; m <= MAX_MIDI; m++) {
    if (m % 12 === 0) {
      const oct = Math.floor(m / 12) - 1;
      ctx.fillText(`C${oct}`, plotLeft - 4, midiToY(m) + 3);
    }
  }

  // X-axis time labels
  ctx.fillStyle = "#64748b";
  ctx.font = "9px sans-serif";
  ctx.textAlign = "center";
  const tickInterval = Math.max(1, Math.ceil(maxTime / 10));
  for (let t = 0; t <= maxTime; t += tickInterval) {
    const x = timeToX(t);
    const mins = Math.floor(t / 60);
    const secs = Math.floor(t % 60);
    ctx.fillText(`${mins}:${secs.toString().padStart(2, "0")}`, x, plotBottom + 14);
  }

  // Legend
  const legendX = plotLeft + 8;
  let legendY = plotTop + 14;
  for (const [layerId] of activeLayers) {
    const color = LAYER_COLORS[layerId] || "#94a3b8";
    const isDimmed = activeLayer !== null && activeLayer !== layerId;
    const alpha = isDimmed ? 0.3 : 1;
    ctx.fillStyle = color;
    ctx.globalAlpha = alpha;
    ctx.fillRect(legendX, legendY - 6, 10, 10);
    ctx.globalAlpha = 1;
    ctx.fillStyle = isDimmed ? "#64748b" : "#e2e8f0";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(layerId, legendX + 14, legendY);
    legendY += 16;
  }

  // Click handler
  if (onNoteClick) {
    canvas.onclick = (e: MouseEvent) => {
      const mx = e.clientX - canvas.getBoundingClientRect().left;
      const my = e.clientY - canvas.getBoundingClientRect().top;
      for (const [layerId, layer] of activeLayers) {
        for (let i = 0; i < layer.notes.length; i++) {
          const n = layer.notes[i];
          const x = timeToX(n.startTime);
          const noteW = Math.max(timeToX(n.endTime) - x, 2);
          const midi = Math.min(Math.max(n.pitch, MIN_MIDI), MAX_MIDI);
          const y = midiToY(midi) - 3;
          if (mx >= x && mx <= x + noteW && my >= y && my <= y + 6) {
            onNoteClick(layerId, i);
            return;
          }
        }
      }
    };
  }
}
