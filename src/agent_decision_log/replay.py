"""Replay a logged session against a fresh agent.

The most common use case: you changed a system prompt or upgraded a model,
and you want to know which previously-recorded decisions the new setup
would make differently. Replay walks each Decision, calls the user-supplied
agent_fn with the original context + options, and diffs the new choice
against the recorded one.

The agent_fn is a single callable:
    agent_fn(context_window: tuple[str, ...], options: tuple[str, ...]) -> str

Returning a chosen option name. This keeps replay framework-agnostic; you
write the adapter to your real agent.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .decision import Decision

AgentFn = Callable[[tuple[str, ...], tuple[str, ...]], str]


@dataclass(frozen=True)
class ReplayRow:
    """Single-decision replay result."""

    decision_id: str
    turn: int
    original_chosen: str
    replayed_chosen: str
    options: tuple[str, ...]
    matched: bool


@dataclass(frozen=True)
class ReplayReport:
    """Aggregate result of replaying a stream of decisions."""

    total: int
    matched: int
    mismatched: int
    rows: tuple[ReplayRow, ...] = field(default_factory=tuple)

    @property
    def match_rate(self) -> float:
        """Share of replayed decisions where the new pick matched the old."""
        if self.total == 0:
            return 0.0
        return self.matched / self.total

    @property
    def mismatch_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.mismatched / self.total

    def diff_rows(self) -> tuple[ReplayRow, ...]:
        """Only the rows where the new pick differs from the recorded one."""
        return tuple(r for r in self.rows if not r.matched)


def replay(
    decisions: Iterable[Decision],
    agent_fn: AgentFn,
) -> ReplayReport:
    """Replay each decision through agent_fn and diff the choice.

    agent_fn is called with the recorded context and option list. The
    chosen value it returns is compared verbatim to the recorded chosen
    value. No outcome attachment is performed; replay is read-only.
    """
    rows: list[ReplayRow] = []
    total = 0
    matched = 0
    mismatched = 0

    for dec in decisions:
        total += 1
        try:
            new_choice = agent_fn(dec.context_window, dec.options)
        except Exception as exc:  # noqa: BLE001 - surfaced verbatim into the row
            new_choice = f"<error:{type(exc).__name__}>"
        is_match = new_choice == dec.chosen
        if is_match:
            matched += 1
        else:
            mismatched += 1
        rows.append(
            ReplayRow(
                decision_id=dec.id,
                turn=dec.turn,
                original_chosen=dec.chosen,
                replayed_chosen=new_choice,
                options=dec.options,
                matched=is_match,
            )
        )

    return ReplayReport(
        total=total,
        matched=matched,
        mismatched=mismatched,
        rows=tuple(rows),
    )


__all__ = ["AgentFn", "ReplayRow", "ReplayReport", "replay"]
