import { useSessionStore } from "../stores/sessionStore";
import { getScorePlayer } from "../audio/ScorePlayer";
import { useEffect, useRef } from "react";

export default function PlaybackControls() {
  const { scoreData, isPlaying, tempo, setTempo, setPlaybackState, layers } = useSessionStore();
  const playerRef = useRef(getScorePlayer());

  // Load score when it changes
  useEffect(() => {
    if (scoreData && scoreData.layers.melody.notes.length > 0) {
      playerRef.current.loadScore(scoreData);
      playerRef.current.onPlaybackState((state) => {
        setPlaybackState(state);
      });
    }
  }, [scoreData, setPlaybackState]);

  // Update tempo
  useEffect(() => {
    playerRef.current.setTempo(tempo);
  }, [tempo]);

  // Update mute states
  useEffect(() => {
    for (const [layerId, state] of Object.entries(layers)) {
      playerRef.current.setLayerMuted(layerId as keyof typeof layers, state.muted);
    }
  }, [layers]);

  if (!scoreData || scoreData.layers.melody.notes.length === 0) {
    return (
      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Playback</h3>
        <p className="text-xs text-gray-600">No notes to play</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Playback</h3>

      <div className="flex items-center gap-2">
        <button
          onClick={() => playerRef.current.play()}
          className="rounded bg-gray-700 px-3 py-1 text-xs text-gray-300 hover:bg-gray-600 transition"
          title="Play"
        >
          ▶
        </button>
        <button
          onClick={() => playerRef.current.pause()}
          className="rounded bg-gray-700 px-3 py-1 text-xs text-gray-300 hover:bg-gray-600 transition"
          title="Pause"
        >
          ⏸
        </button>
        <button
          onClick={() => playerRef.current.stop()}
          className="rounded bg-gray-700 px-3 py-1 text-xs text-gray-300 hover:bg-gray-600 transition"
          title="Stop"
        >
          ⏹
        </button>
      </div>

      {isPlaying && (
        <p className="text-xs text-green-400">Playing...</p>
      )}

      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Tempo:</span>
        <span className="text-sm text-gray-200 font-mono">{tempo} BPM</span>
      </div>

      <div>
        <input
          type="range"
          min={40}
          max={300}
          value={tempo}
          onChange={(e) => setTempo(Number(e.target.value))}
          className="w-full accent-blue-500"
        />
        <div className="flex justify-between text-[10px] text-gray-600">
          <span>40</span>
          <span>300</span>
        </div>
      </div>
    </div>
  );
}
