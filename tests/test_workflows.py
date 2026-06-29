from pathlib import Path

from trading_lab.cli import main
from trading_lab.workflows import (
    workflow_demo_readiness_review,
    workflow_multi_backtest_comparison,
    workflow_single_backtest_review,
)

FIXTURES = Path(__file__).parent / "fixtures"
GOOD = FIXTURES / "sample_strategy_tester_report.htm"
LOSING = FIXTURES / "losing_strategy_report.htm"
WINNING_CSV = FIXTURES / "sample_deals.csv"


def test_single_review_returns_markdown():
    md = workflow_single_backtest_review(GOOD)
    assert "MT5 Strategy Tester Report Analysis" in md
    assert "PASS_TO_DEMO" in md


def test_multi_comparison_returns_ranking():
    md = workflow_multi_backtest_comparison([GOOD, LOSING])
    assert "MT5 Backtest Comparison" in md
    assert "Ranking" in md


def test_demo_readiness_review_prefers_deals():
    md = workflow_demo_readiness_review(report_path=GOOD, deals_path=WINNING_CSV)
    assert "Demo-Readiness" in md


def test_demo_readiness_review_requires_a_source():
    try:
        workflow_demo_readiness_review()
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_workflow_single_cli(tmp_path, capsys):
    out = tmp_path / "review.md"
    exit_code = main(["workflow", "single-review", "--report", str(GOOD), "--out", str(out)])
    assert exit_code == 0
    assert out.exists()
    assert "Review written to:" in capsys.readouterr().out


def test_workflow_compare_cli(tmp_path, capsys):
    out = tmp_path / "comparison.md"
    exit_code = main(
        ["workflow", "compare-runs", "--reports", str(GOOD), str(LOSING), "--out", str(out)]
    )
    assert exit_code == 0
    assert out.exists()


def test_workflow_compare_cli_requires_two(capsys):
    exit_code = main(["workflow", "compare-runs", "--reports", str(GOOD), "--out", "x.md"])
    assert exit_code == 1
    assert "at least two" in capsys.readouterr().err


def test_workflow_demo_cli(tmp_path, capsys):
    out = tmp_path / "demo.md"
    exit_code = main(
        ["workflow", "demo-readiness", "--report", str(GOOD), "--deals", str(WINNING_CSV), "--out", str(out)]
    )
    assert exit_code == 0
    assert out.exists()


def test_workflow_requires_action(capsys):
    exit_code = None
    try:
        main(["workflow"])
    except SystemExit as exc:
        exit_code = exc.code
    assert exit_code == 2
