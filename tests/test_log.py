"""Unit tests for the DecisionLog facade."""

from __future__ import annotations

import pytest

from agent_decision_log import DecisionLog, InMemorySink, Outcome


def test_record_returns_decision_and_persists_to_sink():
    log = DecisionLog()
    dec = log.record(
        turn=4,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="user asked about today's forecast in turn 3",
        context_window=["turn3: forecast", "turn4: pick tool"],
        expected_outcome="weather data for NYC",
    )
    assert dec.chosen == "get_weather"
    assert dec.options == ("get_weather", "get_news")
    assert dec.context_window == ("turn3: forecast", "turn4: pick tool")
    assert dec.outcome == Outcome.UNKNOWN
    assert len(log) == 1
    assert log.get(dec.id) == dec


def test_record_rejects_negative_turn():
    log = DecisionLog()
    with pytest.raises(ValueError):
        log.record(turn=-1, options=["a"], chosen="a", rationale="x")


def test_record_rejects_empty_chosen():
    log = DecisionLog()
    with pytest.raises(ValueError):
        log.record(turn=0, options=["a"], chosen="", rationale="x")


def test_record_allows_chosen_outside_options():
    log = DecisionLog()
    dec = log.record(
        turn=0,
        options=["a", "b"],
        chosen="c",
        rationale="model invented this",
    )
    assert dec.chose_listed_option() is False


def test_attach_outcome_updates_existing_decision():
    log = DecisionLog()
    dec = log.record(turn=0, options=["a"], chosen="a", rationale="x")
    updated = log.attach_outcome(dec.id, Outcome.SUCCESS, observed="returned ok")
    assert updated.outcome == Outcome.SUCCESS
    assert updated.observed == "returned ok"
    assert log.get(dec.id).outcome == Outcome.SUCCESS


def test_attach_outcome_promotes_to_hallucinated_when_chosen_not_in_options():
    log = DecisionLog()
    dec = log.record(turn=0, options=["a", "b"], chosen="c", rationale="x")
    # Even though caller said SUCCESS, the chosen value was never offered.
    updated = log.attach_outcome(dec.id, Outcome.SUCCESS, observed="ran somehow")
    assert updated.outcome == Outcome.HALLUCINATED_OPTION


def test_attach_outcome_keeps_caller_outcome_for_other_buckets():
    log = DecisionLog()
    dec = log.record(turn=0, options=["a", "b"], chosen="c", rationale="x")
    # WRONG_TOOL on a hallucinated option stays as caller specified.
    updated = log.attach_outcome(dec.id, Outcome.WRONG_TOOL, observed="nope")
    assert updated.outcome == Outcome.WRONG_TOOL


def test_attach_outcome_raises_for_unknown_id():
    log = DecisionLog()
    with pytest.raises(KeyError):
        log.attach_outcome("missing", Outcome.SUCCESS)


def test_attach_outcome_validates_enum_type():
    log = DecisionLog()
    dec = log.record(turn=0, options=["a"], chosen="a", rationale="x")
    with pytest.raises(TypeError):
        log.attach_outcome(dec.id, "success")  # type: ignore[arg-type]


def test_iterate_returns_decisions_in_insertion_order():
    log = DecisionLog(InMemorySink())
    a = log.record(turn=0, options=["a"], chosen="a", rationale="x")
    b = log.record(turn=1, options=["b"], chosen="b", rationale="x")
    c = log.record(turn=2, options=["c"], chosen="c", rationale="x")
    seen = list(log)
    assert [d.id for d in seen] == [a.id, b.id, c.id]


def test_metadata_is_round_tripped_through_log():
    log = DecisionLog()
    dec = log.record(
        turn=0,
        options=["a"],
        chosen="a",
        rationale="x",
        metadata={"agent_id": "maya", "model": "gpt-5.4"},
    )
    revived = log.get(dec.id)
    assert revived.metadata == {"agent_id": "maya", "model": "gpt-5.4"}
