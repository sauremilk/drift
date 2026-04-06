# Language Support Matrix

| Language | Support Level | Since | Definition of Done |
| --- | --- | --- | --- |
| Python | full-semantic | v0.1 | All 7 core signals run on language-native AST (`ast` stdlib); findings include reproducible evidence and actionable next step. Validated on 8+ repos with 85% precision. |
| TypeScript | full-semantic | v0.5 | All 7 core signals run on tree-sitter AST; function/class/import extraction, AST n-grams, error-handling patterns, API endpoint detection, test heuristics, Node.js stdlib filter, architecture rules. Validated on 5 repos (§12 STUDY.md). |
| JavaScript | full-semantic | v0.5 | Parsed via TypeScript grammar (tree-sitter); .js and .jsx files fully supported. Same signal coverage as TypeScript. |
| Go | planned | — | Import graph, package boundaries, forbidden dependencies. Blocked until TS/JS production validation complete. |
| Java | config-only (planned) | — | Configuration and repository metadata checks run; outputs remain traceable and reproducible. |
| Kotlin | config-only (planned) | — | Configuration and repository metadata checks run; outputs remain traceable and reproducible. |
| Rust | watchlist | — | Language tracked for future support; entry documents current gap and clear adoption trigger. |
