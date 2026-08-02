import UploadZone from "./components/UploadZone";
import ProcessingStatus from "./components/ProcessingStatus";
import LayerControls from "./components/LayerControls";
import PlaybackControls from "./components/PlaybackControls";
import ScoreCanvas from "./components/ScoreCanvas";
import { useSessionStore } from "./stores/sessionStore";

export default function App() {
  const isComplete = useSessionStore((s) => s.status === "complete");

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="flex items-center justify-between border-b border-gray-800 px-6 py-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">Nota</h1>
          <p className="text-xs text-gray-500">Audio to sheet music</p>
        </div>
        {isComplete && (
          <button
            onClick={() => useSessionStore.getState().reset()}
            className="rounded border border-gray-700 px-3 py-1 text-xs text-gray-400 hover:bg-gray-800 transition"
          >
            New Upload
          </button>
        )}
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="w-56 shrink-0 border-r border-gray-800 p-4 space-y-6 min-h-[calc(100vh-53px)]">
          <UploadZone />
          <ProcessingStatus />
          <LayerControls />
          <PlaybackControls />
        </aside>

        {/* Main score area */}
        <main className="flex-1 p-6 overflow-auto">
          <ScoreCanvas />
        </main>
      </div>
    </div>
  );
}
