import { StrictMode, Component, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <h1 className="text-lg font-bold text-red-400 mb-2">Something went wrong</h1>
            <pre className="text-xs text-gray-500 bg-gray-900 rounded p-3 overflow-auto max-h-40 text-left">
              {this.state.error.message}
            </pre>
            <button
              onClick={() => {
                this.setState({ error: null });
                window.location.reload();
              }}
              className="mt-4 rounded border border-gray-700 px-4 py-1.5 text-sm text-gray-400 hover:bg-gray-800 transition"
            >
              Retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
