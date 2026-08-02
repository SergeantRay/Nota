import { useEffect, useRef, useState, useCallback } from "react";
import { useSessionStore, type LayerKey, type LayerState } from "../stores/sessionStore";
import { renderPianoRoll } from "../rendering/pianoRoll";

const visibleMap = (layers: Record<LayerKey, LayerState>): Record<string, boolean> => ({
  percussion: layers.percussion.visible,
  bass: layers.bass.visible,
  other: layers.other.visible,
  melody: layers.melody.visible,
});

export default function ScoreCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { scoreData, layers } = useSessionStore();
  const [activeLayer, setActiveLayer] = useState<LayerKey | null>(null);

  const handleNoteClick = useCallback((layer: string, noteIdx: number) => {
    setActiveLayer((prev) => (prev === layer ? null : layer as LayerKey));
  }, []);

  useEffect(() => {
    if (!scoreData) return;

    const resize = () => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;
      canvas.width = container.clientWidth;
      canvas.height = Math.max(container.clientHeight, 400);
      renderPianoRoll(canvas, scoreData, visibleMap(layers), activeLayer, handleNoteClick);
    };

    resize();
    const obs = new ResizeObserver(resize);
    if (containerRef.current) obs.observe(containerRef.current);
    window.addEventListener("resize", resize);
    return () => {
      obs.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [scoreData, layers, activeLayer, handleNoteClick]);

  if (!scoreData) {
    return (
      <div className="rounded-lg border border-dashed border-gray-800 p-8 text-center text-sm text-gray-600">
        Score will appear here after processing
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-400">
            Key of <span className="text-white font-semibold">{scoreData.keySignature}</span>
          </span>
          <span className="text-gray-400">
            Tempo <span className="text-white font-semibold">{scoreData.tempo} BPM</span>
          </span>
          <span className="text-gray-400">
            Time <span className="text-white font-semibold">{scoreData.timeSignature.join("/")}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          {activeLayer && (
            <span className="text-xs text-gray-500">
              Filtered to <span className="text-white">{activeLayer}</span>
              <button
                onClick={() => setActiveLayer(null)}
                className="ml-2 underline hover:text-gray-300"
              >
                clear
              </button>
            </span>
          )}
        </div>
      </div>

      {/* Piano roll */}
      <div
        ref={containerRef}
        className="w-full"
        style={{ height: "calc(100vh - 240px)", minHeight: 400 }}
      >
        <canvas
          ref={canvasRef}
          className="w-full h-full"
        />
      </div>
    </div>
  );
}
