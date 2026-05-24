"""Unit tests for Decision, Outcome, RationaleQuality, and helpers."""

from __future__ import annotations

import pytest

from agent_decision_log.decision import (
    Decision,
    Outcome,
    RationaleQuality,
    classify_rationale,
    new_decision_id,
)


def _build(**overrides) -> Decision:
    defaults = dict(
        id="d1",
        turn=0,
        options=("a", "b"),
        chosen="a",
        rationale="because a",
        context_window=("ctx",),
        expected_outcome="ok",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def test_outcome_enum_values_are_string_stable():
    # JSON dumps lean on this; do not let these drift accidentally.
    assert Outcome.SUCCESS.value == "success"
    assert Outcome.WRONG_TOOL.value == "wrong_tool"
    assert Outcome.HALLUCINATED_OPTION.value == "hallucinated_option"
    assert Outcome.UNKNOWN.value == "unknown"


def test_rationale_quality_missing_for_none_and_blank():
    assert classify_rationale(None) == RationaleQuality.MISSING
    assert classify_rationale("") == RationaleQuality.MISSING
    assert classify_rationale("   \n\t  ") == RationaleQuality.MISSING


def test_rationale_quality_structured_when_marker_present():
    assert classify_rationale("turn 3 mentioned forecast") == RationaleQuality.STRUCTURED
    assert classify_rationale("because user said hi") == RationaleQuality.STRUCTURED
    assert classify_rationale("tool: get_weather is right") == RationaleQuality.STRUCTURED


def test_rationale_quality_freetext_when_no_markers():
    assert classify_rationale("looked fine") == RationaleQuality.FREE_TEXT


def test_chose_listed_option_true_when_in_options():
    d = _build(options=("a", "b"), chosen="a")
    assert d.chose_listed_option() is True


def test_chose_listed_option_false_when_hallucinated():
    d = _build(options=("a", "b"), chosen="c")
    assert d.chose_listed_option() is False


def test_to_dict_round_trips_through_from_dict():
    d = _build(metadata={"agent": "maya"}, outcome=Outcome.SUCCESS, observed="ok")
    payload = d.to_dict()
    revived = Decision.from_dict(payload)
    assert revived == d


def test_to_dict_outcome_serialized_as_string():
    d = _build(outcome=Outcome.WRONG_TOOL)
    payload = d.to_dict()
    assert payload["outcome"] == "wrong_tool"


def test_from_dict_handles_missing_optional_fields():
    payload = {
        "id": "x",
        "turn": 1,
        "chosen": "a",
    }
    revived = Decision.from_dict(payload)
    assert revived.id == "x"
    assert revived.options == ()
    assert revived.context_window == ()
    assert revived.outcome == Outcome.UNKNOWN


def test_new_decision_id_is_unique_and_hex():
    ids = {new_decision_id() for _ in range(100)}
    assert len(ids) == 100
    # uuid4().hex is 32 chars of lowercase hex.
    for i in ids:
        assert len(i) == 32
        int(i, 16)  # raises if non-hex


def test_decision_is_frozen():
    d = _build()
    with pytest.raises(Exception):
        d.chosen = "other"  # type: ignore[misc]
