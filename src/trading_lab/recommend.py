"""Rule-based, explainable PASS_TO_DEMO / NEEDS_REVIEW / REJECT recommendation.

Everything here runs locally against the metrics already extracted from the
report. There is no network call, no broker connection, and no trade
execution involved at any point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .metrics import Metrics

PASS_TO_DEMO = "PASS_TO_DEMO"
NEEDS_REVIEW = "NEEDS_REVIEW"
REJECT = "REJECT"

_SEVERITY = {PASS_TO_DEMO: 0, NEEDS_REVIEW: 1, REJECT: 2}


@dataclass(frozen=True)
class Thresholds:
    min_trades: int = 30
    min_profit_factor: float = 1.5
    reject_profit_factor: float = 1.0
    max_drawdown_pct: float = 20.0
    reject_drawdown_pct: float = 40.0
    min_recovery_factor: float = 2.0


@dataclass(frozen=True)
class Recommendation:
    verdict: str
    reasons: List[str] = field(default_factory=list)
    passed: List[str] = field(default_factory=list)


def evaluate(metrics: Metrics, thresholds: Thresholds = Thresholds()) -> Recommendation:
    verdict = PASS_TO_DEMO
    reasons: List[str] = []
    passed: List[str] = []

    def escalate(new_verdict: str, reason: str) -> None:
        nonlocal verdict
        reasons.append(reason)
        if _SEVERITY[new_verdict] > _SEVERITY[verdict]:
            verdict = new_verdict

    if metrics.total_trades is None or metrics.total_net_profit is None or metrics.profit_factor is None:
        escalate(
            NEEDS_REVIEW,
            "Core metrics (total trades, net profit, or profit factor) could not be read "
            "from the report; review it manually.",
        )

    if metrics.total_trades is not None:
        if metrics.total_trades < thresholds.min_trades:
            escalate(
                NEEDS_REVIEW,
                f"Only {metrics.total_trades} trades in the test, below the "
                f"{thresholds.min_trades}-trade minimum for a statistically meaningful sample.",
            )
        else:
            passed.append(f"Sample size OK: {metrics.total_trades} trades (>= {thresholds.min_trades}).")

    if metrics.total_net_profit is not None:
        if metrics.total_net_profit <= 0:
            escalate(REJECT, f"Net loss over the test period ({metrics.total_net_profit:.2f}).")
        else:
            passed.append(f"Net profit is positive ({metrics.total_net_profit:.2f}).")

    if metrics.profit_factor is not None:
        if metrics.profit_factor < thresholds.reject_profit_factor:
            escalate(REJECT, f"Profit factor {metrics.profit_factor:.2f} is below 1.0 (losing strategy).")
        elif metrics.profit_factor < thresholds.min_profit_factor:
            escalate(
                NEEDS_REVIEW,
                f"Profit factor {metrics.profit_factor:.2f} is positive but below the "
                f"{thresholds.min_profit_factor:.2f} comfort threshold.",
            )
        else:
            passed.append(
                f"Profit factor {metrics.profit_factor:.2f} meets the "
                f"{thresholds.min_profit_factor:.2f} threshold."
            )

    drawdown = metrics.balance_drawdown_relative_pct
    if drawdown is None:
        drawdown = metrics.equity_drawdown_relative_pct
    if drawdown is not None:
        if drawdown > thresholds.reject_drawdown_pct:
            escalate(
                REJECT,
                f"Relative drawdown {drawdown:.2f}% exceeds the "
                f"{thresholds.reject_drawdown_pct:.2f}% hard limit.",
            )
        elif drawdown > thresholds.max_drawdown_pct:
            escalate(
                NEEDS_REVIEW,
                f"Relative drawdown {drawdown:.2f}% exceeds the "
                f"{thresholds.max_drawdown_pct:.2f}% comfort threshold.",
            )
        else:
            passed.append(
                f"Relative drawdown {drawdown:.2f}% is within the "
                f"{thresholds.max_drawdown_pct:.2f}% comfort threshold."
            )

    if metrics.recovery_factor is not None:
        if metrics.recovery_factor < thresholds.min_recovery_factor:
            escalate(
                NEEDS_REVIEW,
                f"Recovery factor {metrics.recovery_factor:.2f} is below the "
                f"{thresholds.min_recovery_factor:.2f} comfort threshold.",
            )
        else:
            passed.append(
                f"Recovery factor {metrics.recovery_factor:.2f} meets the "
                f"{thresholds.min_recovery_factor:.2f} threshold."
            )

    if not reasons:
        reasons.append("All automated checks passed.")

    return Recommendation(verdict=verdict, reasons=reasons, passed=passed)
