"""Deterministic diagnostics over backtest metrics.

This layer goes beyond raw numbers: it flags *quality* problems with a result —
too small a sample, missing cost data, risk patterns, and overfit / too-good-to-
be-true signals — each as a :class:`Diagnostic` with a severity. Every rule is a
pure function of the metrics already computed locally; there is no network call,
no broker connection, and no trade execution anywhere here.

Each rule only fires when the data it needs is present, so a metric that could
not be derived never produces a misleading diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .metrics import DealsMetrics, Metrics
from .recommend import Thresholds

# Severity levels, ordered from least to most serious.
INFO = "INFO"
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
BLOCKING = "BLOCKING"

SEVERITY_RANK = {INFO: 0, LOW: 1, MEDIUM: 2, HIGH: 3, BLOCKING: 4}

# Diagnostic thresholds (deterministic, explainable constants). Sample-size and
# drawdown limits come from the shared Thresholds so they stay tunable via CLI.
PROFIT_FACTOR_SANITY_MAX = 10.0   # PF above this on a backtest is usually a red flag
HIGH_WIN_RATE_PCT = 70.0          # "relies on a high hit rate" territory
LOW_PAYOFF_RATIO = 0.7            # paired with a high win rate, this is fragile
BAD_RR_PAYOFF_RATIO = 0.5         # losers more than ~2x the size of winners
FAT_TAIL_LOSS_MULTIPLE = 4.0      # largest loss this many times the average loss
DRAWDOWN_CLUSTER_MIN_STREAK = 5   # consecutive losing trades that cluster drawdown
UNSTABLE_EQUITY_RATIO = 0.5       # peak drawdown vs. final equity


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    recommendation: str


@dataclass(frozen=True)
class DiagnosticInput:
    """Normalized scalars the diagnostic rules operate on, built from either a
    Strategy Tester report or a CSV deals ledger so the rules stay in one place.
    """

    source: str
    trade_count: Optional[int] = None
    net_profit: Optional[float] = None
    profit_factor: Optional[float] = None
    drawdown_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    payoff_ratio: Optional[float] = None
    average_loss: Optional[float] = None
    largest_loss: Optional[float] = None
    max_consecutive_losses: Optional[int] = None
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    has_initial_balance: bool = True
    has_commission: bool = True
    has_swap: bool = True
    has_symbol: bool = True


def input_from_report(metrics: Metrics) -> DiagnosticInput:
    drawdown = metrics.balance_drawdown_relative_pct
    if drawdown is None:
        drawdown = metrics.equity_drawdown_relative_pct
    return DiagnosticInput(
        source="strategy_tester_html",
        trade_count=metrics.total_trades,
        net_profit=metrics.total_net_profit,
        profit_factor=metrics.profit_factor,
        drawdown_pct=drawdown,
        win_rate_pct=metrics.profit_trades_pct,
        payoff_ratio=metrics.win_loss_ratio,
        average_loss=metrics.average_loss_trade,
        largest_loss=metrics.largest_loss_trade,
        max_consecutive_losses=metrics.max_consecutive_losses,
        # An HTML summary carries no per-trade ledger, so cost-completeness and
        # the per-trade series are simply not part of this source.
        has_initial_balance=metrics.initial_deposit is not None,
        has_commission=True,
        has_swap=True,
        has_symbol=metrics.symbol is not None,
    )


def input_from_deals(metrics: DealsMetrics) -> DiagnosticInput:
    return DiagnosticInput(
        source="deals_csv",
        trade_count=metrics.total_trades,
        net_profit=metrics.net_profit,
        profit_factor=metrics.profit_factor,
        drawdown_pct=metrics.max_drawdown_pct,
        win_rate_pct=metrics.win_rate_pct,
        payoff_ratio=metrics.payoff_ratio,
        average_loss=metrics.average_loss,
        largest_loss=metrics.largest_loss,
        max_consecutive_losses=metrics.max_consecutive_losses,
        equity_curve=list(metrics.equity_curve),
        drawdown_curve=list(metrics.drawdown_curve),
        has_initial_balance=metrics.initial_balance is not None,
        has_commission=metrics.total_commission is not None,
        has_swap=metrics.total_swap is not None,
        has_symbol=metrics.symbol_distribution is not None,
    )


def _sample_diagnostics(d: DiagnosticInput, t: Thresholds, out: List[Diagnostic]) -> None:
    if d.trade_count is not None and d.trade_count < t.min_trades:
        out.append(
            Diagnostic(
                code="LOW_SAMPLE_SIZE",
                severity=HIGH,
                message=(
                    f"Only {d.trade_count} closed trades were found, below the "
                    f"{t.min_trades}-trade minimum for a meaningful sample."
                ),
                recommendation="Run a longer backtest or test more symbols/timeframes.",
            )
        )
    if d.source == "deals_csv" and not d.has_initial_balance:
        out.append(
            Diagnostic(
                code="MISSING_INITIAL_BALANCE",
                severity=MEDIUM,
                message="No initial balance was provided, so percentage drawdown cannot be computed.",
                recommendation="Pass --initial-balance to enable percentage-drawdown checks.",
            )
        )
    if d.source == "deals_csv" and not d.has_commission:
        out.append(
            Diagnostic(
                code="MISSING_COMMISSION",
                severity=LOW,
                message="No commission column was present; trading costs may be understated.",
                recommendation="Export a CSV that includes commission, or map the commission column.",
            )
        )
    if d.source == "deals_csv" and not d.has_swap:
        out.append(
            Diagnostic(
                code="MISSING_SWAP",
                severity=LOW,
                message="No swap column was present; overnight financing costs may be understated.",
                recommendation="Export a CSV that includes swap, or map the swap column.",
            )
        )
    if d.source == "deals_csv" and not d.has_symbol:
        out.append(
            Diagnostic(
                code="MISSING_SYMBOL",
                severity=INFO,
                message="No symbol column was present; per-symbol distribution is unavailable.",
                recommendation="Map the symbol column to enable per-symbol breakdowns.",
            )
        )


def _risk_diagnostics(d: DiagnosticInput, t: Thresholds, out: List[Diagnostic]) -> None:
    if d.drawdown_pct is not None and d.drawdown_pct > t.max_drawdown_pct:
        blocking = d.drawdown_pct > t.reject_drawdown_pct
        out.append(
            Diagnostic(
                code="HIGH_DRAWDOWN",
                severity=BLOCKING if blocking else HIGH,
                message=(
                    f"Relative drawdown {d.drawdown_pct:.2f}% exceeds the "
                    f"{t.max_drawdown_pct:.2f}% comfort threshold"
                    + (f" and the {t.reject_drawdown_pct:.2f}% hard limit." if blocking else ".")
                ),
                recommendation="Reduce position sizing or revisit risk management before a demo.",
            )
        )
    if (
        d.largest_loss is not None
        and d.average_loss
        and abs(d.largest_loss) > FAT_TAIL_LOSS_MULTIPLE * abs(d.average_loss)
    ):
        out.append(
            Diagnostic(
                code="FAT_TAIL_LOSS",
                severity=MEDIUM,
                message=(
                    f"The largest loss ({d.largest_loss:.2f}) is more than "
                    f"{FAT_TAIL_LOSS_MULTIPLE:.0f}x the average loss, suggesting fat-tail risk."
                ),
                recommendation="Check for missing stop-losses or outlier trades driving the result.",
            )
        )
    if d.max_consecutive_losses is not None and d.max_consecutive_losses >= DRAWDOWN_CLUSTER_MIN_STREAK:
        out.append(
            Diagnostic(
                code="DRAWDOWN_CLUSTER",
                severity=MEDIUM,
                message=(
                    f"A streak of {d.max_consecutive_losses} consecutive losses indicates "
                    "drawdown clustering."
                ),
                recommendation="Confirm the equity curve can survive the worst observed losing streak.",
            )
        )
    if d.equity_curve and d.drawdown_curve:
        final_equity = d.equity_curve[-1]
        peak_drawdown = max(d.drawdown_curve)
        if final_equity > 0 and peak_drawdown > UNSTABLE_EQUITY_RATIO * final_equity:
            out.append(
                Diagnostic(
                    code="UNSTABLE_EQUITY_CURVE",
                    severity=MEDIUM,
                    message=(
                        f"Peak drawdown ({peak_drawdown:.2f}) is more than "
                        f"{UNSTABLE_EQUITY_RATIO:.0%} of final equity ({final_equity:.2f}); "
                        "the equity curve is unstable."
                    ),
                    recommendation="Look for a smoother equity curve before trusting the net result.",
                )
            )


def _overfit_diagnostics(d: DiagnosticInput, t: Thresholds, out: List[Diagnostic]) -> List[str]:
    flags: List[str] = []
    if d.profit_factor is not None and d.profit_factor > PROFIT_FACTOR_SANITY_MAX:
        flags.append("unrealistic_profit_factor")
        out.append(
            Diagnostic(
                code="UNREALISTIC_PROFIT_FACTOR",
                severity=HIGH,
                message=(
                    f"Profit factor {d.profit_factor:.2f} is implausibly high (> "
                    f"{PROFIT_FACTOR_SANITY_MAX:.0f}); often a sign of curve-fitting or a tiny sample."
                ),
                recommendation="Re-test out-of-sample and on a larger period before trusting this.",
            )
        )
    if (
        d.win_rate_pct is not None
        and d.win_rate_pct > HIGH_WIN_RATE_PCT
        and d.payoff_ratio is not None
        and d.payoff_ratio < LOW_PAYOFF_RATIO
    ):
        flags.append("high_winrate_low_payoff")
        out.append(
            Diagnostic(
                code="HIGH_WINRATE_LOW_PAYOFF",
                severity=MEDIUM,
                message=(
                    f"A high win rate ({d.win_rate_pct:.1f}%) paired with a low payoff "
                    f"ratio ({d.payoff_ratio:.2f}) is fragile: a few big losers can erase many wins."
                ),
                recommendation="Confirm the strategy survives its worst losers, not just its win rate.",
            )
        )
    if d.payoff_ratio is not None and d.payoff_ratio < BAD_RR_PAYOFF_RATIO:
        flags.append("bad_rr_profile")
        out.append(
            Diagnostic(
                code="BAD_RR_PROFILE",
                severity=MEDIUM,
                message=(
                    f"Payoff ratio {d.payoff_ratio:.2f} means average losers are more than "
                    "twice the size of average winners."
                ),
                recommendation="Review the risk/reward profile; small edges erode quickly with costs.",
            )
        )
    if d.trade_count is not None and d.trade_count < t.min_trades:
        flags.append("low_sample")
    if len(flags) >= 2:
        out.append(
            Diagnostic(
                code="OVERFIT_RISK",
                severity=HIGH,
                message=(
                    "Multiple overfit / too-good-to-be-true signals are present "
                    f"({', '.join(flags)}); treat the result with caution."
                ),
                recommendation="Validate out-of-sample and on a larger, independent dataset.",
            )
        )
    return flags


def run_diagnostics(d: DiagnosticInput, thresholds: Thresholds = Thresholds()) -> List[Diagnostic]:
    """Apply every diagnostic rule and return the findings sorted by severity."""
    out: List[Diagnostic] = []
    _sample_diagnostics(d, thresholds, out)
    _risk_diagnostics(d, thresholds, out)
    _overfit_diagnostics(d, thresholds, out)
    out.sort(key=lambda diag: (-SEVERITY_RANK[diag.severity], diag.code))
    return out


def max_severity(diagnostics: List[Diagnostic]) -> Optional[str]:
    """Return the most serious severity among ``diagnostics`` (or ``None``)."""
    if not diagnostics:
        return None
    return max(diagnostics, key=lambda diag: SEVERITY_RANK[diag.severity]).severity
