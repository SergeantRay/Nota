import UploadZone from "./components/UploadZone";
import ProcessingStatus from "./components/ProcessingStatus";
import LayerControls from "./components/LayerControls";
import PlaybackControls from "./components/PlaybackControls";
import ScoreCanvas from "./components/ScoreCanvas";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useSessionStore } from "./stores/sessionStore";
import { useState } from "react";

export default function App() {
  const isComplete = useSessionStore((s) => s.status === "complete");
  const isProcessing = useSessionStore((s) => s.isProcessing);
  const error = useSessionStore((s) => s.error);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useKeyboardShortcuts();

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="flex items-center justify-between border-b border-gray-800 px-4 sm:px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className="rounded p-1 text-xs text-gray-500 hover:bg-gray-800 hover:text-gray-300 transition lg:hidden"
          >
            {sidebarOpen ? "✕" : "☰"}
          </button>
          <div>
            <h1 className="text-lg sm:text-xl font-bold tracking-tight text-white">Nota</h1>
            <p className="text-xs text-gray-500">Audio to sheet music</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isProcessing && (
            <span className="text-xs text-blue-400 animate-pulse hidden sm:inline">Processing...</span>
          )}
          {isComplete && (
            <button
              onClick={() => useSessionStore.getState().reset()}
              className="rounded border border-gray-700 px-3 py-1 text-xs text-gray-400 hover:bg-gray-800 transition"
            >
              New Upload
            </button>
          )}
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="border-b border-red-900 bg-red-950 px-4 py-2 text-center text-xs text-red-400">
          {error}
          <button
            onClick={() => useSessionStore.getState().reset()}
            className="ml-3 underline hover:text-red-300"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="flex">
        {/* Sidebar */}
        <aside
          className={`${
            sidebarOpen ? "block" : "hidden"
          } lg:block w-full lg:w-56 shrink-0 border-r border-gray-800 p-4 space-y-6 min-h-[calc(100vh-53px)] overflow-y-auto`}
        >
          <UploadZone />
          <ProcessingStatus />
          <LayerControls />
          <PlaybackControls />
        </aside>

        {/* Main score area */}
        <main className={`${sidebarOpen ? "hidden" : "block"} lg:block flex-1 p-4 sm:p-6 overflow-auto`}>
          <ScoreCanvas />
        </main>
      </div>
    </div>
  );
}
