/**
 * Pyodide runner — singleton that loads the Python runtime and drift-analyzer
 * into the browser, then exposes runScan() for analysis requests.
 *
 * Pyodide CDN version is pinned here; update when upgrading.
 * Phase 2: move runScan into a dedicated Web Worker to avoid UI freezes.
 */

const PYODIDE_VERSION = '0.26.4';
const PYODIDE_INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

export type PyodideStatus =
  | { state: 'idle' }
  | { state: 'loading-runtime'; message: string }
  | { state: 'installing-drift'; message: string }
  | { state: 'ready' }
  | { state: 'error'; message: string };

export type ScanFiles = Record<string, string>;

// Minimal Pyodide interface — only the subset we use
interface PyodideInterface {
  runPythonAsync: (code: string) => Promise<unknown>;
  globals: { set: (key: string, value: unknown) => void };
  toPy: (value: unknown) => unknown;
  loadPackage: (pkgs: string | string[]) => Promise<void>;
}

declare global {
  interface Window {
    loadPyodide: (config: { indexURL: string }) => Promise<PyodideInterface>;
  }
}

let _pyodide: PyodideInterface | null = null;
let _initPromise: Promise<PyodideInterface> | null = null;

function injectPyodideScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    // Avoid double-injection
    if (document.querySelector('script[data-pyodide]')) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = `${PYODIDE_INDEX_URL}pyodide.js`;
    script.setAttribute('data-pyodide', 'true');
    script.crossOrigin = 'anonymous';
    script.onload = () => resolve();
    script.onerror = () =>
      reject(new Error(`Failed to load Pyodide ${PYODIDE_VERSION} from CDN. Check your network connection.`));
    document.head.appendChild(script);
  });
}

export async function initPyodide(
  onStatus: (s: PyodideStatus) => void,
): Promise<PyodideInterface> {
  if (_pyodide) return _pyodide;
  if (_initPromise) return _initPromise;

  _initPromise = (async () => {
    try {
      onStatus({ state: 'loading-runtime', message: `Loading Python ${PYODIDE_VERSION} runtime (~20 MB)…` });
      await injectPyodideScript();
      const py = await window.loadPyodide({ indexURL: PYODIDE_INDEX_URL });

      onStatus({ state: 'installing-drift', message: 'Installing drift-analyzer via micropip…' });
      await py.loadPackage(['micropip']);
      await py.runPythonAsync(`
import micropip
# keep_going=True: tolerate optional deps that don't have Pyodide wheels
await micropip.install("drift-analyzer", keep_going=True)
`);

      // Smoke-test the import path we'll use later
      await py.runPythonAsync(`
from drift.api import scan as _drift_scan
print("drift-analyzer import OK")
`);

      _pyodide = py;
      onStatus({ state: 'ready' });
      return py;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      onStatus({ state: 'error', message });
      _initPromise = null; // allow retry
      throw err;
    }
  })();

  return _initPromise;
}

// Python script that writes the virtual filesystem and runs the scan.
// Variables _playground_files is injected via pyodide.globals before execution.
const SCAN_SCRIPT = `
import json
import os
import shutil

_work_dir = "/playground_code"

# Clean up from any previous run
if os.path.exists(_work_dir):
    shutil.rmtree(_work_dir)
os.makedirs(_work_dir)

# Write user files into Pyodide's in-memory filesystem
for _fname, _content in _playground_files.items():
    _filepath = os.path.join(_work_dir, _fname)
    _parent = os.path.dirname(_filepath)
    if _parent and not os.path.exists(_parent):
        os.makedirs(_parent, exist_ok=True)
    with open(_filepath, "w", encoding="utf-8") as _fh:
        _fh.write(_content)

# Run drift analysis.
# Git-history signals (TVS, SMS, CCS) are excluded because the browser
# has no access to a git repository. The remaining ~19 signals run normally.
from drift.api import scan as _drift_scan
_result = _drift_scan(
    path=_work_dir,
    exclude_signals=["TVS", "SMS", "CCS"],
    max_findings=30,
)

_scan_output = json.dumps(_result)
`;

export async function runScan(files: ScanFiles): Promise<unknown> {
  if (!_pyodide) throw new Error('Pyodide is not ready. Call initPyodide() first.');

  // Pass files dict into Python globals before running the script
  _pyodide.globals.set('_playground_files', _pyodide.toPy(files));
  await _pyodide.runPythonAsync(SCAN_SCRIPT);
  const raw = await _pyodide.runPythonAsync('_scan_output');
  return JSON.parse(raw as string);
}
