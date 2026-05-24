"""Aggregate stats over a window of decisions.

Given an iterable of Decision records, produce a Stats snapshot the
caller can render in a dashboard or assert on in a test. Everything
here is read-only; no decisions are mutated.

Stats deliberately stay simple: counts, ratios, averages. If you want
percentile latency or cost-per-success, those belong in agenttrace,
not here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from .decision import Decision, Outcome, RationaleQuality


@dataclass(frozen=True)
class Stats:
    """Read-only snapshot of decision-log aggregates."""

    total: int
    """Total decisions in the window."""

    by_option_picked: dict[str, int] = field(default_factory=dict)
    """How many times each option was chosen."""

    outcome_distribution: dict[str, int] = field(default_factory=dict)
    """Histogram of outcome values."""

    rationale_quality_distribution: dict[str, int] = field(default_factory=dict)
    """Histogram of rationale-quality buckets."""

    rationale_length_avg: float = 0.0
    """Mean character length of rationale strings."""

    wrong_tool_rate: float = 0.0
    """Share of decisions whose outcome is WRONG_TOOL."""

    hallucinated_option_rate: float = 0.0
    """Share of decisions where chosen was not in the options list."""

    structured_rationale_rate: float = 0.0
    """Share of decisions whose rationale classifies as STRUCTURED."""

    avg_options_considered: float = 0.0
    """Mean number of candidate options per decision."""


def aggregate(decisions: Iterable[Decision]) -> Stats:
    """Compute a Stats snapshot from a stream of decisions.

    Consumes the iterable once. Empty input returns a zeroed Stats so
    callers can hand the result straight to a dashboard.
    """
    by_option: Counter[str] = Counter()
    by_outcome: Counter[str] = Counter()
    by_quality: Counter[str] = Counter()

    total = 0
    rationale_chars = 0
    wrong_tool = 0
    hallucinated = 0
    structured = 0
    options_seen = 0

    for dec in decisions:
        total += 1
        by_option[dec.chosen] += 1
        by_outcome[dec.outcome.value] += 1
        quality = dec.rationale_quality()
        by_quality[quality.value] += 1
        rationale_chars += len(dec.rationale or "")
        options_seen += len(dec.options)

        if dec.outcome == Outcome.WRONG_TOOL:
            wrong_tool += 1
        if not dec.chose_listed_option():
            hallucinated += 1
        if quality == RationaleQuality.STRUCTURED:
            structured += 1

    if total == 0:
        return Stats(total=0)

    return Stats(
        total=total,
        by_option_picked=dict(by_option),
        outcome_distribution=dict(by_outcome),
        rationale_quality_distribution=dict(by_quality),
        rationale_length_avg=rationale_chars / total,
        wrong_tool_rate=wrong_tool / total,
        hallucinated_option_rate=hallucinated / total,
        structured_rationale_rate=structured / total,
        avg_options_considered=options_seen / total,
    )


__all__ = ["Stats", "aggregate"]
