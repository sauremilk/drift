/**
 * Phase 2 stub — automatic live analysis with debounce.
 *
 * TODO(phase-2): Implement auto-analysis that triggers on code edits.
 * Design:
 *   - useDebounce(files, 1200ms) to delay until the user pauses typing
 *   - Call runAnalysis() automatically when debounced files change
 *
 * Prerequisite: Move runScan() into a dedicated Web Worker so Pyodide
 * execution doesn't block the main thread and freeze the Monaco editor.
 * See src/workers/pyodide.worker.ts (Phase 2 TODO).
 *
 * Risk: even with debounce, scan duration (2–8s in Pyodide) makes live
 * feedback feel sluggish. Consider showing a "stale" indicator instead
 * of a full loading spinner between keystrokes.
 */

// eslint-disable-next-line @typescript-eslint/no-empty-function
export function useDebounceAnalysis(): void {
  // Phase 2 stub — not implemented
}
