"use client";

import { useEffect } from "react";

export type GraphKeyboardApi = {
  toggleFullscreen: () => void;
  /**
   * Called on Escape. Return true if fullscreen was actually exited so the
   * hook can preventDefault; return false when Escape should pass through
   * (e.g. not currently in fullscreen, so native handlers like dialog-close
   * still run).
   */
  exitFullscreen: () => boolean;
  expandAll: () => void;
  collapseAll: () => void;
};

/**
 * Wires the graph's keyboard shortcuts to a stable callback api:
 *   F    → toggleFullscreen
 *   Esc  → exitFullscreen  (only preventDefault when the caller reports it acted)
 *   E    → expandAll
 *   C    → collapseAll
 *
 * Keystrokes are ignored when focus is inside an input, textarea, or
 * contenteditable element so typing in notes/filters doesn't trip shortcuts.
 *
 * The caller is expected to memoize the `api` callbacks (e.g. via useCallback
 * or values from a context) so the keydown listener isn't re-installed on
 * every render.
 */
export function useGraphKeyboard(api: GraphKeyboardApi): void {
  const { toggleFullscreen, exitFullscreen, expandAll, collapseAll } = api;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        toggleFullscreen();
      } else if (e.key === "Escape") {
        const handled = exitFullscreen();
        if (handled) e.preventDefault();
      } else if (e.key === "e" || e.key === "E") {
        e.preventDefault();
        expandAll();
      } else if (e.key === "c" || e.key === "C") {
        e.preventDefault();
        collapseAll();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleFullscreen, exitFullscreen, expandAll, collapseAll]);
}
