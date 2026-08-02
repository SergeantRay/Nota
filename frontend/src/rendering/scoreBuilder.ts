import { Factory, StaveNote, Voice, VoiceMode, Formatter } from "vexflow";
import type { ScoreData, LayerKey } from "../stores/sessionStore";

const NOTE_MAP: Record<string, string> = {
  "16th": "16",
  eighth: "8",
  quarter: "q",
  half: "h",
  whole: "w",
};

const DURATION_TICKS: Record<string, number> = {
  "16th": 1024,
  eighth: 2048,
  quarter: 4096,
  half: 8192,
  whole: 16384,
};

const CLEF_MAP: Record<string, string> = {
  treble: "treble",
  bass: "bass",
  percussion: "percussion",
};

function midiToNoteName(midi: number): string {
  const names = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"];
  const octave = Math.floor(midi / 12) - 1;
  return `${names[midi % 12]}/${octave}`;
}

function durationToVex(duration: string, dots: number): string {
  const base = NOTE_MAP[duration] || "q";
  return base + ".".repeat(dots);
}

const BEATS_PER_MEASURE = 4;
const MEASURES_PER_STAVE = 4;
const MAX_RENDER_MEASURES = 24;

interface NoteItem {
  startTime: number;
  endTime: number;
  duration: string;
  dots: number;
  pitch: number;
  velocity: number;
  accidental: string | null;
  voice: number;
  instrument: string | null;
}

function bundleByMeasure(
  notes: NoteItem[],
  tempo: number,
  maxMeasures: number,
): NoteItem[][] {
  const beatDur = 60 / tempo;
  const measures: NoteItem[][] = [];
  let cap = 0;

  for (const n of notes) {
    const measureIdx = Math.floor(n.startTime / beatDur / BEATS_PER_MEASURE);
    if (measureIdx >= maxMeasures) break;
    while (measures.length <= measureIdx) {
      measures.push([]);
      cap = (measures.length) * BEATS_PER_MEASURE;
    }
    measures[measureIdx].push({
      ...n,
      startTime: n.startTime - cap * beatDur, // rebase to measure start
    });
  }
  return measures;
}

function buildVoiceForMeasure(
  vf: Factory,
  notes: NoteItem[],
  clef: string,
  stemDir: number,
): Voice | null {
  if (notes.length === 0) return null;

  const ticksPerMeasure = BEATS_PER_MEASURE * 4096; // 16384
  const tickables: StaveNote[] = [];
  let usedTicks = 0;

  // Group simultaneous notes into chords
  let i = 0;
  while (i < notes.length) {
    const chordNotes = [notes[i]];
    let j = i + 1;
    while (j < notes.length && notes[j].startTime === notes[i].startTime) {
      chordNotes.push(notes[j]);
      j++;
    }

    const durTicks = DURATION_TICKS[notes[i].duration] || 4096;
    if (usedTicks + durTicks > ticksPerMeasure * 1.1) break; // allow slight overflow

    const keys = chordNotes.map((n) => {
      const noteName = midiToNoteName(n.pitch);
      return n.accidental ? `${noteName}${n.accidental}` : noteName;
    });

    const note = vf.StaveNote({
      keys,
      duration: durationToVex(notes[i].duration, notes[i].dots),
      clef,
      stemDirection: stemDir,
    });

    tickables.push(note);
    usedTicks += durTicks;
    i = j;

    if (tickables.length > 100) break; // safety ceiling
  }

  if (tickables.length === 0) return null;

  // Pad with rest if needed
  if (usedTicks < ticksPerMeasure) {
    const restDur = ticksToRest(ticksPerMeasure - usedTicks);
    if (restDur) {
      tickables.push(vf.StaveNote({ keys: ["b/4"], duration: restDur, clef }));
    }
  }

  const v = new Voice({ numBeats: BEATS_PER_MEASURE, beatValue: 4 });
  v.addTickables(tickables);
  v.setMode(VoiceMode.FULL);
  return v;
}

function ticksToRest(ticks: number): string | null {
  if (ticks >= 16384) return "wr";
  if (ticks >= 8192) return "hr";
  if (ticks >= 4096) return "qr";
  if (ticks >= 2048) return "8r";
  if (ticks >= 1024) return "16r";
  return null;
}

export function renderScore(
  container: HTMLDivElement,
  scoreData: ScoreData,
  visibleLayers: Record<LayerKey, boolean>,
): void {
  container.innerHTML = "";

  const activeLayers = Object.entries(scoreData.layers).filter(
    ([id]) => visibleLayers[id as LayerKey],
  );

  if (activeLayers.length === 0) return;

  const staveWidth = Math.max(container.clientWidth - 80, 400);
  const staveHeight = 160;
  const layerCount = activeLayers.length;

  // Bundle notes by measure for each layer
  const layerMeasures: Array<NoteItem[][]> = [];
  let maxMeasureCount = 0;

  for (const [, layerData] of activeLayers) {
    const measures = bundleByMeasure(layerData.notes, scoreData.tempo, MAX_RENDER_MEASURES);
    layerMeasures.push(measures);
    maxMeasureCount = Math.max(maxMeasureCount, measures.length);
  }

  if (maxMeasureCount === 0) return;

  const stavesPerLayer = Math.ceil(maxMeasureCount / MEASURES_PER_STAVE);
  const pageHeight = layerCount * staveHeight + 50;
  const totalHeight = stavesPerLayer * pageHeight + 20;

  const vf = new Factory({
    renderer: {
      elementId: container.id || "score-container",
      width: staveWidth + 40,
      height: totalHeight,
    },
  });

  const context = vf.getContext();
  context.setFont("Arial", 10, "").setFillStyle("#94a3b8");

  for (let si = 0; si < stavesPerLayer; si++) {
    const startMeasure = si * MEASURES_PER_STAVE;
    const staveTopY = si * pageHeight + 20;

    // Layer label on first stave only
    if (si === 0) {
      context.fillText("Showing first " + MAX_RENDER_MEASURES + " measures", 20, staveTopY - 8);
    }

    for (let li = 0; li < activeLayers.length; li++) {
      const [layerId, layerData] = activeLayers[li];
      const staveY = staveTopY + 40 + li * staveHeight;
      const clef = CLEF_MAP[layerData.clef] || "treble";
      const measures = layerMeasures[li] ?? [];

      // Collect notes for this stave's measures
      const v1Notes: NoteItem[] = [];
      const v2Notes: NoteItem[] = [];

      for (let m = startMeasure; m < startMeasure + MEASURES_PER_STAVE && m < measures.length; m++) {
        for (const n of measures[m]) {
          if (n.voice === 2) {
            v2Notes.push(n);
          } else {
            v1Notes.push(n);
          }
        }
      }

      if (v1Notes.length === 0 && v2Notes.length === 0) {
        // Empty stave — whole rest
        const v = new Voice({ numBeats: BEATS_PER_MEASURE * MEASURES_PER_STAVE, beatValue: 4 });
        v.addTickable(
          new StaveNote({ keys: ["b/4"], duration: `${BEATS_PER_MEASURE * MEASURES_PER_STAVE}w`, clef }),
        );
        v.setMode(VoiceMode.FULL);
        const fmt = new Formatter().joinVoices([v]);
        fmt.format([v], staveWidth);
        const stave = vf.Stave({ x: 20, y: staveY, width: staveWidth });
        stave.addClef(clef);
        if (layerId === activeLayers[0][0]) {
          stave.addTimeSignature("4/4");
          stave.addKeySignature(scoreData.keySignature);
        }
        v.draw(context, stave);
        continue;
      }

      const v1 = buildVoiceForMeasure(vf, v1Notes, clef, 1);
      const v2 = buildVoiceForMeasure(vf, v2Notes, clef, -1);

      const voices: Voice[] = [];
      if (v1) voices.push(v1);
      if (v2) voices.push(v2);
      if (voices.length === 0) continue;

      // Use multi-measure approach: one voice per measure
      const stave = vf.Stave({ x: 20, y: staveY, width: staveWidth });
      stave.addClef(clef);
      if (layerId === activeLayers[0][0]) {
        stave.addTimeSignature("4/4");
        stave.addKeySignature(scoreData.keySignature);
      }

      const fmt = new Formatter().joinVoices(voices);
      fmt.format(voices, staveWidth);

      for (const v of voices) {
        v.draw(context, stave);
      }
    }
  }

  vf.draw();
}
