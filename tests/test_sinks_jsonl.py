"""Unit tests for JsonlSink (append-only file backend)."""

from __future__ import annotations

import json
import os

import pytest

from agent_decision_log import DecisionLog, JsonlSink, Outcome
from agent_decision_log.decision import Decision, new_decision_id


def _mk(**overrides) -> Decision:
    defaults = dict(
        id=new_decision_id(),
        turn=0,
        options=("a", "b"),
        chosen="a",
        rationale="x",
        context_window=("ctx",),
        expected_outcome="",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def test_jsonl_sink_creates_empty_file_on_init(tmp_path):
    path = tmp_path / "log.jsonl"
    sink = JsonlSink(str(path))
    assert path.exists()
    assert list(sink.iterate()) == []
    assert len(sink) == 0
    assert sink.path == str(path)


def test_jsonl_sink_appends_one_line_per_decision(tmp_path):
    sink = JsonlSink(str(tmp_path / "log.jsonl"))
    d1 = _mk()
    d2 = _mk()
    sink.append(d1)
    sink.append(d2)
    with open(tmp_path / "log.jsonl", encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    assert len(lines) == 2
    # Lines are JSON-decodable and round-trip back to Decision.
    payloads = [json.loads(ln) for ln in lines]
    revived = [Decision.from_dict(p) for p in payloads]
    assert revived == [d1, d2]


def test_jsonl_sink_creates_parent_dir_when_missing(tmp_path):
    nested = tmp_path / "deeper" / "still" / "log.jsonl"
    sink = JsonlSink(str(nested))
    assert nested.exists()
    sink.append(_mk())
    assert len(sink) == 1


def test_jsonl_sink_get_raises_keyerror_for_unknown_id(tmp_path):
    sink = JsonlSink(str(tmp_path / "log.jsonl"))
    with pytest.raises(KeyError):
        sink.get("nope")


def test_jsonl_sink_update_outcome_rewrites_file(tmp_path):
    sink = JsonlSink(str(tmp_path / "log.jsonl"))
    a = _mk()
    b = _mk()
    sink.append(a)
    sink.append(b)
    sink.update_outcome(a.id, Outcome.SUCCESS, observed="all good")
    revived_a = sink.get(a.id)
    revived_b = sink.get(b.id)
    assert revived_a.outcome == Outcome.SUCCESS
    assert revived_a.observed == "all good"
    assert revived_b.outcome == Outcome.UNKNOWN
    # File should still contain exactly 2 lines.
    with open(tmp_path / "log.jsonl", encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    assert len(lines) == 2


def test_jsonl_sink_update_outcome_missing_id_raises(tmp_path):
    sink = JsonlSink(str(tmp_path / "log.jsonl"))
    sink.append(_mk())
    with pytest.raises(KeyError):
        sink.update_outcome("nope", Outcome.SUCCESS, observed=None)


def test_jsonl_sink_survives_blank_lines(tmp_path):
    path = tmp_path / "log.jsonl"
    sink = JsonlSink(str(path))
    sink.append(_mk())
    # Inject a couple of blank lines that a careless editor might leave behind.
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n\n   \n")
    sink.append(_mk())
    assert len(sink) == 2


def test_jsonl_sink_works_through_decision_log_facade(tmp_path):
    log = DecisionLog(JsonlSink(str(tmp_path / "log.jsonl")))
    dec = log.record(
        turn=1,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="because turn 0 mentioned forecast",
        context_window=["turn0: forecast?"],
    )
    log.attach_outcome(dec.id, Outcome.SUCCESS, observed="72F NYC")
    # Open a brand-new sink on the same file and verify persistence.
    other = JsonlSink(str(tmp_path / "log.jsonl"))
    revived = other.get(dec.id)
    assert revived.outcome == Outcome.SUCCESS
    assert revived.observed == "72F NYC"


def test_jsonl_sink_tmp_file_is_cleaned_up_after_update(tmp_path):
    path = tmp_path / "log.jsonl"
    sink = JsonlSink(str(path))
    d = _mk()
    sink.append(d)
    sink.update_outcome(d.id, Outcome.SUCCESS, observed=None)
    # The .tmp swap target should not linger.
    assert not os.path.exists(str(path) + ".tmp")
