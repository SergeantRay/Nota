import UploadZone from "./components/UploadZone";
import ProcessingStatus from "./components/ProcessingStatus";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-2xl font-bold tracking-tight text-white">Nota</h1>
        <p className="text-sm text-gray-500">Audio to sheet music</p>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 p-6">
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Upload
          </h2>
          <UploadZone />
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Processing
          </h2>
          <ProcessingStatus />
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Score
          </h2>
          <div className="rounded-lg border border-dashed border-gray-800 p-8 text-center text-sm text-gray-600">
            Score will appear here after processing
          </div>
        </section>
      </main>
    </div>
  );
}
