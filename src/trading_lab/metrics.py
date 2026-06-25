"""Turns a parsed Strategy Tester report or CSV deals export into typed metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

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
    total_commission = _sum_optional(deal.commission for deal in deals)
    total_swap = _sum_optional(deal.swap for deal in deals)
    net_profit = sum(profits) + (total_commission or 0.0) + (total_swap or 0.0)

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
        max_drawdown_amount=_max_drawdown_amount(equity_curve),
        max_drawdown_pct=_max_drawdown_pct(initial_balance, equity_curve),
        total_commission=total_commission,
        total_swap=total_swap,
        initial_balance=initial_balance,
    )
