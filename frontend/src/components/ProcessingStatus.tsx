import { useEffect, useRef } from "react";
import { getSession } from "../api/client";
import { useSessionStore } from "../stores/sessionStore";
import type { SessionStatus } from "../stores/sessionStore";

const STAGES: SessionStatus[] = [
  "uploaded",
  "preprocessing",
  "separating",
  "detecting",
  "postprocessing",
  "assembling",
  "complete",
];

export default function ProcessingStatus() {
  const { sessionId, status, progress, setStatus, setError } = useSessionStore();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!sessionId || status === "complete" || status === "error") return;

    const poll = () => {
      getSession(sessionId)
        .then((data) => {
          setStatus(data.status as SessionStatus, data.progress);
          if (data.status === "error" && data.error) {
            setError(data.error);
          }
        })
        .catch(() => {
          // silently retry on next poll
        });
    };

    intervalRef.current = setInterval(poll, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [sessionId, status, setStatus, setError]);

  if (!sessionId) return null;

  const stageIndex = STAGES.indexOf(status ?? "uploaded");
  const displayStage = status === "complete" ? "complete" : status ?? "uploaded";

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm">
      <div className="flex items-center justify-between">
        <span className="text-gray-300 capitalize">{displayStage}</span>
        <span className="text-gray-500">{Math.round(progress)}%</span>
      </div>
      <div className="mt-2 h-2 w-full rounded bg-gray-800">
        <div
          className="h-2 rounded bg-blue-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
