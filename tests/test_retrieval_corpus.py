"""Tests for drift.retrieval.corpus_builder and fact_ids (ADR-091).

Cover:
- deterministic corpus_sha256 across rebuilds,
- Fact-ID generator shape and stability,
- migration registry transitive resolution,
- per-kind chunk coverage on the real drift repo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from drift.retrieval.cache import clear_memory_cache, load_or_build
from drift.retrieval.corpus_builder import (
    build_corpus,
    compute_corpus_sha256,
    parse_adr,
    parse_policy,
)
from drift.retrieval.fact_ids import (
    MigrationRegistry,
    generate_adr_id,
    generate_audit_id,
    generate_evidence_id,
    generate_policy_id,
    generate_signal_id,
)


@pytest.fixture(scope="module")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


# --- Fact-ID generators ----------------------------------------------------


def test_policy_id_format() -> None:
    assert generate_policy_id(8, 3) == "POLICY#S8.p3"
    assert generate_policy_id("1", "1") == "POLICY#S1.p1"


def test_adr_id_format_and_zero_padding() -> None:
    assert generate_adr_id(91, "Decision") == "ADR-091#decision"
    assert generate_adr_id(7, "Kontext und Ziel") == "ADR-007#kontext-und-ziel"


def test_audit_id_slugifies_row() -> None:
    assert generate_audit_id("fmea_matrix", "R-12") == "AUDIT/fmea_matrix#R-12"
    assert generate_audit_id("stride threat model", "S1") == (
        "AUDIT/stride-threat-model#S1"
    )


def test_signal_id_and_evidence_id() -> None:
    assert generate_signal_id("pattern_fragmentation", "rationale") == (
        "SIGNAL/pattern_fragmentation#rationale"
    )
    assert generate_evidence_id("2.31.0", "precision_recall") == (
        "EVIDENCE/v2.31.0#precision_recall"
    )


# --- Migration registry ----------------------------------------------------


def test_migration_registry_transitive_resolution(tmp_path: Path) -> None:
    registry_file = tmp_path / "migrations.jsonl"
    registry_file.write_text(
        "\n".join(
            [
                json.dumps({"schema_version": 1}),
                json.dumps({"old_id": "POLICY#S8.p2", "new_id": "POLICY#S8.p3"}),
                json.dumps({"old_id": "POLICY#S8.p3", "new_id": "POLICY#S8.p4"}),
            ]
        ),
        encoding="utf-8",
    )
    reg = MigrationRegistry.from_file(registry_file)
    assert reg.resolve("POLICY#S8.p2") == "POLICY#S8.p4"
    assert reg.resolve("POLICY#S8.p4") == "POLICY#S8.p4"
    assert reg.is_migrated("POLICY#S8.p2")
    assert not reg.is_migrated("POLICY#S8.p4")


def test_migration_registry_handles_cycles(tmp_path: Path) -> None:
    registry_file = tmp_path / "migrations.jsonl"
    registry_file.write_text(
        "\n".join(
            [
                json.dumps({"old_id": "A", "new_id": "B"}),
                json.dumps({"old_id": "B", "new_id": "A"}),
            ]
        ),
        encoding="utf-8",
    )
    reg = MigrationRegistry.from_file(registry_file)
    resolved = reg.resolve("A")
    assert resolved in {"A", "B"}


def test_migration_registry_missing_file() -> None:
    reg = MigrationRegistry.from_file(Path("nonexistent-path.jsonl"))
    assert len(reg) == 0
    assert reg.resolve("UNKNOWN") == "UNKNOWN"


# --- Corpus determinism ----------------------------------------------------


def test_corpus_is_deterministic(repo_root: Path) -> None:
    chunks_a = build_corpus(repo_root)
    chunks_b = build_corpus(repo_root)
    sha_a = compute_corpus_sha256(chunks_a)
    sha_b = compute_corpus_sha256(chunks_b)
    assert sha_a == sha_b
    assert [c.fact_id for c in chunks_a] == [c.fact_id for c in chunks_b]


def test_corpus_covers_all_kinds(repo_root: Path) -> None:
    chunks = build_corpus(repo_root)
    kinds = {c.kind for c in chunks}

    expected_kinds = {"policy", "roadmap", "adr", "signal"}

    audit_dir = repo_root / "audit_results"
    if audit_dir.exists() and any(audit_dir.glob("*.md")):
        expected_kinds.add("audit")

    evidence_dir = repo_root / "benchmark_results"
    if evidence_dir.exists() and any(evidence_dir.glob("*.json")):
        expected_kinds.add("evidence")

    for expected in expected_kinds:
        assert expected in kinds, f"kind {expected!r} missing from corpus"


def test_policy_chunks_exist(repo_root: Path) -> None:
    chunks = list(parse_policy(repo_root / "POLICY.md", repo_root))
    fact_ids = {c.fact_id for c in chunks}
    # POLICY §8 is the Zulassungskriterien section and is test-anchor.
    assert any(fid.startswith("POLICY#S8.") for fid in fact_ids)


def test_adr_parses_canonical_sections(repo_root: Path) -> None:
    adr_file = repo_root / "docs" / "decisions" / "ADR-091-drift-retrieval-rag.md"
    if not adr_file.exists():
        pytest.skip("ADR-091 not yet present")
    chunks = list(parse_adr(adr_file, repo_root))
    fact_ids = {c.fact_id for c in chunks}
    assert "ADR-091#entscheidung" in fact_ids
    assert "ADR-091#begr-ndung" in fact_ids or "ADR-091#begrundung" in fact_ids
    assert "ADR-091#konsequenzen" in fact_ids


# --- Cache roundtrip -------------------------------------------------------


def test_cache_roundtrip_stable(repo_root: Path, tmp_path: Path) -> None:
    clear_memory_cache()
    cache_dir = tmp_path / "retrieval-cache"
    manifest_a, chunks_a = load_or_build(repo_root, cache_dir=cache_dir)
    clear_memory_cache()
    manifest_b, chunks_b = load_or_build(repo_root, cache_dir=cache_dir)
    assert manifest_a.corpus_sha256 == manifest_b.corpus_sha256
    assert [c.fact_id for c in chunks_a] == [c.fact_id for c in chunks_b]
