"""Unit tests for InMemorySink."""

from __future__ import annotations

import pytest

from agent_decision_log import InMemorySink, Outcome
from agent_decision_log.decision import Decision, new_decision_id


def _mk(**overrides) -> Decision:
    defaults = dict(
        id=new_decision_id(),
        turn=0,
        options=("a", "b"),
        chosen="a",
        rationale="x",
        context_window=(),
        expected_outcome="",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def test_append_and_get():
    sink = InMemorySink()
    d = _mk()
    sink.append(d)
    assert sink.get(d.id) == d
    assert len(sink) == 1


def test_append_duplicate_id_raises():
    sink = InMemorySink()
    d = _mk(id="dupe")
    sink.append(d)
    with pytest.raises(ValueError):
        sink.append(d)


def test_get_missing_raises_keyerror():
    sink = InMemorySink()
    with pytest.raises(KeyError):
        sink.get("nope")


def test_update_outcome_replaces_record():
    sink = InMemorySink()
    d = _mk()
    sink.append(d)
    updated = sink.update_outcome(d.id, Outcome.SUCCESS, observed="all good")
    assert updated.outcome == Outcome.SUCCESS
    assert updated.observed == "all good"
    # Original record should be replaced, not appended.
    assert sink.get(d.id).outcome == Outcome.SUCCESS
    assert len(sink) == 1


def test_update_outcome_missing_raises_keyerror():
    sink = InMemorySink()
    with pytest.raises(KeyError):
        sink.update_outcome("nope", Outcome.SUCCESS, observed=None)


def test_iterate_returns_snapshot_safe_to_mutate_during_loop():
    sink = InMemorySink()
    for _ in range(3):
        sink.append(_mk(id=new_decision_id()))
    # Mutating mid-iteration must not raise.
    for dec in sink.iterate():
        sink.update_outcome(dec.id, Outcome.SUCCESS, observed="ok")
    # All three should now be SUCCESS.
    outcomes = {d.outcome for d in sink.iterate()}
    assert outcomes == {Outcome.SUCCESS}
