import { Factory, StaveNote, Voice, VoiceMode, Formatter } from "vexflow";
import type { ScoreData, LayerKey } from "../stores/sessionStore";

const NOTE_MAP: Record<string, string> = {
  "16th": "16",
  eighth: "8",
  quarter: "q",
  half: "h",
  whole: "w",
};

const CLEF_MAP: Record<string, string> = {
  treble: "treble",
  bass: "bass",
  percussion: "percussion",
};

function midiToNoteName(midi: number): string {
  const names = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"];
  const octave = Math.floor(midi / 12) - 1;
  const name = names[midi % 12];
  return `${name}/${octave}`;
}

function durationToVex(duration: string, dots: number): string {
  const base = NOTE_MAP[duration] || "q";
  return base + ".".repeat(dots);
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
  const totalHeight = activeLayers.length * staveHeight + 40;

  const vf = new Factory({
    renderer: { elementId: container.id || "score-container", width: staveWidth + 40, height: totalHeight },
  });

  const context = vf.getContext();

  for (const [, layerData] of activeLayers) {
    const notes = layerData.notes;
    const clef = CLEF_MAP[layerData.clef] || "treble";

    const v1Notes = notes.filter((n) => n.voice !== 2);
    const v2Notes = notes.filter((n) => n.voice === 2);

    const voiceGroups = [v1Notes, v2Notes].filter((g) => g.length > 0);

    if (voiceGroups.length === 0) {
      const v = new Voice({ numBeats: 4, beatValue: 4 });
      v.addTickable(
        new StaveNote({ keys: ["b/4"], duration: "wr", clef }),
      );
      v.setMode(VoiceMode.FULL);

      const fmt = new Formatter().joinVoices([v]);
      fmt.format([v], staveWidth);

      const stave = vf.Stave({ width: staveWidth });
      stave.addClef(clef);
      stave.addTimeSignature("4/4");
      stave.addKeySignature(scoreData.keySignature);
      v.draw(context, stave);
      continue;
    }

    const voices: Voice[] = [];

    for (const voiceNotes of voiceGroups) {
      const isV2 = voiceNotes === v2Notes;
      const tickables: StaveNote[] = [];
      let i = 0;

      while (i < voiceNotes.length) {
        const chordNotes = [voiceNotes[i]];
        let j = i + 1;
        while (j < voiceNotes.length && voiceNotes[j].startTime === voiceNotes[i].startTime) {
          chordNotes.push(voiceNotes[j]);
          j++;
        }

        const keys = chordNotes.map((n) => {
          const noteName = midiToNoteName(n.pitch);
          return n.accidental ? `${noteName}${n.accidental}` : noteName;
        });

        const note = vf.StaveNote({
          keys,
          duration: durationToVex(voiceNotes[i].duration, voiceNotes[i].dots),
          clef: layerData.clef === "percussion" ? "percussion" : clef,
          stemDirection: isV2 ? -1 : 1,
        });

        tickables.push(note);
        i = j;
      }

      if (tickables.length > 0) {
        const v = new Voice({ numBeats: 4, beatValue: 4 });
        v.addTickables(tickables);
        v.setMode(VoiceMode.FULL);
        voices.push(v);
      }
    }

    if (voices.length === 0) continue;

    const stave = vf.Stave({ width: staveWidth });
    stave.addClef(clef);
    stave.addTimeSignature("4/4");
    stave.addKeySignature(scoreData.keySignature);

    const fmt = new Formatter().joinVoices(voices);
    fmt.format(voices, staveWidth);

    for (const v of voices) {
      v.draw(context, stave);
    }
  }

  vf.draw();
}
