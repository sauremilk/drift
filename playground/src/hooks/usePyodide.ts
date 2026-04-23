import { useState, useEffect, useCallback, useRef } from 'react';
import {
  initPyodide,
  runScan,
  type PyodideStatus,
  type ScanFiles,
} from '../utils/pyodide-runner';
import type { DriftOutput } from '../types/drift';

export interface UsePyodideReturn {
  status: PyodideStatus;
  scanning: boolean;
  lastResult: DriftOutput | null;
  lastError: string | null;
  runAnalysis: (files: ScanFiles) => Promise<void>;
}

export function usePyodide(): UsePyodideReturn {
  const [status, setStatus] = useState<PyodideStatus>({ state: 'idle' });
  const [scanning, setScanning] = useState(false);
  const [lastResult, setLastResult] = useState<DriftOutput | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const initialized = useRef(false);

  // Start Pyodide initialization once on mount
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    initPyodide(setStatus).catch(() => {
      // Error state is already set via the onStatus callback
    });
  }, []);

  const runAnalysis = useCallback(
    async (files: ScanFiles) => {
      if (status.state !== 'ready') return;
      setScanning(true);
      setLastError(null);
      try {
        const result = await runScan(files);
        setLastResult(result as DriftOutput);
      } catch (err) {
        setLastError(err instanceof Error ? err.message : String(err));
      } finally {
        setScanning(false);
      }
    },
    [status.state],
  );

  return { status, scanning, lastResult, lastError, runAnalysis };
}
