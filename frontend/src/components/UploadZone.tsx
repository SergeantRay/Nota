import { useCallback, useRef, useState } from "react";
import { uploadAudio, startProcessing, ApiError } from "../api/client";
import { useSessionStore } from "../stores/sessionStore";

const ALLOWED_TYPES = [".wav", ".mp3", ".flac"];
const MAX_SIZE = 100 * 1024 * 1024; // 100 MB

export default function UploadZone() {
  const { sessionId, uploadProgress, setSession, setUploadProgress, setError, startPolling } =
    useSessionStore();
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndUpload = useCallback(
    async (file: File) => {
      setLocalError(null);
      const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
      if (!ALLOWED_TYPES.includes(ext)) {
        setLocalError(`Unsupported format. Please use ${ALLOWED_TYPES.join(", ")}`);
        return;
      }
      if (file.size > MAX_SIZE) {
        setLocalError(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max: 100 MB`);
        return;
      }

      setUploading(true);
      try {
        const result = await uploadAudio(file, setUploadProgress);
        setSession({
          sessionId: result.session_id,
          fileName: result.file_name,
          durationSec: result.duration_sec,
          status: result.status as "uploaded",
        });
        startProcessing(result.session_id);
        startPolling();
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Upload failed";
        setLocalError(msg);
        setError(msg);
      } finally {
        setUploading(false);
      }
    },
    [setSession, setUploadProgress, setError],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) validateAndUpload(file);
    },
    [validateAndUpload],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) validateAndUpload(file);
    },
    [validateAndUpload],
  );

  if (sessionId) {
    return (
      <div className="rounded-lg border border-green-800 bg-green-950/30 p-4 text-sm">
        <p className="truncate text-green-400">
          Uploaded: <span className="font-medium">{useSessionStore.getState().fileName}</span>
        </p>
        <p className="mt-1 text-gray-400">
          {useSessionStore.getState().durationSec?.toFixed(1)}s
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
          dragOver
            ? "border-blue-400 bg-blue-950/30"
            : "border-gray-700 hover:border-gray-500"
        }`}
      >
        <p className="text-gray-400 text-sm">
          {uploading
            ? `Uploading... ${uploadProgress}%`
            : dragOver
              ? "Drop your audio file here"
              : "Drop WAV, MP3, or FLAC here"}
        </p>
        {uploading && (
          <div className="mt-3 h-2 w-full rounded bg-gray-800">
            <div
              className="h-2 rounded bg-blue-500 transition-all"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".wav,.mp3,.flac"
          onChange={handleFileChange}
          className="hidden"
        />
      </div>
      {localError && (
        <p className="rounded bg-red-950/40 px-3 py-2 text-sm text-red-400">
          {localError}
        </p>
      )}
    </div>
  );
}
