from pathlib import Path

from trading_lab.cli import main
from trading_lab.compare import compare_deals
from trading_lab.recommend import REJECT

FIXTURES = Path(__file__).parent / "fixtures"

WINNING = FIXTURES / "sample_deals.csv"
LOSING = FIXTURES / "losing_deals.csv"
SEMI = FIXTURES / "semicolon_deals.csv"


def test_compare_deals_ranks_winning_above_losing():
    result = compare_deals([LOSING, WINNING])
    assert result.runs[0].name == WINNING.name
    assert result.best == WINNING.name
    assert result.runs[-1].decision == REJECT


def test_compare_deals_three_runs_sorted_by_score():
    result = compare_deals([WINNING, LOSING, SEMI])
    scores = [run.score.total for run in result.runs]
    assert scores == sorted(scores, reverse=True)
    assert len(result.runs) == 3


def test_compare_deals_with_initial_balance_enables_drawdown():
    result = compare_deals([WINNING, LOSING], initial_balance=10000.0)
    winning = next(r for r in result.runs if r.name == WINNING.name)
    assert winning.drawdown_pct is not None


def test_compare_deals_cli_writes_outputs(tmp_path, capsys):
    out_md = tmp_path / "cmp.md"
    json_out = tmp_path / "cmp.json"
    exit_code = main(
        [
            "compare-deals",
            str(WINNING),
            str(LOSING),
            "--out",
            str(out_md),
            "--json-out",
            str(json_out),
            "--format",
            "both",
        ]
    )
    assert exit_code == 0
    assert out_md.exists()
    assert json_out.exists()
    captured = capsys.readouterr()
    assert "Best candidate:" in captured.out


def test_compare_deals_cli_requires_two_files(capsys):
    exit_code = main(["compare-deals", str(WINNING), "--out", "x.md"])
    assert exit_code == 1
    assert "at least two" in capsys.readouterr().err


def test_compare_reports_cli_missing_file(tmp_path, capsys):
    exit_code = main(
        ["compare-reports", str(FIXTURES / "sample_strategy_tester_report.htm"),
         str(tmp_path / "nope.htm"), "--out", str(tmp_path / "c.md")]
    )
    assert exit_code == 1
    assert "not found" in capsys.readouterr().err
