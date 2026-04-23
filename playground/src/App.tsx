import { useState, useCallback } from 'react';
import { usePyodide } from './hooks/usePyodide';
import { SCENARIOS, DEFAULT_SCENARIO_ID, getScenario } from './scenarios';
import type { Scenario } from './scenarios';

import { LoadingOverlay } from './components/LoadingOverlay';
import { ScenarioPicker } from './components/ScenarioPicker';
import { FileTabBar } from './components/FileTabBar';
import { CodeEditor } from './components/CodeEditor';
import { ScoreBadge } from './components/ScoreBadge';
import { SignalHeatmap } from './components/SignalHeatmap';
import { DrilldownPanel } from './components/DrilldownPanel';

import type { Severity } from './types/drift';
import { deriveSignalStatuses } from './types/drift';

function App() {
  const { status, scanning, lastResult, lastError, runAnalysis } = usePyodide();

  // ── Scenario / file state ──────────────────────────────────────────────

  const [activeScenarioId, setActiveScenarioId] = useState(DEFAULT_SCENARIO_ID);
  const [files, setFiles] = useState<Record<string, string>>(
    () => getScenario(DEFAULT_SCENARIO_ID)!.files,
  );
  const [activeFile, setActiveFile] = useState<string>(
    () => Object.keys(getScenario(DEFAULT_SCENARIO_ID)!.files)[0],
  );

  // ── Signal selection ───────────────────────────────────────────────────

  const [selectedSignalAbbrev, setSelectedSignalAbbrev] = useState<string | null>(null);

  // ── Derived data from last analysis result ──────────────────────────────

  const signalStatuses = lastResult ? deriveSignalStatuses(lastResult) : [];
  const selectedSignal = signalStatuses.find((s) => s.abbrev === selectedSignalAbbrev) ?? null;
  const driftScore = lastResult?.drift_score ?? 0;
  const severity: Severity = (lastResult?.severity as Severity) ?? 'low';

  // ── Handlers ────────────────────────────────────────────────────────────

  const handleScenarioChange = useCallback(
    (id: string) => {
      const scenario = getScenario(id);
      if (!scenario) return;
      setActiveScenarioId(id);
      setFiles(scenario.files);
      setActiveFile(Object.keys(scenario.files)[0]);
      setSelectedSignalAbbrev(null);
    },
    [],
  );

  const handleFileEdit = useCallback(
    (value: string) => {
      setFiles((prev) => ({ ...prev, [activeFile]: value }));
    },
    [activeFile],
  );

  const handleSelectFile = useCallback((name: string) => setActiveFile(name), []);

  const handleAddFile = useCallback(() => {
    const name = window.prompt('New filename (e.g. models.py):');
    if (!name || name.trim() === '') return;
    const safe = name.trim().replace(/[^a-zA-Z0-9_.\-/]/g, '_');
    if (!safe) return;
    setFiles((prev) => {
      if (safe in prev) return prev;
      return { ...prev, [safe]: '' };
    });
    setActiveFile(safe);
  }, []);

  const handleRemoveFile = useCallback(
    (name: string) => {
      setFiles((prev) => {
        const next = { ...prev };
        delete next[name];
        const remaining = Object.keys(next);
        if (remaining.length > 0) {
          setActiveFile((cur) => (cur === name ? remaining[0] : cur));
        }
        return next;
      });
    },
    [],
  );

  const handleAnalyze = useCallback(() => {
    setSelectedSignalAbbrev(null);
    runAnalysis(files);
  }, [files, runAnalysis]);

  const activeScenario: Scenario =
    getScenario(activeScenarioId) ?? SCENARIOS[0];

  const isReady = status.state === 'ready';
  const canAnalyze = isReady && !scanning;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-drift-bg text-drift-text">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="flex shrink-0 items-center justify-between border-b border-drift-border bg-drift-panel px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-lg font-bold tracking-tight text-drift-text">
            drift
          </span>
          <span className="rounded-full border border-drift-accent/40 bg-drift-accent/10 px-2 py-0.5 font-mono text-xs font-medium text-drift-accent">
            playground
          </span>
        </div>

        <div className="flex items-center gap-4">
          <a
            href="https://mick-gsk.github.io/drift/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-drift-muted transition-colors hover:text-drift-text"
          >
            Docs
          </a>
          <a
            href="https://github.com/mick-gsk/drift"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm text-drift-muted transition-colors hover:text-drift-text"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            GitHub
          </a>
        </div>
      </header>

      {/* ── Scenario picker bar ────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-drift-border bg-drift-bg px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ScenarioPicker
            scenarios={SCENARIOS}
            activeId={activeScenarioId}
            onChange={handleScenarioChange}
          />
          <p className="text-xs text-drift-muted">{activeScenario.description}</p>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <main className="flex min-h-0 flex-1 gap-0">
        {/* ── Left: editor ─────────────────────────────────────────────── */}
        <div className="flex w-1/2 min-w-0 flex-col border-r border-drift-border">
          <FileTabBar
            files={files}
            activeFile={activeFile}
            onSelectFile={handleSelectFile}
            onAddFile={handleAddFile}
            onRemoveFile={handleRemoveFile}
          />

          <div className="min-h-0 flex-1">
            {activeFile && files[activeFile] !== undefined ? (
              <CodeEditor
                value={files[activeFile]}
                onChange={handleFileEdit}
                language="python"
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-drift-muted">
                No file selected.
              </div>
            )}
          </div>

          {/* Analyze button */}
          <div className="shrink-0 border-t border-drift-border bg-drift-panel p-3">
            <button
              onClick={handleAnalyze}
              disabled={!canAnalyze}
              className={`w-full rounded-md py-2.5 text-sm font-semibold transition-all duration-150 ${
                canAnalyze
                  ? 'bg-drift-accent text-white hover:bg-drift-accent/90'
                  : scanning
                  ? 'cursor-wait bg-drift-accent/50 text-white/70'
                  : 'cursor-not-allowed bg-drift-border text-drift-muted'
              }`}
            >
              {scanning ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                  Analysing…
                </span>
              ) : (
                '▶  Analyse'
              )}
            </button>

            {lastError && (
              <p className="mt-2 text-xs text-drift-critical">{lastError}</p>
            )}
          </div>
        </div>

        {/* ── Right: results ────────────────────────────────────────────── */}
        <div className="flex w-1/2 min-w-0 flex-col gap-0 overflow-y-auto">
          {lastResult ? (
            <div className="flex flex-col gap-4 p-4">
              {/* Score + heatmap */}
              <div className="flex items-start gap-5 rounded-lg border border-drift-border bg-drift-panel p-4">
                <ScoreBadge score={driftScore} severity={severity} />
                <div className="min-w-0 flex-1">
                  <SignalHeatmap
                    signals={signalStatuses}
                    selectedAbbrev={selectedSignalAbbrev}
                    onSelect={setSelectedSignalAbbrev}
                  />
                </div>
              </div>

              {/* Drilldown */}
              <DrilldownPanel signal={selectedSignal} />
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
              <div className="rounded-full border border-drift-border bg-drift-panel p-4 text-3xl">
                ◈
              </div>
              <div>
                <p className="font-medium text-drift-text">Run your first analysis</p>
                <p className="mt-1 text-sm text-drift-muted">
                  {isReady
                    ? 'Click "Analyse" to scan the scenario code with drift.'
                    : 'Waiting for Python runtime to load…'}
                </p>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ── Loading overlay (blocks UI until Pyodide is ready) ─────────── */}
      <LoadingOverlay status={status} />
    </div>
  );
}

export { App };
