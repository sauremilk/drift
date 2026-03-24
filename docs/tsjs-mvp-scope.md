# TS/JS MVP Scope

## In Scope
- Relative import graph for `.ts` and `.tsx`
- `tsconfig.json` path alias resolution
- Barrel export resolution for `index.ts`
- Package boundary detection from workspace configuration
- Rule: cross-package-import-ban
- Rule: ui-to-infra-import-ban
- Rule: layer-leak-detection
- Rule: circular-module-detection

## Out of Scope
- `.js` and `.jsx` parsing
- Dynamic imports
- Bundler-specific resolution
- Type inference
- Framework-specific decorators