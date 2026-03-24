"""TypeScript Architecture Signal — integrates TS/JS rules into the signal pipeline.

Runs the four TS-specific architecture rules (circular module detection,
cross-package import ban, layer leak detection, ui-to-infra import ban)
and converts their results into standard ``Finding`` objects with
``SignalType.ARCHITECTURE_VIOLATION``.

This signal only activates when TypeScript/TSX files are present in the
parse results, keeping Python-only analyses unaffected.
"""

from __future__ import annotations

import logging
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    SignalType,
    severity_for_score,
)
from drift.signals.base import BaseSignal, register_signal

logger = logging.getLogger("drift.ts_arch")

_TS_LANGUAGES: frozenset[str] = frozenset({"typescript", "tsx", "javascript", "jsx"})


def _has_ts_files(parse_results: list[ParseResult]) -> bool:
    return any(pr.language in _TS_LANGUAGES for pr in parse_results)


def _repo_path_from_pr(parse_results: list[ParseResult]) -> Path | None:
    """Infer repo root from parse result file paths (best-effort)."""
    # Not needed — repo_path comes from BaseSignal._repo_path
    return None


@register_signal
class TypeScriptArchitectureSignal(BaseSignal):
    """Run TS/JS architecture rules and emit findings into the main pipeline."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.ARCHITECTURE_VIOLATION

    @property
    def name(self) -> str:
        return "TypeScript Architecture"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        if not _has_ts_files(parse_results):
            return []

        repo_path = self._repo_path
        if repo_path is None:
            logger.debug("No repo_path available — skipping TS architecture rules.")
            return []

        findings: list[Finding] = []

        # --- 1. Circular module detection ---
        findings.extend(self._run_circular(repo_path))

        # --- 2. Cross-package import ban ---
        findings.extend(self._run_cross_package(repo_path, config))

        # --- 3. Layer leak detection ---
        findings.extend(self._run_layer_leak(repo_path, config))

        # --- 4. UI-to-infra import ban ---
        findings.extend(self._run_ui_to_infra(repo_path, config))

        return findings

    # ------------------------------------------------------------------
    # Rule runners
    # ------------------------------------------------------------------

    def _run_circular(self, repo_path: Path) -> list[Finding]:
        try:
            from drift.rules.tsjs.circular_module_detection import (
                run_circular_module_detection,
            )
        except ImportError:
            return []

        findings: list[Finding] = []
        for raw in run_circular_module_detection(repo_path):
            cycle_nodes: list[str] = raw.get("cycle_nodes", [])  # type: ignore[assignment]
            cycle_len: int = raw.get("cycle_length", len(cycle_nodes))  # type: ignore[assignment]
            score = min(1.0, 0.3 + 0.1 * cycle_len)

            first_file = Path(cycle_nodes[0]) if cycle_nodes else None
            related = [Path(n) for n in cycle_nodes[1:]] if len(cycle_nodes) > 1 else []

            findings.append(
                Finding(
                    signal_type=SignalType.ARCHITECTURE_VIOLATION,
                    severity=severity_for_score(score),
                    score=score,
                    title=f"Circular import cycle ({cycle_len} modules)",
                    description=(
                        f"File-level import cycle detected: "
                        f"{' → '.join(cycle_nodes)} → {cycle_nodes[0] if cycle_nodes else '?'}"
                    ),
                    file_path=first_file,
                    related_files=related,
                    fix="Break the cycle by extracting shared types into a common module.",
                    metadata={"rule_id": "circular-module-detection", "cycle_nodes": cycle_nodes},
                )
            )
        return findings

    def _run_cross_package(self, repo_path: Path, config: DriftConfig) -> list[Finding]:
        try:
            from drift.rules.tsjs.cross_package_import_ban import (
                run_cross_package_import_ban,
            )
        except ImportError:
            return []

        config_path = repo_path / "cross_package_import_ban.json"
        if not config_path.is_file():
            # Check for config in drift config directory
            config_path = repo_path / ".drift" / "cross_package_import_ban.json"
        if not config_path.is_file():
            return []

        findings: list[Finding] = []
        for raw in run_cross_package_import_ban(repo_path, config_path):
            source_file = raw.get("source_file", "")
            target_file = raw.get("target_file", "")
            source_pkg = raw.get("source_package", "?")
            target_pkg = raw.get("target_package", "?")
            score = 0.6

            findings.append(
                Finding(
                    signal_type=SignalType.ARCHITECTURE_VIOLATION,
                    severity=severity_for_score(score),
                    score=score,
                    title=f"Cross-package import: {source_pkg} → {target_pkg}",
                    description=(
                        f"{source_file} imports from {target_file}, "
                        f"crossing package boundary ({source_pkg} → {target_pkg})."
                    ),
                    file_path=Path(source_file),
                    related_files=[Path(target_file)],
                    fix=(
                        f"Move shared code to a common package or add "
                        f"({source_pkg}, {target_pkg}) to allowed_package_import_pairs."
                    ),
                    metadata={"rule_id": "cross-package-import-ban"},
                )
            )
        return findings

    def _run_layer_leak(self, repo_path: Path, config: DriftConfig) -> list[Finding]:
        try:
            from drift.rules.tsjs.layer_leak_detection import run_layer_leak_detection
        except ImportError:
            return []

        config_path = repo_path / "layer_leak_detection.json"
        if not config_path.is_file():
            config_path = repo_path / ".drift" / "layer_leak_detection.json"
        if not config_path.is_file():
            return []

        findings: list[Finding] = []
        for raw in run_layer_leak_detection(repo_path, config_path):
            source_file = raw.get("source_file", "")
            target_file = raw.get("target_file", "")
            source_layer = raw.get("source_layer", "?")
            target_layer = raw.get("target_layer", "?")
            score = 0.7

            findings.append(
                Finding(
                    signal_type=SignalType.ARCHITECTURE_VIOLATION,
                    severity=severity_for_score(score),
                    score=score,
                    title=f"Layer leak: {source_layer} → {target_layer}",
                    description=(
                        f"{source_file} (layer: {source_layer}) imports from "
                        f"{target_file} (layer: {target_layer}), violating layer order."
                    ),
                    file_path=Path(source_file),
                    related_files=[Path(target_file)],
                    fix="Move the dependency behind an interface in the correct layer.",
                    metadata={"rule_id": "layer-leak-detection"},
                )
            )
        return findings

    def _run_ui_to_infra(self, repo_path: Path, config: DriftConfig) -> list[Finding]:
        try:
            from drift.rules.tsjs.ui_to_infra_import_ban import (
                run_ui_to_infra_import_ban,
            )
        except ImportError:
            return []

        config_path = repo_path / "ui_to_infra_import_ban.json"
        if not config_path.is_file():
            config_path = repo_path / ".drift" / "ui_to_infra_import_ban.json"
        if not config_path.is_file():
            return []

        findings: list[Finding] = []
        for raw in run_ui_to_infra_import_ban(repo_path, config_path):
            source_file = raw.get("source_file", "")
            target_file = raw.get("target_file", "")
            source_layer = raw.get("source_layer", "?")
            target_layer = raw.get("target_layer", "?")
            score = 0.8

            findings.append(
                Finding(
                    signal_type=SignalType.ARCHITECTURE_VIOLATION,
                    severity=severity_for_score(score),
                    score=score,
                    title=f"UI → Infrastructure import: {source_layer} → {target_layer}",
                    description=(
                        f"{source_file} (UI layer: {source_layer}) directly imports from "
                        f"{target_file} (infra layer: {target_layer})."
                    ),
                    file_path=Path(source_file),
                    related_files=[Path(target_file)],
                    fix="Introduce an abstraction layer or use dependency injection.",
                    metadata={"rule_id": "ui-to-infra-import-ban"},
                )
            )
        return findings
