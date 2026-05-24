"""Dataclasses for a single agent decision and its post-hoc outcome.

A Decision records:
  - which options the model considered
  - which one it chose
  - the rationale text (free form or structured)
  - the slice of context window that justified the choice
  - what outcome was expected

An Outcome is attached later, after the chosen tool actually runs.

This module is intentionally zero-dep. Everything is plain dataclasses,
enums, and dicts so the records serialize cleanly to JSONL.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class Outcome(str, enum.Enum):
    """Post-hoc outcome of a single decision.

    Kept as a string enum so JSON dumps remain human readable.
    """

    SUCCESS = "success"
    """Chosen option ran and produced the expected outcome."""

    PARTIAL = "partial"
    """Chosen option ran but the result was only partially what was expected."""

    WRONG_TOOL = "wrong_tool"
    """A different option from the candidate list would have been correct."""

    TOOL_ERROR = "tool_error"
    """Chosen option raised an error or returned an error payload."""

    HALLUCINATED_OPTION = "hallucinated_option"
    """Chosen option was not in the candidate list at all."""

    UNKNOWN = "unknown"
    """No outcome attached yet, or outcome cannot be classified."""


class RationaleQuality(str, enum.Enum):
    """How structured the rationale text is.

    This is a cheap heuristic. Replay and aggregate stats use it to flag
    decisions whose rationale is unusable for audit.
    """

    STRUCTURED = "structured"
    """Rationale is structured (mentions specific turn refs or keys)."""

    FREE_TEXT = "free_text"
    """Rationale is plain prose, but non-empty."""

    MISSING = "missing"
    """Rationale is empty, whitespace, or None."""


def classify_rationale(rationale: str | None) -> RationaleQuality:
    """Bucket a rationale string into one of three quality tiers.

    Heuristic only. The goal is to give aggregate dashboards a rough sense
    of how many decisions are auditable vs. opaque.
    """
    if rationale is None:
        return RationaleQuality.MISSING
    stripped = rationale.strip()
    if not stripped:
        return RationaleQuality.MISSING
    # Tokens that look like structured references back into context.
    markers = ("turn", "context:", "user said", "tool:", "because")
    lowered = stripped.lower()
    if any(marker in lowered for marker in markers):
        return RationaleQuality.STRUCTURED
    return RationaleQuality.FREE_TEXT


@dataclass(frozen=True)
class Decision:
    """A single decision point inside an agent loop.

    Fields are deliberately wide so different agent frameworks can map onto
    the same record without inventing new schemas.
    """

    id: str
    """Stable unique id, used by attach_outcome to find the record."""

    turn: int
    """Turn index inside the conversation or agent loop."""

    options: tuple[str, ...]
    """Candidate options the model considered at this branch."""

    chosen: str
    """The option the model actually picked. May or may not be in options."""

    rationale: str
    """Free or structured text explaining the pick."""

    context_window: tuple[str, ...]
    """Slice of prior context the model used to justify the pick."""

    expected_outcome: str
    """What the agent predicts will happen if the chosen option runs."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Free-form per-call metadata. Stored verbatim."""

    created_at: float = field(default_factory=lambda: time.time())
    """Unix epoch seconds when the decision was recorded."""

    outcome: Outcome = Outcome.UNKNOWN
    """Outcome bucket. UNKNOWN until attach_outcome is called."""

    observed: str | None = None
    """Free-form observed-actual text, attached when the outcome lands."""

    def rationale_quality(self) -> RationaleQuality:
        """Cheap quality bucket for the rationale string."""
        return classify_rationale(self.rationale)

    def chose_listed_option(self) -> bool:
        """Whether the chosen value was actually one of the candidates.

        False here typically means the model hallucinated a tool name.
        """
        return self.chosen in self.options

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for serialization."""
        return {
            "id": self.id,
            "turn": self.turn,
            "options": list(self.options),
            "chosen": self.chosen,
            "rationale": self.rationale,
            "context_window": list(self.context_window),
            "expected_outcome": self.expected_outcome,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "outcome": self.outcome.value,
            "observed": self.observed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Decision:
        """Round-trip from a dict produced by to_dict."""
        return cls(
            id=str(data["id"]),
            turn=int(data["turn"]),
            options=tuple(data.get("options") or ()),
            chosen=str(data["chosen"]),
            rationale=str(data.get("rationale") or ""),
            context_window=tuple(data.get("context_window") or ()),
            expected_outcome=str(data.get("expected_outcome") or ""),
            metadata=dict(data.get("metadata") or {}),
            created_at=float(data.get("created_at", time.time())),
            outcome=Outcome(data.get("outcome", Outcome.UNKNOWN.value)),
            observed=data.get("observed"),
        )


def new_decision_id() -> str:
    """Generate a stable unique id for a decision.

    Kept here so callers do not have to import uuid themselves.
    """
    return uuid.uuid4().hex


__all__ = [
    "Decision",
    "Outcome",
    "RationaleQuality",
    "classify_rationale",
    "new_decision_id",
]
