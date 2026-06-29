"""Turns a parsed Strategy Tester report or CSV deals export into typed metrics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Union

from .csv_deals import Deal, ParsedDeals
from .html_report import ParsedReport


@dataclass(frozen=True)
class Metrics:
    symbol: Optional[str]
    period: Optional[str]
    initial_deposit: Optional[float]
    total_net_profit: Optional[float]
    gross_profit: Optional[float]
    gross_loss: Optional[float]
    profit_factor: Optional[float]
    expected_payoff: Optional[float]
    recovery_factor: Optional[float]
    sharpe_ratio: Optional[float]
    balance_drawdown_relative_pct: Optional[float]
    equity_drawdown_relative_pct: Optional[float]
    total_trades: Optional[int]
    profit_trades_pct: Optional[float]
    loss_trades_pct: Optional[float]
    short_trades_won_pct: Optional[float]
    long_trades_won_pct: Optional[float]
    largest_profit_trade: Optional[float]
    largest_loss_trade: Optional[float]
    average_profit_trade: Optional[float]
    average_loss_trade: Optional[float]
    max_consecutive_wins: Optional[int]
    max_consecutive_losses: Optional[int]
    win_loss_ratio: Optional[float]


def _field(report: ParsedReport, key: str):
    return report.fields.get(key)


def _num(report: ParsedReport, key: str) -> Optional[float]:
    field = _field(report, key)
    return field.amount() if field else None


def _pct(report: ParsedReport, key: str) -> Optional[float]:
    field = _field(report, key)
    return field.percent() if field else None


def _text(report: ParsedReport, key: str) -> Optional[str]:
    field = _field(report, key)
    return field.raw if field else None


def _as_int(value: Optional[float]) -> Optional[int]:
    return int(round(value)) if value is not None else None


def compute_metrics(report: ParsedReport) -> Metrics:
    average_profit_trade = _num(report, "average_profit_trade")
    average_loss_trade = _num(report, "average_loss_trade")

    win_loss_ratio = None
    if average_profit_trade is not None and average_loss_trade:
        win_loss_ratio = average_profit_trade / abs(average_loss_trade)

    drawdown_relative = _pct(report, "balance_drawdown_relative")
    if drawdown_relative is None:
        drawdown_relative = _pct(report, "equity_drawdown_relative")

    return Metrics(
        symbol=_text(report, "symbol"),
        period=_text(report, "period"),
        initial_deposit=_num(report, "initial_deposit"),
        total_net_profit=_num(report, "total_net_profit"),
        gross_profit=_num(report, "gross_profit"),
        gross_loss=_num(report, "gross_loss"),
        profit_factor=_num(report, "profit_factor"),
        expected_payoff=_num(report, "expected_payoff"),
        recovery_factor=_num(report, "recovery_factor"),
        sharpe_ratio=_num(report, "sharpe_ratio"),
        balance_drawdown_relative_pct=_pct(report, "balance_drawdown_relative"),
        equity_drawdown_relative_pct=_pct(report, "equity_drawdown_relative"),
        total_trades=_as_int(_num(report, "total_trades")),
        profit_trades_pct=_pct(report, "profit_trades_of_total"),
        loss_trades_pct=_pct(report, "loss_trades_of_total"),
        short_trades_won_pct=_pct(report, "short_trades_won"),
        long_trades_won_pct=_pct(report, "long_trades_won"),
        largest_profit_trade=_num(report, "largest_profit_trade"),
        largest_loss_trade=_num(report, "largest_loss_trade"),
        average_profit_trade=average_profit_trade,
        average_loss_trade=average_loss_trade,
        # MT5 lists the count before the dollar amount for these two fields
        # (e.g. "5 (430.00)"), so the count is the non-percent primary value.
        max_consecutive_wins=_as_int(_num(report, "maximum_consecutive_wins")),
        max_consecutive_losses=_as_int(_num(report, "maximum_consecutive_losses")),
        win_loss_ratio=win_loss_ratio,
    )


@dataclass(frozen=True)
class DealsMetrics:
    total_trades: int
    net_profit: float
    gross_profit: float
    gross_loss: float
    profit_factor: Optional[float]
    win_count: int
    loss_count: int
    win_rate_pct: float
    loss_rate_pct: float
    average_win: Optional[float]
    average_loss: Optional[float]
    largest_win: Optional[float]
    largest_loss: Optional[float]
    payoff_ratio: Optional[float]
    max_consecutive_wins: int
    max_consecutive_losses: int
    equity_curve: List[float] = field(default_factory=list)
    max_drawdown_amount: float = 0.0
    max_drawdown_pct: Optional[float] = None
    total_commission: Optional[float] = None
    total_swap: Optional[float] = None
    initial_balance: Optional[float] = None
    average_trade: Optional[float] = None
    expectancy: Optional[float] = None
    recovery_factor: Optional[float] = None
    drawdown_curve: List[float] = field(default_factory=list)
    long_count: Optional[int] = None
    short_count: Optional[int] = None
    symbol_distribution: Optional[Dict[str, int]] = None
    monthly_returns: Optional[Dict[str, float]] = None


def _max_consecutive(values: List[float], predicate: Callable[[float], bool]) -> int:
    best = current = 0
    for value in values:
        if predicate(value):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _cumulative(values: List[float]) -> List[float]:
    running = 0.0
    curve = []
    for value in values:
        running += value
        curve.append(running)
    return curve


def _max_drawdown_amount(equity_curve: List[float]) -> float:
    """Largest peak-to-trough decline of the cumulative-profit curve (starts at 0)."""
    peak = 0.0
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_dd = max(max_dd, peak - value)
    return max_dd


def _max_drawdown_pct(initial_balance: Optional[float], equity_curve: List[float]) -> Optional[float]:
    if not initial_balance or initial_balance <= 0:
        return None
    peak_balance = initial_balance
    max_dd_pct = 0.0
    for cumulative_profit in equity_curve:
        balance = initial_balance + cumulative_profit
        peak_balance = max(peak_balance, balance)
        if peak_balance > 0:
            max_dd_pct = max(max_dd_pct, (peak_balance - balance) / peak_balance * 100.0)
    return max_dd_pct


def _drawdown_curve(equity_curve: List[float]) -> List[float]:
    """Per-point drawdown (peak-to-current decline) of the cumulative-profit curve."""
    peak = 0.0
    curve: List[float] = []
    for value in equity_curve:
        peak = max(peak, value)
        curve.append(peak - value)
    return curve


_MONTH_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})")


def _month_key(time_value: Optional[str]) -> Optional[str]:
    """Extract a ``YYYY-MM`` key from a raw MT5 time string, or ``None``."""
    if not time_value:
        return None
    match = _MONTH_RE.search(time_value)
    if not match:
        return None
    year, month = match.group(1), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return f"{year}-{month:02d}"


def _sum_optional(values) -> Optional[float]:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def compute_deals_metrics(parsed: ParsedDeals, initial_balance: Optional[float] = None) -> DealsMetrics:
    deals: List[Deal] = parsed.deals
    profits = [deal.profit for deal in deals]
    total_trades = len(profits)

    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p < 0]
    win_count = len(wins)
    loss_count = len(losses)

    gross_profit = sum(wins)
    gross_loss = sum(losses)
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss else None

    average_win = (gross_profit / win_count) if win_count else None
    average_loss = (gross_loss / loss_count) if loss_count else None
    payoff_ratio = (average_win / abs(average_loss)) if average_win is not None and average_loss else None

    equity_curve = _cumulative(profits)
    drawdown_curve = _drawdown_curve(equity_curve)
    max_drawdown_amount = _max_drawdown_amount(equity_curve)
    total_commission = _sum_optional(deal.commission for deal in deals)
    total_swap = _sum_optional(deal.swap for deal in deals)
    net_profit = sum(profits) + (total_commission or 0.0) + (total_swap or 0.0)

    average_trade = (sum(profits) / total_trades) if total_trades else None
    win_prob = (win_count / total_trades) if total_trades else 0.0
    loss_prob = (loss_count / total_trades) if total_trades else 0.0
    expectancy = None
    if average_win is not None or average_loss is not None:
        expectancy = win_prob * (average_win or 0.0) + loss_prob * (average_loss or 0.0)
    recovery_factor = (net_profit / max_drawdown_amount) if max_drawdown_amount > 0 else None

    # Long/short split is only available when the source carries a usable
    # direction; otherwise both counts stay None (reported as unavailable).
    directions = [deal.direction for deal in deals if deal.direction in ("long", "short")]
    long_count = short_count = None
    if directions:
        long_count = sum(1 for d in directions if d == "long")
        short_count = sum(1 for d in directions if d == "short")

    symbols = [deal.symbol for deal in deals if deal.symbol]
    symbol_distribution: Optional[Dict[str, int]] = None
    if symbols:
        symbol_distribution = {}
        for sym in symbols:
            symbol_distribution[sym] = symbol_distribution.get(sym, 0) + 1

    monthly_returns: Optional[Dict[str, float]] = None
    month_keys = [(_month_key(deal.time), deal.profit) for deal in deals]
    if any(key is not None for key, _ in month_keys):
        monthly_returns = {}
        for key, profit in month_keys:
            if key is None:
                continue
            monthly_returns[key] = monthly_returns.get(key, 0.0) + profit

    return DealsMetrics(
        total_trades=total_trades,
        net_profit=net_profit,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        win_count=win_count,
        loss_count=loss_count,
        win_rate_pct=(win_count / total_trades * 100.0) if total_trades else 0.0,
        loss_rate_pct=(loss_count / total_trades * 100.0) if total_trades else 0.0,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=max(wins) if wins else None,
        largest_loss=min(losses) if losses else None,
        payoff_ratio=payoff_ratio,
        max_consecutive_wins=_max_consecutive(profits, lambda p: p > 0),
        max_consecutive_losses=_max_consecutive(profits, lambda p: p < 0),
        equity_curve=equity_curve,
        max_drawdown_amount=max_drawdown_amount,
        max_drawdown_pct=_max_drawdown_pct(initial_balance, equity_curve),
        total_commission=total_commission,
        total_swap=total_swap,
        initial_balance=initial_balance,
        average_trade=average_trade,
        expectancy=expectancy,
        recovery_factor=recovery_factor,
        drawdown_curve=drawdown_curve,
        long_count=long_count,
        short_count=short_count,
        symbol_distribution=symbol_distribution,
        monthly_returns=monthly_returns,
    )


# --- Machine-readable metric layer ------------------------------------------
#
# ``MetricResult`` is the normalized, JSON-friendly view of a single metric.
# When a metric cannot be derived from the available data it is marked
# ``available=False`` with a human-readable reason instead of being guessed.

MetricValue = Union[float, int, str, List[float], Dict[str, float], Dict[str, int], None]

_HTML_SOURCE = "strategy_tester_html"
_DEALS_SOURCE = "deals_csv"


@dataclass(frozen=True)
class MetricResult:
    name: str
    value: MetricValue
    available: bool
    reason_if_unavailable: Optional[str]
    source: str
    warnings: List[str] = field(default_factory=list)


def _is_empty(value: MetricValue) -> bool:
    return value is None or value == {} or value == []


def _mr(
    name: str,
    value: MetricValue,
    source: str,
    reason: str = "not present in this source",
    warnings: Optional[List[str]] = None,
) -> MetricResult:
    available = not _is_empty(value)
    return MetricResult(
        name=name,
        value=value if available else None,
        available=available,
        reason_if_unavailable=None if available else reason,
        source=source,
        warnings=list(warnings or []),
    )


_NO_PER_TRADE = "per-trade data is not available from an HTML summary report"


def report_metric_results(metrics: Metrics) -> List[MetricResult]:
    """Normalize HTML-report metrics into a JSON-friendly ``MetricResult`` list."""
    s = _HTML_SOURCE
    return [
        _mr("symbol", metrics.symbol, s),
        _mr("period", metrics.period, s),
        _mr("initial_deposit", metrics.initial_deposit, s),
        _mr("net_profit", metrics.total_net_profit, s),
        _mr("gross_profit", metrics.gross_profit, s),
        _mr("gross_loss", metrics.gross_loss, s),
        _mr("profit_factor", metrics.profit_factor, s),
        _mr("expected_payoff", metrics.expected_payoff, s),
        _mr("recovery_factor", metrics.recovery_factor, s),
        _mr("sharpe_ratio", metrics.sharpe_ratio, s),
        _mr("max_drawdown_percent", metrics.balance_drawdown_relative_pct
            if metrics.balance_drawdown_relative_pct is not None
            else metrics.equity_drawdown_relative_pct, s),
        _mr("trade_count", metrics.total_trades, s),
        _mr("win_rate", metrics.profit_trades_pct, s),
        _mr("loss_rate", metrics.loss_trades_pct, s),
        _mr("largest_win", metrics.largest_profit_trade, s),
        _mr("largest_loss", metrics.largest_loss_trade, s),
        _mr("average_win", metrics.average_profit_trade, s),
        _mr("average_loss", metrics.average_loss_trade, s),
        _mr("payoff_ratio", metrics.win_loss_ratio, s),
        _mr("max_consecutive_wins", metrics.max_consecutive_wins, s),
        _mr("max_consecutive_losses", metrics.max_consecutive_losses, s),
        _mr("equity_curve", None, s, _NO_PER_TRADE),
        _mr("drawdown_curve", None, s, _NO_PER_TRADE),
        _mr("monthly_returns", None, s, _NO_PER_TRADE),
        _mr("symbol_distribution", None, s, _NO_PER_TRADE),
        _mr("long_short_split", None, s, _NO_PER_TRADE),
    ]


def deals_metric_results(metrics: DealsMetrics) -> List[MetricResult]:
    """Normalize CSV-deals metrics into a JSON-friendly ``MetricResult`` list."""
    s = _DEALS_SOURCE
    long_short = None
    if metrics.long_count is not None and metrics.short_count is not None:
        long_short = {"long": metrics.long_count, "short": metrics.short_count}
    return [
        _mr("net_profit", metrics.net_profit, s),
        _mr("gross_profit", metrics.gross_profit, s),
        _mr("gross_loss", metrics.gross_loss, s),
        _mr("profit_factor", metrics.profit_factor, s,
            "no losing trades, so profit factor is undefined"),
        _mr("recovery_factor", metrics.recovery_factor, s,
            "no drawdown occurred, so recovery factor is undefined"),
        _mr("trade_count", metrics.total_trades, s),
        _mr("win_count", metrics.win_count, s),
        _mr("loss_count", metrics.loss_count, s),
        _mr("win_rate", metrics.win_rate_pct, s),
        _mr("loss_rate", metrics.loss_rate_pct, s),
        _mr("average_trade", metrics.average_trade, s),
        _mr("average_win", metrics.average_win, s, "no winning trades in the sample"),
        _mr("average_loss", metrics.average_loss, s, "no losing trades in the sample"),
        _mr("payoff_ratio", metrics.payoff_ratio, s),
        _mr("expectancy", metrics.expectancy, s),
        _mr("largest_win", metrics.largest_win, s, "no winning trades in the sample"),
        _mr("largest_loss", metrics.largest_loss, s, "no losing trades in the sample"),
        _mr("max_consecutive_wins", metrics.max_consecutive_wins, s),
        _mr("max_consecutive_losses", metrics.max_consecutive_losses, s),
        _mr("max_drawdown_absolute", metrics.max_drawdown_amount, s),
        _mr("max_drawdown_percent", metrics.max_drawdown_pct, s,
            "no --initial-balance provided, so percentage drawdown cannot be computed"),
        _mr("total_commission", metrics.total_commission, s,
            "no commission column present in the source"),
        _mr("total_swap", metrics.total_swap, s,
            "no swap column present in the source"),
        _mr("equity_curve", metrics.equity_curve, s),
        _mr("drawdown_curve", metrics.drawdown_curve, s),
        _mr("long_short_split", long_short, s,
            "deal direction (buy/sell) is not present in the source"),
        _mr("symbol_distribution", metrics.symbol_distribution, s,
            "symbol column is not present in the source"),
        _mr("monthly_returns", metrics.monthly_returns, s,
            "deal time column is not present in the source"),
    ]
