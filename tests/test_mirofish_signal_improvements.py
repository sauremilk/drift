"""Tests for MiroFish-derived signal improvements.

V2: Method↔Function AST normalization (MDS) — self.attr collapsed to Name
V3: PFS repetition spread factor — high non-canonical counts boost score
V4: scripts/commands/cli layer recognition (AVS) — entry-point directories
"""

import ast
from pathlib import Path

from drift.ingestion.ast_parser import _compute_ast_ngrams
from drift.models import (
    ImportInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
)
from drift.signals.architecture_violation import (
    ArchitectureViolationSignal,
    _infer_layer,
)
from drift.signals.mutant_duplicates import _structural_similarity
from drift.signals.pattern_fragmentation import PatternFragmentationSignal

# ── V2: Method↔Function AST normalization ────────────────────────────────


class TestMethodFunctionNormalization:
    """self.attr and bare attr should produce identical AST n-grams."""

    def _ngrams_for_source(self, source: str) -> list[list[str]]:
        tree = ast.parse(source)
        func_node = tree.body[0]
        return _compute_ast_ngrams(func_node)

    def test_self_attr_collapsed_to_name(self):
        """self.x produces the same n-grams as bare x."""
        method_src = "def do(self):\n    return self.config"
        func_src = "def do(config):\n    return config"

        ng_method = self._ngrams_for_source(method_src)
        ng_func = self._ngrams_for_source(func_src)

        sim = _structural_similarity(
            [tuple(ng) for ng in ng_method],
            [tuple(ng) for ng in ng_func],
        )
        # After normalization, these should be very similar (>=0.8)
        assert sim >= 0.8, f"Expected >=0.8, got {sim}"

    def test_cls_attr_also_normalized(self):
        """cls.x should be treated the same as bare x."""
        classmethod_src = "def create(cls):\n    return cls.default_value"
        func_src = "def create(default_value):\n    return default_value"

        ng_cls = self._ngrams_for_source(classmethod_src)
        ng_func = self._ngrams_for_source(func_src)

        sim = _structural_similarity(
            [tuple(ng) for ng in ng_cls],
            [tuple(ng) for ng in ng_func],
        )
        assert sim >= 0.8, f"Expected >=0.8, got {sim}"

    def test_non_self_attribute_unchanged(self):
        """other.x should NOT be collapsed — only self/cls."""
        src_attr = "def f():\n    return obj.config"
        src_name = "def f():\n    return config"

        ng_attr = self._ngrams_for_source(src_attr)
        ng_name = self._ngrams_for_source(src_name)

        # These should differ (Attribute node preserved for non-self)
        assert ng_attr != ng_name

    def test_chained_self_access(self):
        """self.config.get('key') vs config.get('key') should be similar."""
        method_src = "def f(self):\n    return self.config.get('key')"
        func_src = "def f(config):\n    return config.get('key')"

        ng_method = self._ngrams_for_source(method_src)
        ng_func = self._ngrams_for_source(func_src)

        sim = _structural_similarity(
            [tuple(ng) for ng in ng_method],
            [tuple(ng) for ng in ng_func],
        )
        assert sim > 0.8, f"Expected >0.8, got {sim}"

    def test_complex_method_vs_function(self):
        """A realistic method vs function with self access patterns."""
        method_src = """\
def create_model(self):
    model = LLM(api_key=self.api_key, model=self.model_name)
    return model
"""
        func_src = """\
def create_model(api_key, model_name):
    model = LLM(api_key=api_key, model=model_name)
    return model
"""
        ng_method = self._ngrams_for_source(method_src)
        ng_func = self._ngrams_for_source(func_src)

        sim = _structural_similarity(
            [tuple(ng) for ng in ng_method],
            [tuple(ng) for ng in ng_func],
        )
        # After V2 normalization, these should be much more similar
        assert sim >= 0.75, f"Expected >=0.75 after normalization, got {sim}"


# ── V3: PFS spread factor ────────────────────────────────────────────────


def _make_pattern(
    category: PatternCategory,
    module: str,
    func: str,
    fingerprint: dict,
    line: int = 1,
) -> PatternInstance:
    return PatternInstance(
        category=category,
        file_path=Path(f"{module}/{func}.py"),
        function_name=func,
        start_line=line,
        end_line=line + 5,
        fingerprint=fingerprint,
    )


def _wrap(patterns: list[PatternInstance]) -> list[ParseResult]:
    return [
        ParseResult(
            file_path=Path("dummy.py"),
            language="python",
            patterns=patterns,
        )
    ]


class TestPFSSpreadFactor:
    """High-repetition fragmentation should score higher than low-repetition."""

    def test_many_deviations_boost_score(self):
        """20 instances with 3 variants should score higher than 3 instances."""
        fp_canonical = {"h": [{"type": "ValueError", "act": ["raise"]}]}
        fp_variant_a = {"h": [{"type": "Exception", "act": ["print"]}]}
        fp_variant_b = {"h": [{"type": "OSError", "act": ["log"]}]}

        # Small case: 3 instances, 3 variants (1 each)
        small_patterns = [
            _make_pattern(PatternCategory.ERROR_HANDLING, "mod", f"f{i}", fp)
            for i, fp in enumerate([fp_canonical, fp_variant_a, fp_variant_b])
        ]
        small_findings = PatternFragmentationSignal().analyze(
            _wrap(small_patterns),
            {},
            None,
        )
        assert len(small_findings) == 1
        small_score = small_findings[0].score

        # Large case: 20 instances — 10 canonical, 5 variant_a, 5 variant_b
        cat = PatternCategory.ERROR_HANDLING
        large_patterns = (
            [_make_pattern(cat, "mod", f"c{i}", fp_canonical) for i in range(10)]
            + [_make_pattern(cat, "mod", f"a{i}", fp_variant_a) for i in range(5)]
            + [_make_pattern(cat, "mod", f"b{i}", fp_variant_b) for i in range(5)]
        )
        large_findings = PatternFragmentationSignal().analyze(
            _wrap(large_patterns),
            {},
            None,
        )
        assert len(large_findings) == 1
        large_score = large_findings[0].score

        # The large case should score higher due to spread factor
        assert large_score > small_score, f"Expected large ({large_score}) > small ({small_score})"

    def test_spread_factor_only_activates_above_threshold(self):
        """1 non-canonical instance should NOT get a spread boost."""
        fp_a = {"h": [{"type": "ValueError", "act": ["raise"]}]}
        fp_b = {"h": [{"type": "Exception", "act": ["print"]}]}

        patterns = [
            _make_pattern(PatternCategory.ERROR_HANDLING, "mod", "f1", fp_a),
            _make_pattern(PatternCategory.ERROR_HANDLING, "mod", "f2", fp_a),
            _make_pattern(PatternCategory.ERROR_HANDLING, "mod", "f3", fp_b),
        ]
        findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
        assert len(findings) == 1

        # 2 canonical, 1 non-canonical → non_canonical_count=1 → no boost
        # Base score = 1 - 1/2 = 0.5, should remain exactly 0.5
        assert findings[0].score == 0.5

    def test_high_spread_capped_at_one(self):
        """Even extreme spreads should not produce scores > 1.0."""
        fp_a = {"h": [{"type": "ValueError", "act": ["raise"]}]}
        fp_b = {"h": [{"type": "Exception", "act": ["print"]}]}
        fp_c = {"h": [{"type": "OSError", "act": ["log"]}]}
        fp_d = {"h": [{"type": "RuntimeError", "act": ["other"]}]}
        fp_e = {"h": [{"type": "TypeError", "act": ["pass"]}]}

        # 5 variants × 10 instances each = 50 total, 10 canonical
        cat = PatternCategory.ERROR_HANDLING
        patterns = (
            [_make_pattern(cat, "mod", f"a{i}", fp_a) for i in range(10)]
            + [_make_pattern(cat, "mod", f"b{i}", fp_b) for i in range(10)]
            + [_make_pattern(cat, "mod", f"c{i}", fp_c) for i in range(10)]
            + [_make_pattern(cat, "mod", f"d{i}", fp_d) for i in range(10)]
            + [_make_pattern(cat, "mod", f"e{i}", fp_e) for i in range(10)]
        )
        findings = PatternFragmentationSignal().analyze(_wrap(patterns), {}, None)
        assert len(findings) == 1
        assert findings[0].score <= 1.0


# ── V4: scripts/commands/cli layer recognition ───────────────────────────


class TestScriptsLayerRecognition:
    """Entry-point directories should be recognized as layer 0."""

    def test_scripts_inferred_as_layer_zero(self):
        assert _infer_layer(Path("scripts/run_sim.py")) == 0

    def test_commands_inferred_as_layer_zero(self):
        assert _infer_layer(Path("commands/serve.py")) == 0

    def test_cli_inferred_as_layer_zero(self):
        assert _infer_layer(Path("cli/main.py")) == 0

    def test_scripts_upward_import_from_db_not_flagged(self):
        """scripts/ importing from db/ is downward (0→2) — no violation."""
        results = [
            ParseResult(
                file_path=Path("scripts/seed.py"),
                language="python",
                imports=[
                    ImportInfo(
                        source_file=Path("scripts/seed.py"),
                        imported_module="db.models",
                        imported_names=[],
                        line_number=1,
                    ),
                ],
            ),
            ParseResult(file_path=Path("db/models.py"), language="python"),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, None)
        upward = [f for f in findings if "Upward" in f.title]
        assert upward == []

    def test_db_importing_from_scripts_is_violation(self):
        """db/ importing from scripts/ is upward (2→0) — violation."""
        results = [
            ParseResult(
                file_path=Path("db/migrator.py"),
                language="python",
                imports=[
                    ImportInfo(
                        source_file=Path("db/migrator.py"),
                        imported_module="scripts.seed",
                        imported_names=[],
                        line_number=1,
                    ),
                ],
            ),
            ParseResult(file_path=Path("scripts/seed.py"), language="python"),
        ]
        signal = ArchitectureViolationSignal()
        findings = signal.analyze(results, {}, None)
        upward = [f for f in findings if "Upward" in f.title]
        assert len(upward) >= 1
