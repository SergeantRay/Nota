import * as Tone from "tone";
import type { ScoreData, LayerKey } from "../stores/sessionStore";

const INSTRUMENT_FACTORIES: Record<
  LayerKey,
  () => Tone.Synth | Tone.MembraneSynth | Tone.FMSynth
> = {
  percussion: () => new Tone.MembraneSynth().toDestination(),
  bass: () => new Tone.FMSynth().toDestination(),
  other: () => new Tone.Synth().toDestination(),
  melody: () => new Tone.Synth().toDestination(),
};

const DEFAULT_VOLUMES: Record<LayerKey, number> = {
  percussion: -6,
  bass: -9,
  other: -12,
  melody: 0,
};

export interface PlaybackState {
  playing: boolean;
  position: number;
  duration: number;
}

export class ScorePlayer {
  private parts: Map<LayerKey, Tone.Part> = new Map();
  private synths: Map<LayerKey, Tone.Synth | Tone.MembraneSynth | Tone.FMSynth> = new Map();
  private gains: Map<LayerKey, Tone.Gain> = new Map();
  private scoreData: ScoreData | null = null;
  private onStateChange: ((state: PlaybackState) => void) | null = null;
  private rafId: number | null = null;
  private _disposed = false;

  loadScore(scoreData: ScoreData): void {
    this.disposeAll();
    this.scoreData = scoreData;

    for (const layerId of ["percussion", "bass", "other", "melody"] as LayerKey[]) {
      const layerData = scoreData.layers[layerId];
      if (!layerData || layerData.notes.length === 0) continue;

      const synth = INSTRUMENT_FACTORIES[layerId]();
      const gain = new Tone.Gain(DEFAULT_VOLUMES[layerId]).toDestination();
      synth.disconnect();
      synth.connect(gain);

      this.synths.set(layerId, synth);
      this.gains.set(layerId, gain);

      const events: Array<{ time: number; note: number; duration: number; velocity: number }> = [];
      for (const note of layerData.notes) {
        events.push({
          time: note.startTime,
          note: note.pitch,
          duration: note.endTime - note.startTime,
          velocity: note.velocity,
        });
      }

      const part = new Tone.Part(
        (time, value) => {
          synth.triggerAttackRelease(
            value.note,
            Math.max(value.duration, 0.01),
            time,
            value.velocity / 127,
          );
        },
        events,
      );

      part.loop = false;
      this.parts.set(layerId, part);
    }

    // Compute total duration
    let maxEnd = 0;
    for (const [, layerData] of Object.entries(scoreData.layers)) {
      for (const note of layerData.notes) {
        if (note.endTime > maxEnd) maxEnd = note.endTime;
      }
    }
    this._duration = maxEnd;
  }

  private _duration = 0;

  get duration(): number {
    return this._duration;
  }

  play(): void {
    if (this._disposed || !this.scoreData) return;
    if (Tone.getTransport().state === "started") return;

    // Set tempo
    Tone.getTransport().bpm.value = this.scoreData.tempo;

    // Schedule all parts
    for (const part of this.parts.values()) {
      part.start(0);
    }

    Tone.getTransport().start();
    this.startCursorLoop();
  }

  pause(): void {
    Tone.getTransport().pause();
    this.stopCursorLoop();
  }

  stop(): void {
    Tone.getTransport().stop();
    for (const part of this.parts.values()) {
      part.stop();
    }
    this.stopCursorLoop();
    if (this.onStateChange) {
      this.onStateChange({ playing: false, position: 0, duration: this._duration });
    }
  }

  setTempo(bpm: number): void {
    if (this._disposed) return;
    Tone.getTransport().bpm.value = bpm;
  }

  setLayerMuted(layer: LayerKey, muted: boolean): void {
    const gain = this.gains.get(layer);
    if (gain) {
      gain.gain.rampTo(muted ? -Infinity : DEFAULT_VOLUMES[layer], 0.1);
    }
  }

  setLayerVolume(layer: LayerKey, db: number): void {
    const gain = this.gains.get(layer);
    if (gain) {
      gain.gain.rampTo(db, 0.1);
    }
  }

  onPlaybackState(cb: (state: PlaybackState) => void): void {
    this.onStateChange = cb;
  }

  dispose(): void {
    this.disposeAll();
    this._disposed = true;
  }

  private disposeAll(): void {
    this.stopCursorLoop();
    Tone.getTransport().cancel();
    for (const part of this.parts.values()) {
      part.dispose();
    }
    this.parts.clear();
    for (const synth of this.synths.values()) {
      synth.dispose();
    }
    this.synths.clear();
    for (const gain of this.gains.values()) {
      gain.dispose();
    }
    this.gains.clear();
  }

  private startCursorLoop(): void {
    this.stopCursorLoop();
    const tick = () => {
      if (this._disposed) return;
      const transport = Tone.getTransport();
      const pos = transport.seconds;
      if (this.onStateChange) {
        this.onStateChange({
          playing: transport.state === "started",
          position: pos,
          duration: this._duration,
        });
      }
      if (transport.state === "started") {
        this.rafId = requestAnimationFrame(tick);
      }
    };
    this.rafId = requestAnimationFrame(tick);
  }

  private stopCursorLoop(): void {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }
}

// Singleton
let _player: ScorePlayer | null = null;

export function getScorePlayer(): ScorePlayer {
  if (!_player) {
    _player = new ScorePlayer();
  }
  return _player;
}
