import { useSessionStore, type LayerKey } from "../stores/sessionStore";

const LAYERS: { key: LayerKey; label: string; color: string }[] = [
  { key: "percussion", label: "Percussion", color: "bg-yellow-500" },
  { key: "bass", label: "Bass", color: "bg-blue-500" },
  { key: "other", label: "Tenor / Alto", color: "bg-purple-500" },
  { key: "melody", label: "Melody", color: "bg-pink-500" },
];

export default function LayerControls() {
  const { layers, toggleLayerVisible, toggleLayerMuted, toggleLayerSolo, scoreData } =
    useSessionStore();

  if (!scoreData) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Layers</h3>
      {LAYERS.map(({ key, label, color }) => {
        const state = layers[key];
        return (
          <div
            key={key}
            className="flex items-center gap-2 rounded border border-gray-800 bg-gray-900 px-3 py-2"
          >
            <div className={`h-3 w-3 rounded-sm ${color}`} />
            <span className="flex-1 text-sm text-gray-300">{label}</span>
            <button
              onClick={() => toggleLayerVisible(key)}
              className={`rounded px-2 py-0.5 text-xs transition ${
                state.visible
                  ? "bg-gray-700 text-gray-200"
                  : "bg-gray-800 text-gray-600"
              }`}
              title={state.visible ? "Hide" : "Show"}
            >
              {state.visible ? "👁" : "—"}
            </button>
            <button
              onClick={() => toggleLayerMuted(key)}
              className={`rounded px-2 py-0.5 text-xs transition ${
                state.muted ? "bg-red-900 text-red-400" : "bg-gray-700 text-gray-200"
              }`}
              title={state.muted ? "Unmute" : "Mute"}
            >
              M
            </button>
            <button
              onClick={() => toggleLayerSolo(key)}
              className={`rounded px-2 py-0.5 text-xs transition ${
                state.solo ? "bg-yellow-700 text-yellow-300" : "bg-gray-700 text-gray-200"
              }`}
              title={state.solo ? "Unsolo" : "Solo"}
            >
              S
            </button>
          </div>
        );
      })}
    </div>
  );
}
