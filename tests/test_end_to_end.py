"""End-to-end smoke tests across log, sinks, aggregate, and replay."""

from __future__ import annotations

from agent_decision_log import (
    DecisionLog,
    JsonlSink,
    Outcome,
    aggregate,
    replay,
)


def test_jsonl_record_attach_aggregate_round_trip(tmp_path):
    """Real workflow: record, attach outcome, persist, aggregate from disk."""
    path = tmp_path / "decisions.jsonl"
    log = DecisionLog(JsonlSink(str(path)))

    # Two turns: one correct, one wrong.
    d1 = log.record(
        turn=0,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="user said forecast in turn 0",
        context_window=["user: today's forecast?"],
        expected_outcome="temperature for current city",
    )
    log.attach_outcome(d1.id, Outcome.SUCCESS, observed="72F NYC")

    d2 = log.record(
        turn=1,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="default fallback",
        context_window=["user: what's the news?"],
        expected_outcome="weather",
    )
    log.attach_outcome(d2.id, Outcome.WRONG_TOOL, observed="user actually wanted news")

    # Re-open a fresh sink at the same path to prove persistence is independent
    # of the DecisionLog instance.
    fresh = DecisionLog(JsonlSink(str(path)))
    fresh_decs = list(fresh.iterate())
    assert len(fresh_decs) == 2
    fresh_outcomes = {d.id: d.outcome for d in fresh_decs}
    assert fresh_outcomes[d1.id] == Outcome.SUCCESS
    assert fresh_outcomes[d2.id] == Outcome.WRONG_TOOL

    stats = aggregate(fresh.iterate())
    assert stats.total == 2
    assert stats.by_option_picked == {"get_weather": 2}
    assert stats.wrong_tool_rate == 0.5
    assert stats.hallucinated_option_rate == 0.0


def test_replay_after_prompt_change_simulates_new_choice(tmp_path):
    """Simulate a prompt change that flips one decision and observe via replay."""
    log = DecisionLog(JsonlSink(str(tmp_path / "decisions.jsonl")))
    log.record(
        turn=0,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="forecast",
        context_window=("user: forecast",),
    )
    log.record(
        turn=1,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="news (model misread)",
        context_window=("user: news",),
    )

    # The "new" prompt now correctly picks news when context mentions news.
    def smarter_agent(context, options):
        joined = " ".join(context).lower()
        if "news" in joined and "get_news" in options:
            return "get_news"
        if "forecast" in joined and "get_weather" in options:
            return "get_weather"
        return options[0]

    report = replay(log.iterate(), smarter_agent)
    assert report.total == 2
    assert report.matched == 1
    assert report.mismatched == 1
    diff = report.diff_rows()
    assert len(diff) == 1
    assert diff[0].original_chosen == "get_weather"
    assert diff[0].replayed_chosen == "get_news"
    assert diff[0].turn == 1


def test_hallucinated_option_is_force_classified(tmp_path):
    log = DecisionLog(JsonlSink(str(tmp_path / "decisions.jsonl")))
    d = log.record(
        turn=0,
        options=["get_weather", "get_news"],
        chosen="invent_tool",  # not in options
        rationale="model invented this",
    )
    # Caller mis-classifies as SUCCESS; library forces HALLUCINATED_OPTION.
    log.attach_outcome(d.id, Outcome.SUCCESS, observed="ran somehow")

    stats = aggregate(log.iterate())
    assert stats.outcome_distribution == {"hallucinated_option": 1}
    assert stats.hallucinated_option_rate == 1.0
