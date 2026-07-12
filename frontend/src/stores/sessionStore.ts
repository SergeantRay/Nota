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

  setSession: (data: {
    sessionId: string;
    fileName: string;
    durationSec: number;
    status: SessionStatus;
  }) => void;
  setStatus: (status: SessionStatus, progress: number) => void;
  setError: (error: string) => void;
  setUploadProgress: (pct: number) => void;
  reset: () => void;
  startPolling: () => void;
  stopPolling: () => void;
}

let _pollTimer: ReturnType<typeof setInterval> | null = null;

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
    }),

  setStatus: (status, progress) => set({ status, progress }),

  setError: (error) => set({ error, status: "error" as SessionStatus, isProcessing: false }),

  setUploadProgress: (pct) => set({ uploadProgress: pct }),

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
}));
