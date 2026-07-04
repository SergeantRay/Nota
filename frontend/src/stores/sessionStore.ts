import { create } from "zustand";

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
  error: string | null;
  uploadProgress: number;

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
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: null,
  fileName: null,
  durationSec: null,
  status: null,
  progress: 0,
  error: null,
  uploadProgress: 0,

  setSession: (data) =>
    set({
      sessionId: data.sessionId,
      fileName: data.fileName,
      durationSec: data.durationSec,
      status: data.status,
      progress: 0,
      error: null,
      uploadProgress: 0,
    }),

  setStatus: (status, progress) => set({ status, progress }),

  setError: (error) => set({ error, status: "error" as SessionStatus }),

  setUploadProgress: (pct) => set({ uploadProgress: pct }),

  reset: () =>
    set({
      sessionId: null,
      fileName: null,
      durationSec: null,
      status: null,
      progress: 0,
      error: null,
      uploadProgress: 0,
    }),
}));
