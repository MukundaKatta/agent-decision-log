"""Unit tests for aggregate stats."""

from __future__ import annotations

from agent_decision_log import DecisionLog, Outcome, aggregate
from agent_decision_log.aggregate import Stats


def _seed_log() -> DecisionLog:
    log = DecisionLog()
    # 3 weather picks, 1 news pick, 1 hallucinated.
    w1 = log.record(
        turn=0,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="because user asked about forecast",
        context_window=["turn0: forecast"],
    )
    log.attach_outcome(w1.id, Outcome.SUCCESS, observed="72F")
    w2 = log.record(
        turn=1,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="follow-up forecast",
        context_window=["turn1"],
    )
    log.attach_outcome(w2.id, Outcome.SUCCESS, observed="70F")
    n1 = log.record(
        turn=2,
        options=["get_weather", "get_news"],
        chosen="get_news",
        rationale="news request",
    )
    log.attach_outcome(n1.id, Outcome.WRONG_TOOL, observed="user wanted weather")
    w3 = log.record(
        turn=3,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="default fallback",
    )
    log.attach_outcome(w3.id, Outcome.PARTIAL, observed="stale cache")
    h1 = log.record(
        turn=4,
        options=["get_weather", "get_news"],
        chosen="fly_drone",
        rationale="",
    )
    # Hallucinated option; library forces HALLUCINATED_OPTION even if caller said SUCCESS.
    log.attach_outcome(h1.id, Outcome.SUCCESS, observed="invented")
    return log


def test_aggregate_returns_zeroed_stats_for_empty():
    stats = aggregate([])
    assert isinstance(stats, Stats)
    assert stats.total == 0
    assert stats.by_option_picked == {}
    assert stats.outcome_distribution == {}
    assert stats.rationale_length_avg == 0.0
    assert stats.wrong_tool_rate == 0.0
    assert stats.hallucinated_option_rate == 0.0
    assert stats.structured_rationale_rate == 0.0
    assert stats.avg_options_considered == 0.0


def test_aggregate_counts_by_option_picked():
    log = _seed_log()
    stats = aggregate(log.iterate())
    assert stats.by_option_picked["get_weather"] == 3
    assert stats.by_option_picked["get_news"] == 1
    assert stats.by_option_picked["fly_drone"] == 1


def test_aggregate_outcome_distribution_uses_string_keys():
    log = _seed_log()
    stats = aggregate(log.iterate())
    assert stats.outcome_distribution["success"] == 2
    assert stats.outcome_distribution["wrong_tool"] == 1
    assert stats.outcome_distribution["partial"] == 1
    assert stats.outcome_distribution["hallucinated_option"] == 1


def test_aggregate_wrong_tool_rate():
    log = _seed_log()
    stats = aggregate(log.iterate())
    # 1 wrong_tool out of 5 decisions.
    assert stats.wrong_tool_rate == 1 / 5


def test_aggregate_hallucinated_option_rate():
    log = _seed_log()
    stats = aggregate(log.iterate())
    # fly_drone was not in options; the others all were.
    assert stats.hallucinated_option_rate == 1 / 5


def test_aggregate_avg_options_considered():
    log = _seed_log()
    stats = aggregate(log.iterate())
    # All 5 decisions offered 2 options each.
    assert stats.avg_options_considered == 2.0


def test_aggregate_rationale_quality_distribution():
    log = _seed_log()
    stats = aggregate(log.iterate())
    # "because user asked about forecast" → STRUCTURED
    # "follow-up forecast" → FREE_TEXT
    # "news request" → FREE_TEXT
    # "default fallback" → FREE_TEXT
    # "" → MISSING
    assert stats.rationale_quality_distribution["structured"] == 1
    assert stats.rationale_quality_distribution["free_text"] == 3
    assert stats.rationale_quality_distribution["missing"] == 1
    assert stats.structured_rationale_rate == 1 / 5


def test_aggregate_rationale_length_avg_matches_manual_count():
    log = _seed_log()
    stats = aggregate(log.iterate())
    rationales = [d.rationale for d in log.iterate()]
    expected = sum(len(r) for r in rationales) / len(rationales)
    assert stats.rationale_length_avg == expected
