"""Unit tests for replay()."""

from __future__ import annotations

from agent_decision_log import DecisionLog, replay


def _seed_log() -> DecisionLog:
    log = DecisionLog()
    log.record(
        turn=0,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="turn 0 forecast",
        context_window=("forecast",),
    )
    log.record(
        turn=1,
        options=["get_weather", "get_news"],
        chosen="get_news",
        rationale="news",
        context_window=("headlines",),
    )
    log.record(
        turn=2,
        options=["fetch_url", "summarize"],
        chosen="summarize",
        rationale="long article",
        context_window=("long doc",),
    )
    return log


def test_replay_full_match_when_agent_repeats_choices():
    log = _seed_log()
    original = list(log.iterate())
    by_id = {d.id: d.chosen for d in original}

    # Build a context-keyed answer table.
    context_to_choice = {d.context_window: d.chosen for d in original}

    def agent_fn(context, options):
        return context_to_choice.get(context, options[0])

    report = replay(log.iterate(), agent_fn)
    assert report.total == 3
    assert report.matched == 3
    assert report.mismatched == 0
    assert report.match_rate == 1.0
    assert report.mismatch_rate == 0.0
    assert report.diff_rows() == ()
    # decision_ids are preserved on rows.
    for row in report.rows:
        assert by_id[row.decision_id] == row.original_chosen
        assert row.matched is True


def test_replay_records_mismatch_when_agent_picks_differently():
    log = _seed_log()

    # Always pick the first option, which will mismatch on the news turn.
    def agent_fn(_context, options):
        return options[0]

    report = replay(log.iterate(), agent_fn)
    assert report.total == 3
    # Turn 0 picked option[0]=get_weather, matches.
    # Turn 1 picked option[0]=get_weather, but original was get_news, mismatch.
    # Turn 2 picked option[0]=fetch_url, but original was summarize, mismatch.
    assert report.matched == 1
    assert report.mismatched == 2
    assert report.mismatch_rate == 2 / 3
    diff = report.diff_rows()
    assert len(diff) == 2
    for row in diff:
        assert row.original_chosen != row.replayed_chosen


def test_replay_captures_agent_errors_inline():
    log = _seed_log()

    def agent_fn(_context, _options):
        raise RuntimeError("model down")

    report = replay(log.iterate(), agent_fn)
    assert report.total == 3
    assert report.matched == 0
    assert report.mismatched == 3
    for row in report.rows:
        assert row.replayed_chosen == "<error:RuntimeError>"
        assert row.matched is False


def test_replay_empty_iterable_gives_zeroed_report():
    def agent_fn(_context, _options):
        return "should not be called"

    report = replay([], agent_fn)
    assert report.total == 0
    assert report.matched == 0
    assert report.mismatched == 0
    assert report.match_rate == 0.0
    assert report.mismatch_rate == 0.0
    assert report.rows == ()


def test_replay_passes_context_and_options_through_to_agent_fn():
    log = _seed_log()
    seen: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def agent_fn(context, options):
        seen.append((context, options))
        return options[0]

    replay(log.iterate(), agent_fn)
    assert len(seen) == 3
    # First call should match the first recorded decision.
    first_ctx, first_opts = seen[0]
    assert first_ctx == ("forecast",)
    assert first_opts == ("get_weather", "get_news")
