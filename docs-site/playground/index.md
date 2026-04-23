---
title: "Interactive Playground"
description: "Run drift against Python code directly in your browser — no installation, no sign-up."
---

# Interactive Playground

Run drift against Python code directly in your browser — no Python installation, no sign-up.

**[→ Open the Playground](https://mick-gsk.github.io/drift/playground/)**

---

## What you can do

- **Choose a scenario** — four realistic code patterns (God Class, Circular Dependencies, Dead Code, Clean Architecture)
- **Edit the Python files** live in a Monaco editor
- **Click Analyse** — drift runs entirely in the browser via WebAssembly (Pyodide)
- **Explore the signal heatmap** — click any tile to drill into findings

## How it works

The playground uses [Pyodide](https://pyodide.org/) to run CPython 3.11 in the browser. On first load it downloads the Python runtime (~20 MB, cached by the browser) and installs `drift-analyzer` via `micropip`. Subsequent visits start in seconds.

!!! note "Two signals excluded"
    `TVS` and `SMS` require git history, which is not available in the browser. All other 23 signals run normally.
