"""Pluggable persistence backends for decisions.

A Sink is the seam between the in-memory DecisionLog facade and whatever
storage the user actually wants: a local JSONL file for replay, an in-memory
list for tests, or a thin shim to Honeycomb, Datadog, S3, Kafka, etc.

The protocol is intentionally tiny on purpose: append, update, iterate, get.
That keeps third-party sinks shallow.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterable, Iterator
from dataclasses import replace
from typing import Protocol, runtime_checkable

from .decision import Decision, Outcome


@runtime_checkable
class Sink(Protocol):
    """Storage protocol for decisions.

    Implementations may be remote and eventually consistent. The DecisionLog
    facade does not assume strict ordering across writers, only that a given
    decision id is unique per sink.
    """

    def append(self, decision: Decision) -> None:
        """Persist a new decision record."""

    def update_outcome(
        self,
        decision_id: str,
        outcome: Outcome,
        observed: str | None,
    ) -> Decision:
        """Update outcome + observed on an existing decision and return it.

        Should raise KeyError if the id is unknown to this sink.
        """

    def get(self, decision_id: str) -> Decision:
        """Fetch a single decision by id. Raises KeyError if missing."""

    def iterate(self) -> Iterable[Decision]:
        """Iterate over all decisions known to this sink."""


class InMemorySink:
    """Thread-safe in-memory sink, mostly for tests and short-lived agents.

    Decisions are stored in insertion order. Iteration returns a snapshot
    so callers can mutate the sink while iterating.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Insertion-ordered dict, since Python 3.7+ preserves it.
        self._records: dict[str, Decision] = {}

    def append(self, decision: Decision) -> None:
        with self._lock:
            if decision.id in self._records:
                raise ValueError(f"duplicate decision id: {decision.id}")
            self._records[decision.id] = decision

    def update_outcome(
        self,
        decision_id: str,
        outcome: Outcome,
        observed: str | None,
    ) -> Decision:
        with self._lock:
            if decision_id not in self._records:
                raise KeyError(decision_id)
            existing = self._records[decision_id]
            updated = replace(existing, outcome=outcome, observed=observed)
            self._records[decision_id] = updated
            return updated

    def get(self, decision_id: str) -> Decision:
        with self._lock:
            if decision_id not in self._records:
                raise KeyError(decision_id)
            return self._records[decision_id]

    def iterate(self) -> Iterator[Decision]:
        with self._lock:
            # Snapshot, so callers can attach outcomes mid-loop without RuntimeError.
            snapshot = list(self._records.values())
        return iter(snapshot)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


class JsonlSink:
    """Append-only JSONL sink backed by a file on disk.

    Layout: each line is one Decision.to_dict, JSON encoded. update_outcome
    rewrites the file in place because JSONL has no native in-place edit.
    For high-write workloads, plug in a real database sink instead.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        # Make sure the parent dir exists so first append does not blow up.
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        # Touch the file so iterate returns [] cleanly on a brand-new sink.
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8"):
                pass

    @property
    def path(self) -> str:
        return self._path

    def append(self, decision: Decision) -> None:
        line = json.dumps(decision.to_dict(), sort_keys=True)
        with self._lock, open(self._path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.write("\n")

    def _read_all(self) -> list[Decision]:
        decisions: list[Decision] = []
        with open(self._path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                payload = json.loads(raw)
                decisions.append(Decision.from_dict(payload))
        return decisions

    def update_outcome(
        self,
        decision_id: str,
        outcome: Outcome,
        observed: str | None,
    ) -> Decision:
        with self._lock:
            decisions = self._read_all()
            found_idx: int | None = None
            for idx, dec in enumerate(decisions):
                if dec.id == decision_id:
                    found_idx = idx
                    break
            if found_idx is None:
                raise KeyError(decision_id)
            updated = replace(decisions[found_idx], outcome=outcome, observed=observed)
            decisions[found_idx] = updated
            # Atomic-ish rewrite via temp file in the same dir.
            tmp_path = self._path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                for dec in decisions:
                    fh.write(json.dumps(dec.to_dict(), sort_keys=True))
                    fh.write("\n")
            os.replace(tmp_path, self._path)
            return updated

    def get(self, decision_id: str) -> Decision:
        with self._lock:
            for dec in self._read_all():
                if dec.id == decision_id:
                    return dec
            raise KeyError(decision_id)

    def iterate(self) -> Iterator[Decision]:
        with self._lock:
            decisions = self._read_all()
        return iter(decisions)

    def __len__(self) -> int:
        with self._lock:
            return sum(1 for _ in self._read_all())


__all__ = [
    "Sink",
    "InMemorySink",
    "JsonlSink",
]
