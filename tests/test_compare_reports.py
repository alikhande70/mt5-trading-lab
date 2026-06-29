from pathlib import Path

from trading_lab.compare import compare_reports
from trading_lab.recommend import PASS_TO_DEMO, REJECT, Thresholds
from trading_lab.report import build_comparison_payload

FIXTURES = Path(__file__).parent / "fixtures"

GOOD = FIXTURES / "sample_strategy_tester_report.htm"
BORDERLINE = FIXTURES / "borderline_strategy_report.htm"
LOSING = FIXTURES / "losing_strategy_report.htm"


def test_compare_ranks_best_first_by_score():
    result = compare_reports([LOSING, GOOD, BORDERLINE])
    scores = [run.score.total for run in result.runs]
    assert scores == sorted(scores, reverse=True)
    assert result.runs[0].name == GOOD.name
    assert result.best == GOOD.name


def test_losing_run_is_flagged_and_ranked_last():
    result = compare_reports([GOOD, BORDERLINE, LOSING])
    last = result.runs[-1]
    assert last.name == LOSING.name
    assert last.decision == REJECT
    assert "losing" in last.flags


def test_best_candidate_recommendation_mentions_winner():
    result = compare_reports([GOOD, LOSING])
    assert result.best == GOOD.name
    assert GOOD.name in result.recommendation
    assert result.runs[0].decision == PASS_TO_DEMO


def test_ranking_is_risk_adjusted_not_net_profit():
    # The borderline run has positive net profit but high drawdown and weak
    # stability, so it must rank below the cleaner, higher-quality run.
    result = compare_reports([BORDERLINE, GOOD])
    assert result.runs[0].name == GOOD.name
    assert result.runs[0].score.total > result.runs[1].score.total


def test_comparison_is_deterministic():
    a = compare_reports([GOOD, BORDERLINE, LOSING])
    b = compare_reports([LOSING, BORDERLINE, GOOD])
    assert [r.name for r in a.runs] == [r.name for r in b.runs]
    assert [r.score.total for r in a.runs] == [r.score.total for r in b.runs]


def test_comparison_payload_structure():
    result = compare_reports([GOOD, BORDERLINE, LOSING])
    payload = build_comparison_payload(result)
    assert payload["best"] == GOOD.name
    assert len(payload["runs"]) == 3
    first = payload["runs"][0]
    assert "score" in first and "total" in first["score"]
    assert set(first["score"]).issuperset(
        {"stability", "profit_quality", "drawdown_control", "sample_quality", "report_completeness"}
    )


def test_thresholds_influence_flags():
    strict = Thresholds(min_trades=200)
    result = compare_reports([GOOD], strict)
    assert "low-sample" in result.runs[0].flags
