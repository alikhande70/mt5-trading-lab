"""Turns a parsed Strategy Tester report into a typed set of metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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
