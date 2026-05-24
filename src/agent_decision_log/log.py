"""DecisionLog facade.

This is the thing users actually call from inside their agent loop:

    log = DecisionLog(sink=InMemorySink())
    decision = log.record(turn=4, options=[...], chosen="get_weather", ...)
    log.attach_outcome(decision.id, Outcome.SUCCESS, observed="returned 72F")

The facade is thin on purpose. It holds a single Sink and a couple of
defensive validations so callers cannot persist obviously broken records.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence

from .decision import Decision, Outcome, new_decision_id
from .sinks import InMemorySink, Sink


class DecisionLog:
    """Append-only log of agent decisions.

    Backed by a swappable Sink. Defaults to an in-memory sink so the lib
    works without any setup, but production callers should plug in a
    JsonlSink or their own remote sink.
    """

    def __init__(self, sink: Sink | None = None) -> None:
        self._sink: Sink = sink if sink is not None else InMemorySink()

    @property
    def sink(self) -> Sink:
        return self._sink

    def record(
        self,
        *,
        turn: int,
        options: Sequence[str],
        chosen: str,
        rationale: str,
        context_window: Sequence[str] = (),
        expected_outcome: str = "",
        metadata: dict | None = None,
    ) -> Decision:
        """Record a single decision.

        All fields are keyword-only because order would not be obvious in
        an agent loop, and getting the wrong field is easy with positionals.
        """
        if turn < 0:
            raise ValueError("turn must be >= 0")
        if not isinstance(chosen, str) or not chosen:
            raise ValueError("chosen must be a non-empty string")
        # We intentionally allow chosen to be outside options; that case is
        # tracked as HALLUCINATED_OPTION at outcome time and as
        # chose_listed_option() on the Decision itself.
        options_tuple = tuple(str(opt) for opt in options)
        context_tuple = tuple(str(c) for c in context_window)

        decision = Decision(
            id=new_decision_id(),
            turn=turn,
            options=options_tuple,
            chosen=chosen,
            rationale=rationale or "",
            context_window=context_tuple,
            expected_outcome=expected_outcome or "",
            metadata=dict(metadata or {}),
        )
        self._sink.append(decision)
        return decision

    def attach_outcome(
        self,
        decision_id: str,
        outcome: Outcome,
        observed: str | None = None,
    ) -> Decision:
        """Attach a post-hoc outcome to an existing decision.

        Caller is expected to know the right Outcome bucket; the lib only
        cross-checks one cheap invariant: if the chosen value was not in
        the options list, the outcome is forced to HALLUCINATED_OPTION.
        That keeps audit dashboards honest even if the wiring code is
        sloppy about classifying the result.
        """
        if not isinstance(outcome, Outcome):
            raise TypeError("outcome must be an Outcome enum member")
        existing = self._sink.get(decision_id)
        effective = outcome
        if not existing.chose_listed_option() and outcome == Outcome.SUCCESS:
            # A hallucinated option that nonetheless "succeeded" is still
            # interesting to flag as hallucinated. Real-world telemetry
            # often masks this case.
            effective = Outcome.HALLUCINATED_OPTION
        return self._sink.update_outcome(decision_id, effective, observed)

    def get(self, decision_id: str) -> Decision:
        return self._sink.get(decision_id)

    def iterate(self) -> Iterable[Decision]:
        return self._sink.iterate()

    def __iter__(self) -> Iterator[Decision]:
        return iter(self.iterate())

    def __len__(self) -> int:
        try:
            return len(self._sink)  # type: ignore[arg-type]
        except TypeError:
            return sum(1 for _ in self._sink.iterate())


__all__ = ["DecisionLog"]
