# drift playground

Browser-based interactive demo for [drift-analyzer](https://github.com/mick-gsk/drift) — no installation required.

**Live:** https://mick-gsk.github.io/drift/playground/

## What it does

Runs drift against Python code directly in the browser using [Pyodide](https://pyodide.org/) (CPython 3.11 compiled to WebAssembly). Users can:

- Select from four pre-built scenarios that demonstrate different architectural patterns
- Edit or add Python files in a Monaco editor
- Click **Analyse** to run drift and see a signal heatmap + drilldown panel
- All without installing Python or drift locally

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript |
| Build | Vite 5 |
| Editor | Monaco Editor (loaded from CDN) |
| Styling | Tailwind CSS 3.4 (dark terminal theme) |
| Python runtime | Pyodide 0.26.4 (WebAssembly) |
| Hosting | GitHub Pages (`site/playground/`) |

## Local development

```bash
cd playground
npm install
npm run dev
```

The dev server runs at `http://localhost:5173`. Pyodide loads from CDN on first visit (~20 MB, cached by the browser).

> **Note:** On first load Pyodide downloads `micropip` and installs `drift-analyzer`. Subsequent page reloads use the browser cache.

## Build

```bash
npm run build
# Output in playground/dist/
# GitHub Actions copies this to site/playground/ during the docs deploy
```

The Vite base path is `/drift/playground/` (matching the GitHub Pages URL). To test the production build locally:

```bash
npm run preview
# Runs at http://localhost:4173/drift/playground/
```

## Adding a scenario

1. Create `src/scenarios/my-scenario.ts` following the `Scenario` interface:
   ```typescript
   import type { Scenario } from './index';

   export const myScenario: Scenario = {
     id: 'my-scenario',          // URL-safe identifier
     label: 'My Scenario',       // Button label in the picker
     description: 'One sentence.',
     files: {
       'app.py': `# Python source...`,
     },
   };
   ```
2. Import and add it to `SCENARIOS` in `src/scenarios/index.ts`.

## Excluded signals

The following signals are excluded in the browser because they require git history (subprocess not available in Pyodide):

- **TVS** — Test velocity signal
- **SMS** — Stale module signal  
- **CCS** — Contributor concentration signal

Excluded via `exclude_signals=["TVS", "SMS", "CCS"]` in `pyodide-runner.ts`.

## Updating the Pyodide version

1. Update `PYODIDE_CDN` in `src/utils/pyodide-runner.ts` to the new version URL.
2. Verify that `drift-analyzer` and its dependencies (pydantic, click, etc.) are available in the new Pyodide package set: https://pyodide.org/en/stable/usage/packages-in-pyodide.html
3. Test locally with `npm run dev`.

## GitHub Pages deployment

The playground is built as part of the docs workflow (`.github/workflows/docs.yml`). Pushes to `main` that touch `playground/**` trigger a rebuild. The build output lands at `site/playground/` alongside the MkDocs output.
