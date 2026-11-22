"""
Anti-Phishing SOAR — Observable Enrichment & Threat Intelligence Pipeline
Academic SOAR Platform (Phase 3)
"""

__version__ = "1.0.0"

from .schemas import (
    ObservableType,
    Verdict,
    Confidence,
    EvidenceItem,
    EnrichedObservable,
    ValidationError,
    validate_and_normalize,
)
from .mock_intel import MockIntelEngine
from .risk_scorer import RiskScorer
from .enricher import EnrichmentPipeline

__all__ = [
    "ObservableType",
    "Verdict",
    "Confidence",
    "EvidenceItem",
    "EnrichedObservable",
    "ValidationError",
    "validate_and_normalize",
    "MockIntelEngine",
    "RiskScorer",
    "EnrichmentPipeline",
]
