import { useSessionStore } from "../stores/sessionStore";

export default function ScorePlaceholder() {
  const { scoreData, status } = useSessionStore();

  if (!scoreData) {
    if (status === "complete") {
      return (
        <div className="rounded-lg border border-dashed border-gray-800 p-8 text-center text-sm text-gray-500">
          Processing complete but no score data available. Try re-processing.
        </div>
      );
    }
    return (
      <div className="rounded-lg border border-dashed border-gray-800 p-8 text-center text-sm text-gray-600">
        Score will appear here after processing
      </div>
    );
  }

  const layerEntries = Object.entries(scoreData.layers) as [
    string,
    { notes: unknown[]; instrumentName: string },
  ][];
  const totalNotes = layerEntries.reduce((sum, [, l]) => sum + l.notes.length, 0);

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
      <div className="mb-4 flex items-center gap-4 text-sm">
        <span className="text-gray-300">
          Key of <span className="text-white font-semibold">{scoreData.keySignature}</span>
        </span>
        <span className="text-gray-300">
          Tempo{" "}
          <span className="text-white font-semibold">{scoreData.tempo} BPM</span>
        </span>
        <span className="text-gray-300">
          {totalNotes} <span className="text-gray-500">notes</span>
        </span>
      </div>

      <div className="rounded-lg border border-gray-800 bg-gray-950 p-8">
        {/* VexFlow canvas will mount here in Part 7 */}
        <div className="text-center text-sm text-gray-500">
          <p className="mb-2">Score ready — VexFlow rendering coming in Part 7</p>
          <div className="space-y-1 text-xs text-gray-600">
            {layerEntries.map(([layerId, layer]) => (
              <p key={layerId}>
                {layer.instrumentName}: {layer.notes.length} notes
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
