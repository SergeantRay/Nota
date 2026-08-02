import { create } from "zustand";
import { getSession, startProcessing } from "../api/client";

export type SessionStatus =
  | "uploaded"
  | "preprocessing"
  | "separating"
  | "detecting"
  | "postprocessing"
  | "assembling"
  | "complete"
  | "error";

export type LayerKey = "percussion" | "bass" | "other" | "melody";

export interface LayerState {
  visible: boolean;
  muted: boolean;
  solo: boolean;
}

export interface ScoreData {
  tempo: number;
  timeSignature: [number, number];
  keySignature: string;
  layers: Record<LayerKey, {
    notes: Array<{
      pitch: number;
      startTime: number;
      endTime: number;
      velocity: number;
      duration: string;
      dots: number;
      accidental: string | null;
      voice: number;
      instrument: string | null;
    }>;
    midiProgram: number;
    clef: string;
    instrumentName: string;
  }>;
}

export interface SessionState {
  sessionId: string | null;
  fileName: string | null;
  durationSec: number | null;
  status: SessionStatus | null;
  progress: number;
  stage: string;
  error: string | null;
  uploadProgress: number;
  isProcessing: boolean;
  scoreData: ScoreData | null;
  layers: Record<LayerKey, LayerState>;
  tempo: number;

  setSession: (data: {
    sessionId: string;
    fileName: string;
    durationSec: number;
    status: SessionStatus;
  }) => void;
  setStatus: (status: SessionStatus, progress: number) => void;
  setError: (error: string) => void;
  setUploadProgress: (pct: number) => void;
  setScoreData: (data: ScoreData) => void;
  toggleLayerVisible: (layer: LayerKey) => void;
  toggleLayerMuted: (layer: LayerKey) => void;
  toggleLayerSolo: (layer: LayerKey) => void;
  setTempo: (tempo: number) => void;
  reset: () => void;
  startPolling: () => void;
  stopPolling: () => void;
  isPlaying: boolean;
  playbackPosition: number;
  setPlaybackState: (state: { playing: boolean; position: number; duration: number }) => void;
}

let _pollTimer: ReturnType<typeof setInterval> | null = null;

function defaultLayers(): Record<LayerKey, LayerState> {
  return {
    percussion: { visible: true, muted: false, solo: false },
    bass: { visible: true, muted: false, solo: false },
    other: { visible: true, muted: false, solo: false },
    melody: { visible: true, muted: false, solo: false },
  };
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessionId: null,
  fileName: null,
  durationSec: null,
  status: null,
  progress: 0,
  stage: "",
  error: null,
  uploadProgress: 0,
  isProcessing: false,
  scoreData: null,
  layers: defaultLayers(),
  tempo: 120,
  isPlaying: false,
  playbackPosition: 0,

  setSession: (data) =>
    set({
      sessionId: data.sessionId,
      fileName: data.fileName,
      durationSec: data.durationSec,
      status: data.status,
      progress: 0,
      stage: "",
      error: null,
      uploadProgress: 0,
      isProcessing: false,
      scoreData: null,
      layers: defaultLayers(),
    }),

  setStatus: (status, progress) => set({ status, progress }),

  setError: (error) => set({ error, status: "error" as SessionStatus, isProcessing: false }),

  setUploadProgress: (pct) => set({ uploadProgress: pct }),

  setScoreData: (data) => set({ scoreData: data, tempo: data.tempo }),

  toggleLayerVisible: (layer) =>
    set((state) => ({
      layers: {
        ...state.layers,
        [layer]: { ...state.layers[layer], visible: !state.layers[layer].visible },
      },
    })),

  toggleLayerMuted: (layer) =>
    set((state) => ({
      layers: {
        ...state.layers,
        [layer]: { ...state.layers[layer], muted: !state.layers[layer].muted },
      },
    })),

  toggleLayerSolo: (layer) =>
    set((state) => ({
      layers: {
        ...state.layers,
        [layer]: { ...state.layers[layer], solo: !state.layers[layer].solo },
      },
    })),

  setTempo: (tempo) => set({ tempo }),

  reset: () => {
    get().stopPolling();
    set({
      sessionId: null,
      fileName: null,
      durationSec: null,
      status: null,
      progress: 0,
      stage: "",
      error: null,
      uploadProgress: 0,
      isProcessing: false,
      scoreData: null,
      layers: defaultLayers(),
      tempo: 120,
      isPlaying: false,
      playbackPosition: 0,
    });
  },

  startPolling: () => {
    const { sessionId, stopPolling } = get();
    if (!sessionId) return;
    stopPolling();

    const poll = async () => {
      const { sessionId: id } = get();
      if (!id) return;
      try {
        const data = await getSession(id);
        set({
          status: data.status as SessionStatus,
          progress: data.progress,
          stage: data.stage,
          error: data.error,
          isProcessing:
            data.status !== "complete" && data.status !== "error",
        });
        if (data.status === "complete" || data.status === "error") {
          get().stopPolling();
        }
        if (data.score_json) {
          set({ scoreData: data.score_json as unknown as ScoreData, tempo: (data.score_json as Record<string, unknown>).tempo as number ?? 120 });
        }
      } catch {
        // backend may be temporarily unavailable; keep polling
      }
    };

    _pollTimer = setInterval(poll, 2000);
    poll(); // immediate first poll
  },

  stopPolling: () => {
    if (_pollTimer !== null) {
      clearInterval(_pollTimer);
      _pollTimer = null;
    }
    set({ isProcessing: false });
  },

  setPlaybackState: (s) =>
    set({ isPlaying: s.playing, playbackPosition: s.position }),
}));
