import { useSessionStore } from "../stores/sessionStore";

const STAGE_LABELS: Record<string, string> = {
  "separating:starting": "Loading model...",
  "separating:cpu_warning": "No GPU detected — processing on CPU (this will be slower)",
  "separating:running_demucs": "Running Demucs...",
  "separating:running_demucs_subprocess": "Running Demucs (subprocess)...",
  "separating:model_loaded": "Model loaded — separating stems...",
  "separating:saving_stems": "Saving stems...",
  "separating:collecting_output": "Collecting output...",
  "separating:complete": "Separation complete",
  "detecting:starting": "Starting pitch detection...",
  "detecting:percussion": "Detecting percussion onsets...",
  "detecting:bass": "Detecting bass notes...",
  "detecting:other": "Detecting tenor/alto notes...",
  "detecting:melody": "Detecting melody notes...",
  "detecting:done": "Pitch detection complete",
  "detecting:complete": "Pitch detection complete",
  "postprocessing:starting": "Analyzing tempo and key...",
  "postprocessing:tempo_detected": "Tempo detected",
  "postprocessing:key_detected": "Key signature detected",
  "postprocessing:quantized": "Quantizing notes...",
  "postprocessing:voices_separated": "Separating voices...",
  "postprocessing:complete": "Post-processing complete",
};

export default function ProcessingStatus() {
  const { sessionId, status, progress, stage } = useSessionStore();

  if (!sessionId || status === "uploaded") return null;

  const displayLabel =
    STAGE_LABELS[stage] ?? status?.replace(/^./, (c) => c.toUpperCase()) ?? "";
  const pct = Math.round(progress * 100);

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm">
      <div className="flex items-center justify-between">
        <span className="text-gray-300">{displayLabel || "Processing..."}</span>
        <span className="text-gray-500">{pct}%</span>
      </div>
      <div className="mt-2 h-2 w-full rounded bg-gray-800">
        <div
          className="h-2 rounded bg-blue-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      {status === "complete" && (
        <p className="mt-2 text-green-400">Processing complete. Ready for next step.</p>
      )}
      {status === "error" && (
        <p className="mt-2 text-red-400">
          {useSessionStore.getState().error || "An error occurred during processing."}
        </p>
      )}
    </div>
  );
}
