"""Detection signals for Drift analysis."""

from drift.signals.architecture_violation import ArchitectureViolationSignal
from drift.signals.base import BaseSignal
from drift.signals.broad_exception_monoculture import BroadExceptionMonocultureSignal
from drift.signals.bypass_accumulation import BypassAccumulationSignal
from drift.signals.circular_import import CircularImportSignal
from drift.signals.co_change_coupling import CoChangeCouplingSignal
from drift.signals.cognitive_complexity import CognitiveComplexitySignal
from drift.signals.cohesion_deficit import CohesionDeficitSignal
from drift.signals.dead_code_accumulation import DeadCodeAccumulationSignal
from drift.signals.doc_impl_drift import DocImplDriftSignal
from drift.signals.exception_contract_drift import ExceptionContractDriftSignal
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal
from drift.signals.fan_out_explosion import FanOutExplosionSignal
from drift.signals.guard_clause_deficit import GuardClauseDeficitSignal
from drift.signals.mutant_duplicates import MutantDuplicateSignal
from drift.signals.naming_contract_violation import NamingContractViolationSignal
from drift.signals.pattern_fragmentation import PatternFragmentationSignal
from drift.signals.phantom_reference import PhantomReferenceSignal
from drift.signals.system_misalignment import SystemMisalignmentSignal
from drift.signals.temporal_volatility import TemporalVolatilitySignal
from drift.signals.test_polarity_deficit import TestPolarityDeficitSignal
from drift.signals.ts_architecture import TypeScriptArchitectureSignal

__all__ = [
    "BaseSignal",
    "PatternFragmentationSignal",
    "ArchitectureViolationSignal",
    "MutantDuplicateSignal",
    "ExplainabilityDeficitSignal",
    "TemporalVolatilitySignal",
    "SystemMisalignmentSignal",
    "DocImplDriftSignal",
    "BroadExceptionMonocultureSignal",
    "TestPolarityDeficitSignal",
    "GuardClauseDeficitSignal",
    "CoChangeCouplingSignal",
    "CohesionDeficitSignal",
    "NamingContractViolationSignal",
    "BypassAccumulationSignal",
    "ExceptionContractDriftSignal",
    "TypeScriptArchitectureSignal",
    "CognitiveComplexitySignal",
    "FanOutExplosionSignal",
    "CircularImportSignal",
    "DeadCodeAccumulationSignal",
    "PhantomReferenceSignal",
]
