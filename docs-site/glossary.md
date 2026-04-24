# Glossary

## Architecture drift

Structural divergence between the way a repository was meant to evolve and the way patterns actually spread across files and modules.

## Architectural erosion

The gradual loss of shared implementation shape, boundary discipline, and structural clarity over time.

## Architectural linter

A tool that focuses on structural consistency and cross-file coherence rather than only local style or syntax.

## Pattern Fragmentation (PFS)

One category of pattern implemented several different ways within a module.

## Architecture Violations (AVS)

Imports or dependencies that cross intended boundaries or create cycles.

## Mutant Duplicates (MDS)

Near-identical functions that diverged after copy-modify work.

## Explainability Deficit (EDS)

Complex code that lacks the supporting context needed to review or change it safely, such as docs, types, or tests.

## Temporal Volatility (TVS)

Abnormal change patterns in files, such as unusually high churn or author diversity.

## System Misalignment (SMS)

Patterns or imports that look foreign to the module where they appear.

## Doc-Implementation Drift (DIA)

Documented structure that no longer matches the code. Drift currently reports DIA but excludes it from the composite score.

## SARIF

A machine-readable format that allows findings to appear in code scanning and related review workflows.
