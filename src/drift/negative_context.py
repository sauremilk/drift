"""Negative context generation — translates drift findings into anti-pattern warnings.

Coding agents consume these items as "what NOT to do" context before generating
code.  Every item is deterministically derived from signal findings — no LLM
involved.

Architecture:
    findings_to_negative_context(findings) → list[NegativeContext]

Each signal type has a registered generator that converts its findings into
zero or more NegativeContext items.  Generators are keyed by SignalType so
new signals automatically participate once they register a generator function.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from drift.models import (
    Finding,
    NegativeContext,
    NegativeContextCategory,
    NegativeContextScope,
    Severity,
    SignalType,
)

# ---------------------------------------------------------------------------
# Metadata sanitisation — strip control chars to prevent injection in
# code-block output that agents may execute.
# ---------------------------------------------------------------------------


def _sanitize(value: str, max_len: int = 200) -> str:
    """Remove newlines and control characters from metadata strings."""
    cleaned = value.replace("\n", " ").replace("\r", "")
    # Strip non-printable control characters (keep space)
    cleaned = "".join(ch for ch in cleaned if ch == " " or ch.isprintable())
    return cleaned[:max_len]


# ---------------------------------------------------------------------------
# Signal → Category mapping
# ---------------------------------------------------------------------------

_SIGNAL_CATEGORY: dict[SignalType, NegativeContextCategory] = {
    # Security
    SignalType.MISSING_AUTHORIZATION: NegativeContextCategory.SECURITY,
    SignalType.HARDCODED_SECRET: NegativeContextCategory.SECURITY,
    SignalType.INSECURE_DEFAULT: NegativeContextCategory.SECURITY,
    # Error handling
    SignalType.BROAD_EXCEPTION_MONOCULTURE: NegativeContextCategory.ERROR_HANDLING,
    SignalType.EXCEPTION_CONTRACT_DRIFT: NegativeContextCategory.ERROR_HANDLING,
    # Architecture
    SignalType.ARCHITECTURE_VIOLATION: NegativeContextCategory.ARCHITECTURE,
    SignalType.CIRCULAR_IMPORT: NegativeContextCategory.ARCHITECTURE,
    SignalType.CO_CHANGE_COUPLING: NegativeContextCategory.ARCHITECTURE,
    SignalType.FAN_OUT_EXPLOSION: NegativeContextCategory.ARCHITECTURE,
    SignalType.COHESION_DEFICIT: NegativeContextCategory.ARCHITECTURE,
    SignalType.TS_ARCHITECTURE: NegativeContextCategory.ARCHITECTURE,
    # Testing
    SignalType.TEST_POLARITY_DEFICIT: NegativeContextCategory.TESTING,
    # Naming
    SignalType.NAMING_CONTRACT_VIOLATION: NegativeContextCategory.NAMING,
    # Complexity
    SignalType.EXPLAINABILITY_DEFICIT: NegativeContextCategory.COMPLEXITY,
    SignalType.COGNITIVE_COMPLEXITY: NegativeContextCategory.COMPLEXITY,
    SignalType.GUARD_CLAUSE_DEFICIT: NegativeContextCategory.COMPLEXITY,
    # Completeness
    SignalType.DOC_IMPL_DRIFT: NegativeContextCategory.COMPLETENESS,
    SignalType.DEAD_CODE_ACCUMULATION: NegativeContextCategory.COMPLETENESS,
    SignalType.BYPASS_ACCUMULATION: NegativeContextCategory.COMPLETENESS,
    # Structural
    SignalType.PATTERN_FRAGMENTATION: NegativeContextCategory.ARCHITECTURE,
    SignalType.MUTANT_DUPLICATE: NegativeContextCategory.ARCHITECTURE,
    SignalType.TEMPORAL_VOLATILITY: NegativeContextCategory.ARCHITECTURE,
    SignalType.SYSTEM_MISALIGNMENT: NegativeContextCategory.ARCHITECTURE,
}

# ---------------------------------------------------------------------------
# Generator registry
# ---------------------------------------------------------------------------

GeneratorFn = Callable[[Finding], list[NegativeContext]]
_GENERATORS: dict[SignalType, GeneratorFn] = {}
_FALLBACK_ONLY_SIGNALS: frozenset[SignalType] = frozenset()


def _policy_covered_signal_types() -> set[SignalType]:
    """Return all signal types explicitly covered by NC policy."""
    return set(_GENERATORS) | set(_FALLBACK_ONLY_SIGNALS)


def _policy_uncovered_signal_types() -> set[SignalType]:
    """Return signal types lacking both dedicated and fallback-only policy."""
    return set(SignalType) - _policy_covered_signal_types()


def _register(signal_type: SignalType) -> Callable[[GeneratorFn], GeneratorFn]:
    """Decorator to register a negative-context generator for a signal type."""

    def decorator(fn: GeneratorFn) -> GeneratorFn:
        _GENERATORS[signal_type] = fn
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _neg_id(signal_type: SignalType, finding: Finding) -> str:
    """Generate a deterministic anti-pattern ID."""
    fp = finding.file_path.as_posix() if finding.file_path else ""
    blob = f"neg:{signal_type.value}:{fp}:{finding.title}"
    short_hash = hashlib.sha256(blob.encode()).hexdigest()[:10]
    return f"neg-{signal_type.value[:3]}-{short_hash}"


def _affected(finding: Finding) -> list[str]:
    """Extract affected file paths as strings."""
    files: list[str] = []
    if finding.file_path:
        files.append(finding.file_path.as_posix())
    files.extend(rf.as_posix() for rf in finding.related_files)
    return list(dict.fromkeys(files))


def _scope_from_finding(finding: Finding) -> NegativeContextScope:
    """Determine scope based on finding characteristics."""
    if finding.related_files and len(finding.related_files) > 2:
        return NegativeContextScope.MODULE
    if finding.file_path:
        return NegativeContextScope.FILE
    return NegativeContextScope.REPO


# ---------------------------------------------------------------------------
# Cluster A generators (RPN ≥ 280)
# ---------------------------------------------------------------------------


@_register(SignalType.TEST_POLARITY_DEFICIT)
def _gen_tpd(finding: Finding) -> list[NegativeContext]:
    """FM-07 (RPN 384): Test happy-path only."""
    meta = finding.metadata
    func_name = meta.get("function_name", finding.symbol or "the tested function")

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.TEST_POLARITY_DEFICIT, finding),
        category=NegativeContextCategory.TESTING,
        source_signal=SignalType.TEST_POLARITY_DEFICIT,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=(
            f"Tests for '{func_name}' cover only the success path. "
            f"Missing: error cases, boundary conditions, invalid inputs."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Only happy-path test\n"
            "def test_function():\n"
            "    result = function(valid_input)\n"
            "    assert result == expected  # No error/edge case tests"
        ),
        canonical_alternative=(
            "# REQUIRED: Include error and boundary tests\n"
            "def test_function_success():\n"
            "    assert function(valid_input) == expected\n\n"
            "def test_function_invalid_input():\n"
            "    with pytest.raises(ValueError):\n"
            "        function(invalid_input)\n\n"
            "def test_function_boundary():\n"
            "    assert function(boundary_value) == boundary_expected"
        ),
        affected_files=_affected(finding),
        confidence=0.9,
        rationale=(
            "AI agents tend to generate only success-path tests (FMEA FM-07, RPN 384). "
            "Every function with >1 code path requires at least one error-case test."
        ),
    )]


@_register(SignalType.DOC_IMPL_DRIFT)
def _gen_dia(finding: Finding) -> list[NegativeContext]:
    """FM-12 (RPN 320): Docstring hallucination / doc-code mismatch."""
    meta = finding.metadata
    func_name = meta.get("function_name", finding.symbol or "the function")
    mismatch_type = meta.get("mismatch_type", "signature mismatch")

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.DOC_IMPL_DRIFT, finding),
        category=NegativeContextCategory.COMPLETENESS,
        source_signal=SignalType.DOC_IMPL_DRIFT,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=(
            f"Documentation for '{func_name}' does not match implementation "
            f"({mismatch_type}). Do not trust or copy existing docstring."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Docstring contradicts actual signature/behavior\n"
            "def process(data, timeout=30):\n"
            '    """Process data with retries.\n\n'
            "    Args:\n"
            "        data: Input data\n"
            "        max_retries: Number of retries  # <- param doesn't exist!\n"
            '    """'
        ),
        canonical_alternative=(
            "# REQUIRED: Docstring must match actual parameters and behavior\n"
            "# Before writing docstrings, verify:\n"
            "# 1. All documented params exist in the signature\n"
            "# 2. All params in the signature are documented\n"
            "# 3. Return type matches actual returns\n"
            "# 4. Described behavior matches implementation"
        ),
        affected_files=_affected(finding),
        confidence=0.85,
        rationale=(
            "AI agents frequently hallucinate plausible but incorrect docstrings "
            "(FMEA FM-12, RPN 320). Always verify docs against actual code."
        ),
    )]


@_register(SignalType.MISSING_AUTHORIZATION)
def _gen_maz(finding: Finding) -> list[NegativeContext]:
    """FM-03 (RPN 300): Missing authorization on endpoints."""
    meta = finding.metadata
    auth_mechs = meta.get("auth_mechanisms_in_module", [])
    framework = meta.get("framework", "unknown")
    endpoint = meta.get("endpoint", finding.symbol or "endpoint")

    if auth_mechs:
        auth_example = auth_mechs[0] if isinstance(auth_mechs[0], str) else str(auth_mechs[0])
    else:
        auth_example = "@login_required or equivalent"

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.MISSING_AUTHORIZATION, finding),
        category=NegativeContextCategory.SECURITY,
        source_signal=SignalType.MISSING_AUTHORIZATION,
        severity=Severity.HIGH,
        scope=_scope_from_finding(finding),
        description=(
            f"Endpoint '{endpoint}' has no authorization. "
            f"This repo uses {framework} with auth pattern: {auth_example}. "
            f"Every new endpoint MUST include authorization."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Endpoint without authorization (CWE-862)\n"
            f"# Framework: {framework}\n"
            "def create_item(request):\n"
            "    # <- No auth check! Any anonymous user can access this\n"
            "    return create(request.data)"
        ),
        canonical_alternative=(
            "# REQUIRED: Apply this repo's established auth pattern\n"
            "# Every new endpoint MUST be protected.\n"
            "# Only health-check and public docs endpoints are exempt."
        ),
        affected_files=_affected(finding),
        confidence=0.95,
        rationale=(
            "AI agents copy endpoint patterns from public tutorials without auth "
            "(FMEA FM-03, RPN 300, CWE-862). "
            "This repo's auth pattern must be applied to ALL new endpoints."
        ),
        metadata={"cwe": "CWE-862", "framework": framework},
    )]


@_register(SignalType.EXPLAINABILITY_DEFICIT)
def _gen_eds(finding: Finding) -> list[NegativeContext]:
    """FM-05 proxy (RPN 294): Over-abstraction via EDS."""
    meta = finding.metadata
    func_name = meta.get("function_name", finding.symbol or "the construct")
    complexity = meta.get("complexity", 0)

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.EXPLAINABILITY_DEFICIT, finding),
        category=NegativeContextCategory.COMPLEXITY,
        source_signal=SignalType.EXPLAINABILITY_DEFICIT,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=(
            f"'{func_name}' has unexplained complexity "
            f"(complexity={complexity}). Do not add unnecessary abstractions."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Unnecessary abstraction layers\n"
            "class AbstractProcessor(ABC):  # Only 1 subclass exists!\n"
            "    @abstractmethod\n"
            "    def process(self): ...\n\n"
            "class ConcreteProcessor(AbstractProcessor):\n"
            "    def process(self): return do_work()"
        ),
        canonical_alternative=(
            "# PREFERRED: Direct implementation without premature abstraction\n"
            "def process():\n"
            "    return do_work()\n\n"
            "# Add abstraction only when a second variant actually exists"
        ),
        affected_files=_affected(finding),
        confidence=0.75,
        rationale=(
            "AI agents tend to introduce Factory/Strategy/ABC patterns for single-use "
            "(FMEA FM-05, RPN 294). Prefer flat, direct implementations."
        ),
    )]


@_register(SignalType.BROAD_EXCEPTION_MONOCULTURE)
def _gen_bem(finding: Finding) -> list[NegativeContext]:
    """FM-02 (RPN 288): Shallow exception handling."""
    meta = finding.metadata
    handler_action = meta.get("handler_action", "pass")

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.BROAD_EXCEPTION_MONOCULTURE, finding),
        category=NegativeContextCategory.ERROR_HANDLING,
        source_signal=SignalType.BROAD_EXCEPTION_MONOCULTURE,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=(
            "Broad exception handler swallows errors without recovery or re-raise. "
            f"Handler action: '{handler_action}'."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Bare except or broad except with pass/print\n"
            "try:\n"
            "    result = dangerous_operation()\n"
            "except Exception:\n"
            "    pass  # <- Silently swallows ALL errors!"
        ),
        canonical_alternative=(
            "# REQUIRED: Catch specific exceptions, re-raise or handle\n"
            "try:\n"
            "    result = dangerous_operation()\n"
            "except SpecificError as exc:\n"
            "    logger.warning('Operation failed: %s', exc)\n"
            "    raise  # or: return fallback_value"
        ),
        affected_files=_affected(finding),
        confidence=0.9,
        rationale=(
            "AI agents generate syntactically correct but semantically empty exception "
            "handlers (FMEA FM-02, RPN 288). Always catch specific exceptions and "
            "either re-raise or handle with recovery logic."
        ),
    )]


@_register(SignalType.EXCEPTION_CONTRACT_DRIFT)
def _gen_ecm(finding: Finding) -> list[NegativeContext]:
    """FM-08 (RPN 252): Inconsistent error contract — project-specific."""
    meta = finding.metadata
    module = meta.get(
        "module",
        finding.file_path.as_posix() if finding.file_path else "module",
    )
    exception_types = meta.get("exception_types", [])
    exc_str = (
        ", ".join(str(e) for e in exception_types[:5])
        if exception_types
        else "mixed types"
    )
    # Phase 3: extract concrete drift details
    diverged_fns = meta.get("diverged_functions", [])
    divergence_count = meta.get("divergence_count", 0)
    comparison_ref = meta.get("comparison_ref", "")
    module_fn_count = meta.get("module_function_count", 0)

    # Build enriched description
    desc_parts = [
        f"Module '{module}' has inconsistent exception types: {exc_str}.",
    ]
    if diverged_fns:
        fn_list = ", ".join(str(f) for f in diverged_fns[:3])
        desc_parts.append(
            f"Functions with changed contracts: {fn_list}"
            f" ({divergence_count}/{module_fn_count} diverged)."
        )
    if comparison_ref:
        desc_parts.append(
            f"Contract changed relative to {comparison_ref}."
        )
    desc_parts.append("Do NOT introduce new exception hierarchies.")

    # Concrete forbidden pattern showing actual diverged function
    if diverged_fns:
        example_fn = diverged_fns[0]
        forbidden = (
            f"# ANTI-PATTERN: Exception contract drift in '{module}'\n"
            f"# '{example_fn}' changed its exception behavior\n"
            "class MyNewError(Exception): ...  # <- Conflicts with contract"
        )
    else:
        forbidden = (
            "# ANTI-PATTERN: Introducing a new exception type in a module\n"
            "# that already uses a different exception hierarchy\n"
            "class MyNewError(Exception): ...  # <- Conflicts with contract"
        )

    enriched_meta: dict[str, Any] = {}
    if diverged_fns:
        enriched_meta["diverged_functions"] = diverged_fns[:5]
    if comparison_ref:
        enriched_meta["comparison_ref"] = comparison_ref

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.EXCEPTION_CONTRACT_DRIFT, finding),
        category=NegativeContextCategory.ERROR_HANDLING,
        source_signal=SignalType.EXCEPTION_CONTRACT_DRIFT,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=" ".join(desc_parts),
        forbidden_pattern=forbidden,
        canonical_alternative=(
            f"# REQUIRED: Use the existing exception types in '{module}': "
            f"{exc_str}\n"
            "# Before adding new exceptions, check what the module already uses\n"
            "# Align error handling with the module's established contract"
        ),
        affected_files=_affected(finding),
        confidence=0.85 if diverged_fns else 0.8,
        rationale=(
            "AI agents introduce new exception types without knowing the module's "
            "existing contract (FMEA FM-08, RPN 252). "
            f"This module has {len(exception_types)} established exception types."
        ),
        metadata=enriched_meta,
    )]


# ---------------------------------------------------------------------------
# Cluster B generators (RPN 200–279)
# ---------------------------------------------------------------------------


@_register(SignalType.ARCHITECTURE_VIOLATION)
def _gen_avs(finding: Finding) -> list[NegativeContext]:
    """FM-14 (RPN 240): Architecture layer violation — project-specific."""
    meta = finding.metadata
    # Phase 3: extract concrete layer identities from actual metadata
    src_layer = _sanitize(str(meta.get("src_layer") or meta.get("source_layer", "unknown")))
    dst_layer = _sanitize(str(meta.get("dst_layer") or meta.get("target_layer", "unknown")))
    rule = _sanitize(str(meta.get("rule", "")))
    import_path = _sanitize(str(meta.get("import", "")))
    blast_radius = meta.get("blast_radius")
    instability = meta.get("instability")

    # Build enriched description from real project data
    desc_parts = [
        f"Layer violation: '{src_layer}' -> '{dst_layer}'.",
    ]
    if rule:
        desc_parts.append(f"Boundary rule violated: {rule}.")
    if blast_radius is not None:
        desc_parts.append(f"Blast radius: {blast_radius} modules affected.")
    desc_parts.append(
        "Do NOT introduce imports that cross this boundary."
    )

    # Concrete forbidden import from actual finding
    if import_path:
        forbidden = (
            f"# ANTI-PATTERN: Forbidden cross-layer import\n"
            f"import {import_path}  # <- violates {src_layer} -> {dst_layer} boundary"
        )
    else:
        forbidden = (
            f"# ANTI-PATTERN: Importing from forbidden layer\n"
            f"from {dst_layer} import ...  # <- violates layer boundary"
        )

    # Stability-aware canonical alternative
    canonical_parts = [
        "# REQUIRED: Respect layer boundaries in this project:\n",
        f"# {src_layer} must NOT depend on {dst_layer}\n",
    ]
    if instability is not None:
        canonical_parts.append(
            f"# Module instability={instability:.2f} -- "
            "depend on stable (low-I) modules only\n"
        )
    canonical_parts.append(
        "# Use dependency injection or interfaces for cross-layer access"
    )

    enriched_meta: dict[str, Any] = {}
    if rule:
        enriched_meta["boundary_rule"] = rule
    if blast_radius is not None:
        enriched_meta["blast_radius"] = blast_radius
    if instability is not None:
        enriched_meta["instability"] = instability

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.ARCHITECTURE_VIOLATION, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.ARCHITECTURE_VIOLATION,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=" ".join(desc_parts),
        forbidden_pattern=forbidden,
        canonical_alternative="".join(canonical_parts),
        affected_files=_affected(finding),
        confidence=0.90 if rule else 0.85,
        rationale=(
            "AI agents do not see the import graph and create layer violations "
            "(FMEA FM-14, RPN 240). "
            "This project has explicit boundary rules that MUST be respected."
        ),
        metadata=enriched_meta,
    )]


@_register(SignalType.CO_CHANGE_COUPLING)
def _gen_ccc(finding: Finding) -> list[NegativeContext]:
    """FM-17 (RPN 240): Co-change coupling — project-specific pairs."""
    meta = finding.metadata
    # Phase 3: use actual CCC metadata for concrete coupled pair
    file_a = meta.get("file_a") or (
        finding.file_path.as_posix() if finding.file_path else "file_a"
    )
    file_b = meta.get("file_b", "")
    co_change_weight = meta.get("co_change_weight")
    confidence_val = meta.get("confidence", 0.0)
    commit_samples = meta.get("commit_samples", [])
    coupled_files = meta.get("coupled_files", [])

    # Determine the concrete partner files
    partners: list[str] = []
    if file_b:
        partners.append(str(file_b))
    partners.extend(str(f) for f in coupled_files if str(f) != file_b)
    partners_str = ", ".join(partners[:5]) if partners else "related files"

    # Enriched description with coupling strength
    desc_parts = [
        f"'{file_a}' is historically co-changed with: {partners_str}.",
    ]
    if co_change_weight is not None:
        desc_parts.append(
            f"Co-change strength: {co_change_weight:.1f}"
            f" (confidence {confidence_val:.0%})."
        )
    desc_parts.append(
        "When changing one file, you MUST review and update the others."
    )

    # Evidence from commit history
    evidence_note = ""
    if commit_samples:
        samples = commit_samples[:3]
        evidence_note = (
            f"\n# Evidence: {len(commit_samples)} commits show co-change, "
            f"e.g. {', '.join(str(s)[:8] for s in samples)}"
        )

    all_partners = partners[:5]
    canonical_lines = [f"# REQUIRED: When modifying '{file_a}', also review:"]
    for p in all_partners:
        canonical_lines.append(f"# - {p}")
    if evidence_note:
        canonical_lines.append(evidence_note)

    enriched_meta: dict[str, Any] = {}
    if co_change_weight is not None:
        enriched_meta["co_change_weight"] = co_change_weight
    if commit_samples:
        enriched_meta["commit_samples"] = commit_samples[:3]

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.CO_CHANGE_COUPLING, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.CO_CHANGE_COUPLING,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=" ".join(desc_parts),
        forbidden_pattern=(
            f"# ANTI-PATTERN: Changing '{file_a}' in isolation\n"
            f"# These files are historically co-changed: {partners_str}\n"
            f"# Modifying one without the other causes hidden regressions"
        ),
        canonical_alternative="\n".join(canonical_lines),
        affected_files=_affected(finding),
        confidence=min(0.95, 0.6 + confidence_val * 0.35),
        rationale=(
            "AI agents change files in isolation without seeing co-change history "
            "(FMEA FM-17, RPN 240). "
            f"This pair has been co-changed in {len(commit_samples)} commits."
        ),
        metadata=enriched_meta,
    )]


@_register(SignalType.HARDCODED_SECRET)
def _gen_hsc(finding: Finding) -> list[NegativeContext]:
    """FM-04 (RPN 200): Hardcoded secrets — project-specific."""
    meta = finding.metadata
    var_name = _sanitize(str(meta.get("variable") or meta.get(
        "variable_name", finding.symbol or "secret",
    )))
    # Phase 3: use concrete detection rule for specific guidance
    rule_id = meta.get("rule_id", "hardcoded_secret")
    cwe = meta.get("cwe", "CWE-798")

    # Map rule_id to specific forbidden pattern -- use fixed variable names
    # per rule category so identical signals deduplicate in export (#109).
    if rule_id == "hardcoded_api_token":
        forbidden = (
            f"# ANTI-PATTERN: Hardcoded API token ({cwe})\n"
            'API_KEY = "sk-A1B2C3..."  '
            "# <- NEVER hardcode API tokens"
        )
        desc_detail = "API token"
    elif rule_id == "placeholder_secret":
        forbidden = (
            f"# ANTI-PATTERN: Placeholder secret left in code ({cwe})\n"
            'SECRET = "changeme"  '
            "# <- Placeholder secrets get deployed to production"
        )
        desc_detail = "placeholder secret"
    else:
        forbidden = (
            f"# ANTI-PATTERN: Hardcoded credentials ({cwe})\n"
            'SECRET = "secret_value"  '
            "# <- NEVER embed secrets in source"
        )
        desc_detail = "hardcoded credential"

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.HARDCODED_SECRET, finding),
        category=NegativeContextCategory.SECURITY,
        source_signal=SignalType.HARDCODED_SECRET,
        severity=Severity.HIGH,
        scope=_scope_from_finding(finding),
        description=(
            f"Hardcoded {desc_detail} in variable '{var_name}'. "
            "Never embed credentials, API keys, or tokens in source code. "
            f"Detection rule: {rule_id}."
        ),
        forbidden_pattern=forbidden,
        canonical_alternative=(
            "# REQUIRED: Use environment variables or a secrets manager\n"
            "import os\n"
            'VAR = os.environ["SECRET_NAME"]\n'
            "# Alternative: use a .env file with python-dotenv or similar"
        ),
        affected_files=_affected(finding),
        confidence=0.95,
        rationale=(
            "AI agents copy credential patterns from tutorials "
            f"(FMEA FM-04, RPN 200, {cwe}). "
            f"Detection: {rule_id}."
        ),
        metadata={"cwe": cwe, "rule_id": rule_id},
    )]


# ---------------------------------------------------------------------------
# Cluster C generators (RPN 96–199)
# ---------------------------------------------------------------------------


@_register(SignalType.PATTERN_FRAGMENTATION)
def _gen_pfs(finding: Finding) -> list[NegativeContext]:
    """FM-01 (RPN 189): Copy-paste proliferation."""
    meta = finding.metadata
    variant_count = meta.get("variant_count", 0)
    canonical = meta.get("canonical_variant", "the dominant pattern")
    module = meta.get("module", finding.file_path.as_posix() if finding.file_path else "module")

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.PATTERN_FRAGMENTATION, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.PATTERN_FRAGMENTATION,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=(
            f"Module '{module}' has {variant_count} pattern variants. "
            f"Use the canonical variant: {canonical}."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Introducing yet another pattern variant\n"
            f"# This module already has {variant_count} variants -- do not add more"
        ),
        canonical_alternative=(
            f"# REQUIRED: Follow the canonical pattern in this module:\n"
            f"# {canonical}\n"
            "# Align new code to the existing dominant pattern"
        ),
        affected_files=_affected(finding),
        confidence=0.85,
        rationale=(
            "AI agents create near-identical implementations without reusing existing "
            "patterns (FMEA FM-01, RPN 189)."
        ),
    )]


@_register(SignalType.MUTANT_DUPLICATE)
def _gen_mds(finding: Finding) -> list[NegativeContext]:
    """Copy-paste proliferation via duplicate functions."""
    meta = finding.metadata
    func_a = meta.get("function_a", "function_a")
    func_b = meta.get("function_b", "function_b")
    similarity = meta.get("similarity", 0.0)

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.MUTANT_DUPLICATE, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.MUTANT_DUPLICATE,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=(
            f"'{func_a}' and '{func_b}' are {similarity:.0%} similar. "
            "Reuse or consolidate instead of duplicating."
        ),
        forbidden_pattern=(
            f"# ANTI-PATTERN: Creating a near-duplicate of '{func_a}'\n"
            f"# '{func_b}' already exists with {similarity:.0%} similarity"
        ),
        canonical_alternative=(
            f"# REQUIRED: Reuse '{func_a}' or extract shared logic\n"
            "# Parameterize differences instead of copy-pasting"
        ),
        affected_files=_affected(finding),
        confidence=0.85,
        rationale="AI agents copy-paste and modify instead of parameterizing.",
    )]


@_register(SignalType.INSECURE_DEFAULT)
def _gen_isd(finding: Finding) -> list[NegativeContext]:
    """FM-16 (RPN 180): Insecure default config."""
    meta = finding.metadata
    setting = meta.get("setting", finding.symbol or "configuration")

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.INSECURE_DEFAULT, finding),
        category=NegativeContextCategory.SECURITY,
        source_signal=SignalType.INSECURE_DEFAULT,
        severity=Severity.HIGH,
        scope=_scope_from_finding(finding),
        description=(
            f"Insecure default detected: '{setting}'. "
            "Never use debug/development defaults in production-facing code."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Insecure defaults (CWE-1188)\n"
            'DEBUG = True  # <- NEVER as default\n'
            'CORS_ALLOW_ALL = True  # <- NEVER in production'
        ),
        canonical_alternative=(
            "# REQUIRED: Secure defaults, opt-in for development\n"
            "DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'\n"
            "CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',')"
        ),
        affected_files=_affected(finding),
        confidence=0.9,
        rationale=(
            "AI agents copy dev configuration as defaults "
            "(FMEA FM-16, RPN 180, CWE-1188)."
        ),
        metadata={"cwe": "CWE-1188"},
    )]


@_register(SignalType.NAMING_CONTRACT_VIOLATION)
def _gen_nbv(finding: Finding) -> list[NegativeContext]:
    """FM-09 (RPN 140): Naming convention drift."""
    meta = finding.metadata
    violation = meta.get("violation_type", "naming inconsistency")

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.NAMING_CONTRACT_VIOLATION, finding),
        category=NegativeContextCategory.NAMING,
        source_signal=SignalType.NAMING_CONTRACT_VIOLATION,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=(
            f"Naming violation: {violation}. "
            "Follow this repository's naming conventions."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Inconsistent naming\n"
            "# Do not introduce names that contradict the existing style"
        ),
        canonical_alternative=(
            "# REQUIRED: Match existing naming patterns in this module\n"
            "# Check similar symbols in the same file/module for style cues"
        ),
        affected_files=_affected(finding),
        confidence=0.7,
        rationale=(
            "AI agents use generic naming conventions instead of matching the "
            "project style (FMEA FM-09, RPN 140)."
        ),
    )]


@_register(SignalType.GUARD_CLAUSE_DEFICIT)
def _gen_gcd(finding: Finding) -> list[NegativeContext]:
    """FM-06 (RPN 105): Deep nesting instead of guard clauses."""
    func_name = finding.metadata.get("function_name", finding.symbol or "function")

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.GUARD_CLAUSE_DEFICIT, finding),
        category=NegativeContextCategory.COMPLEXITY,
        source_signal=SignalType.GUARD_CLAUSE_DEFICIT,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=(
            f"'{func_name}' uses deep nesting instead of early returns."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Deep nesting\n"
            "def process(data):\n"
            "    if data:\n"
            "        if data.valid:\n"
            "            if data.ready:\n"
            "                return do_work(data)  # <- 3 levels deep"
        ),
        canonical_alternative=(
            "# PREFERRED: Guard clauses with early return\n"
            "def process(data):\n"
            "    if not data:\n"
            "        return None\n"
            "    if not data.valid:\n"
            "        raise ValueError('invalid')\n"
            "    if not data.ready:\n"
            "        return None\n"
            "    return do_work(data)"
        ),
        affected_files=_affected(finding),
        confidence=0.8,
        rationale=(
            "AI agents generate nested if/else chains instead of guard clauses "
            "(FMEA FM-06, RPN 105)."
        ),
    )]


@_register(SignalType.DEAD_CODE_ACCUMULATION)
def _gen_dca(finding: Finding) -> list[NegativeContext]:
    """FM-10 (RPN 96): Dead code generation."""
    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.DEAD_CODE_ACCUMULATION, finding),
        category=NegativeContextCategory.COMPLETENESS,
        source_signal=SignalType.DEAD_CODE_ACCUMULATION,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description="Unreachable or unused code detected. Do not add speculative code.",
        forbidden_pattern=(
            "# ANTI-PATTERN: Unused imports, functions, or constants\n"
            "import unused_module  # <- never referenced\n"
            "def helper_just_in_case(): ...  # <- never called"
        ),
        canonical_alternative=(
            "# REQUIRED: Only add code that is immediately used\n"
            "# Remove unused imports and speculative helper functions"
        ),
        affected_files=_affected(finding),
        confidence=0.75,
        rationale=(
            "AI agents add 'just in case' code that is never used "
            "(FMEA FM-10, RPN 96)."
        ),
    )]


@_register(SignalType.CIRCULAR_IMPORT)
def _gen_cir(finding: Finding) -> list[NegativeContext]:
    """FM-13 (RPN 96): Circular import introduction."""
    meta = finding.metadata
    cycle = meta.get("cycle", [])
    cycle_str = " -> ".join(str(c) for c in cycle[:5]) if cycle else "circular dependency"

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.CIRCULAR_IMPORT, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.CIRCULAR_IMPORT,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=(
            f"Circular import detected: {cycle_str}. "
            "Do not add imports that create or extend dependency cycles."
        ),
        forbidden_pattern=(
            f"# ANTI-PATTERN: Import creating circular dependency\n"
            f"# Existing cycle: {cycle_str}\n"
            "# Do NOT add imports between these modules"
        ),
        canonical_alternative=(
            "# REQUIRED: Break cycles via TYPE_CHECKING imports or interface modules\n"
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from module_in_cycle import Type  # type-only, no runtime cycle"
        ),
        affected_files=_affected(finding),
        confidence=0.9,
        rationale=(
            "AI agents cannot see the import graph "
            "(FMEA FM-13, RPN 96)."
        ),
    )]


@_register(SignalType.FAN_OUT_EXPLOSION)
def _gen_foe(finding: Finding) -> list[NegativeContext]:
    """FM-15 (RPN 96): Fan-out explosion."""
    meta = finding.metadata
    import_count = meta.get("import_count", 15)
    func_name = finding.symbol or "function"

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.FAN_OUT_EXPLOSION, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.FAN_OUT_EXPLOSION,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=(
            f"'{func_name}' imports {import_count} modules. "
            "Do not add more dependencies without consolidation."
        ),
        forbidden_pattern=(
            f"# ANTI-PATTERN: Function with {import_count}+ imports\n"
            "# Do not add more module-level imports to this file"
        ),
        canonical_alternative=(
            "# REQUIRED: Consolidate imports or split function\n"
            "# Consider extracting sub-functions into focused modules"
        ),
        affected_files=_affected(finding),
        confidence=0.75,
        rationale=(
            "AI agents accumulate dependencies without cohesion awareness "
            "(FMEA FM-15, RPN 96)."
        ),
    )]


@_register(SignalType.TEMPORAL_VOLATILITY)
def _gen_tvs(finding: Finding) -> list[NegativeContext]:
    """Frequent churn hotspot; avoid stacking risk on unstable areas."""
    meta = finding.metadata
    module = meta.get("module") or (
        finding.file_path.as_posix() if finding.file_path else "module"
    )
    change_frequency = meta.get("change_frequency_30d", meta.get("change_frequency", 0))
    recent_commits = meta.get("recent_commits", meta.get("commit_count", 0))

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.TEMPORAL_VOLATILITY, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.TEMPORAL_VOLATILITY,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=(
            f"Module '{module}' is a high-churn hotspot "
            f"(change_frequency={change_frequency}, recent_commits={recent_commits}). "
            "Do not add unrelated logic in volatile areas."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Piggybacking unrelated refactors onto a volatile module\n"
            f"# '{module}' is already changing rapidly"
        ),
        canonical_alternative=(
            "# REQUIRED: Keep changes minimal and isolated in volatile hotspots\n"
            "# Move unrelated improvements into separate, focused modules or follow-up PRs"
        ),
        affected_files=_affected(finding),
        confidence=0.8,
        rationale=(
            "High temporal volatility increases regression risk; unrelated changes in "
            "hotspots reduce reviewability and stability."
        ),
    )]


@_register(SignalType.SYSTEM_MISALIGNMENT)
def _gen_sms(finding: Finding) -> list[NegativeContext]:
    """Cross-module/system mismatch; enforce local system contracts."""
    meta = finding.metadata
    module = meta.get("module") or (
        finding.file_path.as_posix() if finding.file_path else "module"
    )
    expected_contract = meta.get(
        "expected_contract", meta.get("expected_pattern", "expected contract")
    )
    actual_behavior = meta.get("actual_behavior", meta.get("detected_pattern", "observed behavior"))

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.SYSTEM_MISALIGNMENT, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.SYSTEM_MISALIGNMENT,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=(
            f"System misalignment in '{module}': expected '{expected_contract}', "
            f"observed '{actual_behavior}'. Avoid extending conflicting behavior."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Reinforcing inconsistent system behavior\n"
            f"# Expected: {expected_contract}\n"
            f"# Observed: {actual_behavior}"
        ),
        canonical_alternative=(
            "# REQUIRED: Align changes with the established system contract\n"
            "# Prefer adapting this module to the dominant project behavior before adding features"
        ),
        affected_files=_affected(finding),
        confidence=0.78,
        rationale=(
            "System-level inconsistencies accumulate when AI-generated changes follow local "
            "outliers instead of repository-wide contracts."
        ),
    )]


@_register(SignalType.TS_ARCHITECTURE)
def _gen_tsa(finding: Finding) -> list[NegativeContext]:
    """TypeScript boundary violations should preserve architecture constraints."""
    meta = finding.metadata
    source = meta.get("source", meta.get("src_layer", "source"))
    target = meta.get("target", meta.get("dst_layer", "target"))
    rule = meta.get("rule", "TypeScript architecture boundary")

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.TS_ARCHITECTURE, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.TS_ARCHITECTURE,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=(
            f"TypeScript architecture constraint violated ({rule}): "
            f"'{source}' should not depend on '{target}'."
        ),
        forbidden_pattern=(
            "# ANTI-PATTERN: Cross-boundary TypeScript dependency\n"
            f"# Violated rule: {rule}\n"
            f"# {source} -> {target}"
        ),
        canonical_alternative=(
            "# REQUIRED: Respect TS architecture boundaries\n"
            "# Introduce shared interfaces/adapters instead of direct cross-layer imports"
        ),
        affected_files=_affected(finding),
        confidence=0.82,
        rationale=(
            "TypeScript modules drift quickly when cross-layer imports are added without "
            "respecting boundary rules."
        ),
    )]


@_register(SignalType.BYPASS_ACCUMULATION)
def _gen_bat(finding: Finding) -> list[NegativeContext]:
    """FM-11 (RPN 105): TODO/placeholder accumulation."""
    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.BYPASS_ACCUMULATION, finding),
        category=NegativeContextCategory.COMPLETENESS,
        source_signal=SignalType.BYPASS_ACCUMULATION,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description="Bypass pattern accumulation detected. Complete implementations fully.",
        forbidden_pattern=(
            "# ANTI-PATTERN: Placeholder or bypass code\n"
            "def important_function():\n"
            "    pass  # TODO: implement later\n"
            "    raise NotImplementedError"
        ),
        canonical_alternative=(
            "# REQUIRED: Implement completely or remove\n"
            "# Do not leave TODO/FIXME/NotImplementedError in production code"
        ),
        affected_files=_affected(finding),
        confidence=0.8,
        rationale=(
            "AI agents leave placeholder stubs instead of completing "
            "implementations (FMEA FM-11, RPN 105)."
        ),
    )]


@_register(SignalType.COGNITIVE_COMPLEXITY)
def _gen_cxs(finding: Finding) -> list[NegativeContext]:
    """Cognitive complexity warning."""
    func_name = finding.metadata.get("function_name", finding.symbol or "function")
    complexity = finding.metadata.get("complexity", 0)

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.COGNITIVE_COMPLEXITY, finding),
        category=NegativeContextCategory.COMPLEXITY,
        source_signal=SignalType.COGNITIVE_COMPLEXITY,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=f"'{func_name}' has complexity {complexity}. Keep new code simple.",
        forbidden_pattern=(
            "# ANTI-PATTERN: Adding more branches to already-complex function\n"
            f"# '{func_name}' complexity is already {complexity} -- do not increase"
        ),
        canonical_alternative=(
            "# REQUIRED: Extract helper functions to reduce complexity\n"
            "# Each function should have a single responsibility"
        ),
        affected_files=_affected(finding),
        confidence=0.8,
        rationale="High-complexity functions attract more complexity over time.",
    )]


@_register(SignalType.COHESION_DEFICIT)
def _gen_cod(finding: Finding) -> list[NegativeContext]:
    """Low module cohesion."""
    fp = finding.file_path.as_posix() if finding.file_path else "module"
    module = finding.metadata.get("module", fp)

    return [NegativeContext(
        anti_pattern_id=_neg_id(SignalType.COHESION_DEFICIT, finding),
        category=NegativeContextCategory.ARCHITECTURE,
        source_signal=SignalType.COHESION_DEFICIT,
        severity=finding.severity,
        scope=NegativeContextScope.MODULE,
        description=f"Module '{module}' has low cohesion. Do not add unrelated functionality.",
        forbidden_pattern=(
            f"# ANTI-PATTERN: Adding unrelated functions to '{module}'\n"
            "# This module already has low cohesion"
        ),
        canonical_alternative=(
            "# REQUIRED: Place new functions in the appropriate module\n"
            "# or create a new module if the concern is distinct"
        ),
        affected_files=_affected(finding),
        confidence=0.7,
        rationale="AI agents add functions to the nearest file rather than the right module.",
    )]


# Fallback generator for signals without specific generators
def _gen_fallback(finding: Finding) -> list[NegativeContext]:
    """Generic fallback for signals without a specific generator."""
    category = _SIGNAL_CATEGORY.get(finding.signal_type, NegativeContextCategory.ARCHITECTURE)
    policy = (
        "explicit_fallback_only"
        if finding.signal_type in _FALLBACK_ONLY_SIGNALS
        else "implicit_missing_policy"
    )
    return [NegativeContext(
        anti_pattern_id=_neg_id(finding.signal_type, finding),
        category=category,
        source_signal=finding.signal_type,
        severity=finding.severity,
        scope=_scope_from_finding(finding),
        description=finding.description,
        forbidden_pattern=f"# Drift signal: {finding.signal_type.value}\n# {finding.title}",
        canonical_alternative=finding.fix or "See drift_explain for remediation guidance",
        affected_files=_affected(finding),
        confidence=0.5,
        rationale=f"Drift signal '{finding.signal_type.value}' detected.",
        metadata={"fallback_policy": policy},
    )]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Severity score for prioritization
_SEVERITY_SCORE: dict[Severity, int] = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}


def findings_to_negative_context(
    findings: list[Finding],
    *,
    scope: str | None = None,
    target_file: str | None = None,
    max_items: int = 50,
) -> list[NegativeContext]:
    """Convert drift findings into negative context items for agents.

    Parameters
    ----------
    findings:
        List of Finding objects from a drift analysis.
    scope:
        Filter by scope: "file", "module", or "repo".  None = all.
    target_file:
        Filter to items affecting a specific file path.
    max_items:
        Maximum items to return (prioritized by severity).
    """
    items: list[NegativeContext] = []
    seen_ids: set[str] = set()

    for finding in findings:
        generator = _GENERATORS.get(finding.signal_type, _gen_fallback)
        generated = generator(finding)

        for item in generated:
            if item.anti_pattern_id in seen_ids:
                continue
            seen_ids.add(item.anti_pattern_id)

            # Filter by scope
            if scope:
                try:
                    requested = NegativeContextScope(scope)
                    if item.scope != requested:
                        continue
                except ValueError:
                    pass

            # Filter by target file
            if target_file and target_file not in item.affected_files:
                continue

            items.append(item)

    # Sort by severity (highest first), then confidence
    items.sort(
        key=lambda nc: (-_SEVERITY_SCORE.get(nc.severity, 0), -nc.confidence),
    )

    return items[:max_items]


def negative_context_to_dict(nc: NegativeContext) -> dict[str, Any]:
    """Serialize a NegativeContext to a JSON-compatible dict."""
    return {
        "anti_pattern_id": nc.anti_pattern_id,
        "category": nc.category.value,
        "source_signal": nc.source_signal.value,
        "severity": nc.severity.value,
        "scope": nc.scope.value,
        "description": nc.description,
        "forbidden_pattern": nc.forbidden_pattern,
        "canonical_alternative": nc.canonical_alternative,
        "affected_files": nc.affected_files,
        "confidence": nc.confidence,
        "rationale": nc.rationale,
        "metadata": nc.metadata,
    }
