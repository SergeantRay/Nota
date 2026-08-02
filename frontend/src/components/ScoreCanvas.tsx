import { useEffect, useRef, useState } from "react";
import { useSessionStore, type LayerKey, type LayerState } from "../stores/sessionStore";
import { renderScore } from "../rendering/scoreBuilder";

const visibleMap = (layers: Record<LayerKey, LayerState>): Record<LayerKey, boolean> => ({
  percussion: layers.percussion.visible,
  bass: layers.bass.visible,
  other: layers.other.visible,
  melody: layers.melody.visible,
});

export default function ScoreCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scoreData, layers } = useSessionStore();
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    if (!containerRef.current || !scoreData) return;
    renderScore(containerRef.current, scoreData, visibleMap(layers));
  }, [scoreData, layers, zoom]);

  useEffect(() => {
    return () => {
      if (containerRef.current) containerRef.current.innerHTML = "";
    };
  }, []);

  if (!scoreData) {
    return (
      <div className="rounded-lg border border-dashed border-gray-800 p-8 text-center text-sm text-gray-600">
        Score will appear here after processing
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900">
      {/* Zoom controls */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
        <div className="flex items-center gap-3 text-sm">
          <span className="text-gray-400">
            Key of <span className="text-white font-semibold">{scoreData.keySignature}</span>
          </span>
          <span className="text-gray-400">
            Tempo <span className="text-white font-semibold">{scoreData.tempo} BPM</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))}
            className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400 hover:bg-gray-700 transition"
          >
            −
          </button>
          <span className="text-xs text-gray-500 w-8 text-center">{Math.round(zoom * 100)}%</span>
          <button
            onClick={() => setZoom((z) => Math.min(2, z + 0.1))}
            className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400 hover:bg-gray-700 transition"
          >
            +
          </button>
        </div>
      </div>

      {/* Score render area */}
      <div
        className="overflow-auto p-4"
        style={{ maxHeight: "calc(100vh - 200px)" }}
      >
        <div
          ref={containerRef}
          id="score-container"
          className="min-w-0"
          style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}
        />
      </div>
    </div>
  );
}
