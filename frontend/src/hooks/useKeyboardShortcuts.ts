import { useEffect } from "react";
import { useSessionStore, type LayerKey } from "../stores/sessionStore";
import { getScorePlayer } from "../audio/ScorePlayer";

const LAYER_KEYS: LayerKey[] = ["percussion", "bass", "other", "melody"];

export function useKeyboardShortcuts() {
  const store = useSessionStore;
  const player = getScorePlayer();

  useEffect(() => {
    function handle(e: KeyboardEvent) {
      // Don't capture when in an input
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      const state = store.getState();

      switch (e.key) {
        case " ":
          e.preventDefault();
          if (!state.scoreData) break;
          if (state.isPlaying) {
            player.pause();
          } else {
            player.play();
          }
          break;
        case "1":
        case "2":
        case "3":
        case "4": {
          const idx = Number(e.key) - 1;
          const layer = LAYER_KEYS[idx];
          if (layer) {
            if (e.shiftKey) {
              store.getState().toggleLayerSolo(layer);
            } else if (e.metaKey || e.ctrlKey) {
              store.getState().toggleLayerMuted(layer);
            } else {
              store.getState().toggleLayerVisible(layer);
            }
          }
          break;
        }
        case "m":
        case "M": {
          // Mute the first visible layer or toggle all
          const layers = store.getState().layers;
          const firstVisible = LAYER_KEYS.find((k) => layers[k].visible);
          if (firstVisible) {
            store.getState().toggleLayerMuted(firstVisible);
          }
          break;
        }
        case "s":
        case "S": {
          const layers = store.getState().layers;
          const firstVisible = LAYER_KEYS.find((k) => layers[k].visible);
          if (firstVisible) {
            store.getState().toggleLayerSolo(firstVisible);
          }
          break;
        }
      }
    }

    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);
}
