const API_BASE = "http://localhost:8000";

export interface UploadResponse {
  session_id: string;
  file_name: string;
  duration_sec: number;
  sample_rate: number;
  channels: number;
  status: string;
}

export interface SessionResponse {
  session_id: string;
  file_name: string;
  duration_sec: number;
  sample_rate: number;
  channels: number;
  status: string;
  progress: number;
  stage: string;
  error: string | null;
  stem_paths: Record<string, string> | null;
  tempo: number | null;
  key_signature: string | null;
}

export interface ScoreResponse {
  session_id: string;
  tempo: number;
  key_signature: string;
  score_json: Record<string, unknown>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, init);
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(res.status, detail.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export function uploadAudio(file: File, onProgress?: (pct: number) => void) {
  return new Promise<UploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/upload`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as UploadResponse);
      } else {
        try {
          const err = JSON.parse(xhr.responseText) as { detail?: string };
          reject(new ApiError(xhr.status, err.detail ?? xhr.statusText));
        } catch {
          reject(new ApiError(xhr.status, xhr.statusText));
        }
      }
    };

    xhr.onerror = () => reject(new ApiError(0, "Network error"));
    xhr.ontimeout = () => reject(new ApiError(0, "Upload timed out"));

    const formData = new FormData();
    formData.append("file", file);
    xhr.send(formData);
  });
}

export function getSession(sessionId: string) {
  return request<SessionResponse>(`/api/session/${sessionId}`);
}

export function startProcessing(sessionId: string) {
  return request<{ session_id: string; status: string; message: string }>(
    `/api/session/${sessionId}/process`,
    { method: "POST" },
  );
}

export function getScore(sessionId: string) {
  return request<ScoreResponse>(`/api/session/${sessionId}/score`);
}
