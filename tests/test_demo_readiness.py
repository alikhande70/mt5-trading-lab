from pathlib import Path

from trading_lab.cli import main
from trading_lab.demo_readiness import (
    NEEDS_REVIEW,
    NOT_READY,
    READY,
    readiness_for_deals,
    readiness_for_report,
)
from trading_lab.recommend import Thresholds

FIXTURES = Path(__file__).parent / "fixtures"

GOOD = FIXTURES / "sample_strategy_tester_report.htm"
BORDERLINE = FIXTURES / "borderline_strategy_report.htm"
LOSING = FIXTURES / "losing_strategy_report.htm"
WINNING_CSV = FIXTURES / "sample_deals.csv"
LOSING_CSV = FIXTURES / "losing_deals.csv"


def test_good_report_is_ready():
    readiness = readiness_for_report(GOOD)
    assert readiness.status == READY
    assert readiness.decision == "PASS_TO_DEMO"
    assert all(item.value for item in readiness.evidence)


def test_losing_report_is_not_ready():
    readiness = readiness_for_report(LOSING)
    assert readiness.status == NOT_READY


def test_borderline_report_needs_review():
    readiness = readiness_for_report(BORDERLINE)
    assert readiness.status == NEEDS_REVIEW
    # A borderline run surfaces at least one MEDIUM+ risk finding.
    assert readiness.risk_findings


def test_evidence_has_expected_checks():
    readiness = readiness_for_report(GOOD)
    labels = {item.label for item in readiness.evidence}
    assert {"Trade count", "Profit factor", "Max drawdown", "Recovery factor", "Data completeness"} <= labels


def test_deals_readiness_winning_vs_losing():
    assert readiness_for_deals(WINNING_CSV).status != NOT_READY
    assert readiness_for_deals(LOSING_CSV).status == NOT_READY


def test_thresholds_flip_evidence_ok():
    readiness = readiness_for_report(GOOD, Thresholds(min_trades=500))
    trade_count = next(i for i in readiness.evidence if i.label == "Trade count")
    assert trade_count.ok is False


def test_demo_readiness_cli_report(tmp_path, capsys):
    out_md = tmp_path / "demo.md"
    json_out = tmp_path / "demo.json"
    exit_code = main(
        ["demo-readiness", str(GOOD), "--out", str(out_md), "--json-out", str(json_out), "--format", "both"]
    )
    assert exit_code == 0
    assert out_md.exists() and json_out.exists()
    assert "Demo readiness: READY" in capsys.readouterr().out


def test_demo_readiness_cli_autodetects_csv(tmp_path, capsys):
    exit_code = main(["demo-readiness", str(LOSING_CSV), "--out", str(tmp_path / "d.md")])
    assert exit_code == 0
    assert "NOT_READY" in capsys.readouterr().out


def test_demo_readiness_cli_deals_flag_overrides(tmp_path, capsys):
    # Positional is a report, but --deals takes precedence as the assessed source.
    exit_code = main(
        ["demo-readiness", str(GOOD), "--deals", str(LOSING_CSV), "--out", str(tmp_path / "d.md")]
    )
    assert exit_code == 0
    assert "NOT_READY" in capsys.readouterr().out


def test_demo_readiness_cli_missing_file(capsys):
    exit_code = main(["demo-readiness", "does_not_exist.htm", "--out", "x.md"])
    assert exit_code == 1
    assert "not found" in capsys.readouterr().err
