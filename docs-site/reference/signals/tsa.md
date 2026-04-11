# TypeScript Architecture Signal (TSA)

**Signal ID:** `TSA`  
**Full name:** TypeScript Architecture  
**Type:** Report-only signal (weight 0.0 — does not contribute to drift score)  
**Default weight:** `0.0`  
**Scope:** cross_file

---

## What TSA detects

TSA runs **four TypeScript/JavaScript architecture rules** to detect structural problems in frontend and Node.js codebases:

1. **Circular module detection** — modules importing each other directly or transitively.
2. **Cross-package import ban** — direct imports between packages in a monorepo (bypassing package boundaries).
3. **Layer-leak detection** — imports that violate configured layer boundaries (similar to AVS for Python).
4. **UI-to-infrastructure import ban** — UI components importing directly from infrastructure/database layers.

### Example finding

```
ts_architecture in src/components/UserList.tsx
  Rule: ui_to_infra_import_ban
  Import: import { query } from '../database/connection'
  → UI component directly accessing database layer
```

---

## Why TypeScript architecture rules matter

- **Full-stack drift** — frontend and backend code erode differently; TSA covers the JavaScript/TypeScript side.
- **Monorepo boundary violations** — in monorepos, cross-package imports bypass the package contract.
- **Circular dependencies** — cause cryptic runtime errors and import timing issues in Node.js.
- **AI-generated frontend code** often ignores architectural boundaries, importing the shortest path.

---

## Status

TSA is **report-only** (weight `0.0`) until precision and recall have been validated across diverse TypeScript repositories. Findings appear in reports but do not affect the drift score.

---

## Configuration

```yaml
# drift.yaml
weights:
  ts_architecture: 0.0   # report-only (set > 0.0 to make scoring-active)
```

To activate TSA for scoring, set the weight to a positive value after validating its precision in your codebase.

---

## Detection details

1. **Parse TypeScript/JavaScript imports** using regex-based extraction (no TS compiler required).
2. **Build import graph** across all `.ts`, `.tsx`, `.js`, `.jsx` files.
3. **Apply rules** — circular detection (DFS cycle finding), cross-package checks, layer validation, UI-to-infra checks.
4. **Report violations** with file, line, rule name, and import path.

TSA is deterministic and does not require a TypeScript compiler installation.

---

## Related signals

- **AVS (Architecture Violation)** — Python-specific layer boundary detection. TSA is the TypeScript equivalent.
- **CIR (Circular Import)** — Python-specific cycle detection. TSA includes cycle detection for TS/JS.
