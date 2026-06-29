"""Assembles a structured, explainable decision report.

The verdict itself (PASS_TO_DEMO / NEEDS_REVIEW / REJECT) is produced by
:mod:`trading_lab.recommend`. This module wraps that verdict together with the
diagnostics into a single structured object that explains *why* the decision was
reached, how confident it is given data completeness, and what to do next.

Everything here is deterministic and local: same inputs produce the same
decision report, with every contributing reason listed. No network, no broker,
no trade execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .diagnostics import BLOCKING, HIGH, Diagnostic, max_severity
from .recommend import NEEDS_REVIEW, PASS_TO_DEMO, REJECT, Recommendation

# Confidence levels describe how much the available data supports the verdict.
CONFIDENCE_LOW = "LOW"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_HIGH = "HIGH"

_VERDICT_ACTION = {
    PASS_TO_DEMO: (
        "Consider forward-testing this strategy on a demo account. This tool "
        "places no trades; any next step is manual and outside this CLI."
    ),
    NEEDS_REVIEW: (
        "Review the flagged items, gather more trade history or tune parameters, "
        "and re-run this analysis before deciding on demo testing."
    ),
    REJECT: (
        "Do not advance this strategy to demo or live trading as-is. Revisit the "
        "strategy logic or parameters before re-testing."
    ),
}


@dataclass(frozen=True)
class DecisionReport:
    decision: str
    confidence: str
    blocking_reasons: List[str] = field(default_factory=list)
    review_reasons: List[str] = field(default_factory=list)
    passed: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)


def _confidence(diagnostics: List[Diagnostic]) -> str:
    """Confidence reflects data completeness and the seriousness of findings.

    A small sample makes any verdict low-confidence; missing data or a serious
    finding makes it medium; otherwise the data fully supports the verdict.
    """
    codes = {d.code for d in diagnostics}
    if "LOW_SAMPLE_SIZE" in codes:
        return CONFIDENCE_LOW
    if any(code.startswith("MISSING_") for code in codes) or max_severity(diagnostics) in (
        HIGH,
        BLOCKING,
    ):
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_HIGH


def build_decision(recommendation: Recommendation, diagnostics: List[Diagnostic]) -> DecisionReport:
    """Combine the verdict and diagnostics into a structured decision report."""
    verdict = recommendation.verdict

    blocking_reasons: List[str] = []
    review_reasons: List[str] = []
    if verdict == REJECT:
        blocking_reasons = list(recommendation.reasons)
    elif verdict == NEEDS_REVIEW:
        review_reasons = list(recommendation.reasons)

    # Next actions: lead with the verdict-level guidance, then append each
    # diagnostic's recommendation (most serious first, de-duplicated).
    next_actions: List[str] = [_VERDICT_ACTION[verdict]]
    seen = set(next_actions)
    for diag in diagnostics:
        if diag.recommendation not in seen:
            next_actions.append(diag.recommendation)
            seen.add(diag.recommendation)

    return DecisionReport(
        decision=verdict,
        confidence=_confidence(diagnostics),
        blocking_reasons=blocking_reasons,
        review_reasons=review_reasons,
        passed=list(recommendation.passed),
        next_actions=next_actions,
    )
