"""agent_decision_log: structured decision log for AI agents.

Capture why each branch in an agent's reasoning was chosen, with the
context the model saw, the option it picked vs. rejected, and the
post-hoc outcome. Composable sinks, replay, aggregate stats. Zero deps.

Public surface:
    DecisionLog, Decision, Outcome, RationaleQuality
    InMemorySink, JsonlSink, Sink
    aggregate, Stats
    replay, ReplayReport, ReplayRow, AgentFn
"""

from .aggregate import Stats, aggregate
from .decision import (
    Decision,
    Outcome,
    RationaleQuality,
    classify_rationale,
    new_decision_id,
)
from .log import DecisionLog
from .replay import AgentFn, ReplayReport, ReplayRow, replay
from .sinks import InMemorySink, JsonlSink, Sink

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DecisionLog",
    "Decision",
    "Outcome",
    "RationaleQuality",
    "classify_rationale",
    "new_decision_id",
    "Sink",
    "InMemorySink",
    "JsonlSink",
    "Stats",
    "aggregate",
    "replay",
    "ReplayReport",
    "ReplayRow",
    "AgentFn",
]
