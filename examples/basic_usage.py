"""Basic usage example for agent_decision_log.

Run with:
    python examples/basic_usage.py
"""

from __future__ import annotations

from agent_decision_log import (
    DecisionLog,
    JsonlSink,
    Outcome,
    aggregate,
)


def main() -> None:
    log = DecisionLog(sink=JsonlSink("decisions.jsonl"))

    # Inside an agent loop, record a decision before calling the chosen tool.
    decision = log.record(
        turn=4,
        options=["get_weather", "get_news", "fetch_url"],
        chosen="get_weather",
        rationale="user asked about today's forecast in turn 3",
        context_window=[
            "turn3: user: what's the weather like today?",
            "turn4: assistant: choosing tool",
        ],
        expected_outcome="returns weather data for the user's location",
    )

    # After the tool runs, attach an outcome.
    log.attach_outcome(decision.id, Outcome.SUCCESS, observed="returned 72F NYC")

    # A second turn where the model picked the wrong branch.
    bad = log.record(
        turn=5,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="defaulted to weather",
        context_window=["turn5: user: any news today?"],
        expected_outcome="weather data",
    )
    log.attach_outcome(bad.id, Outcome.WRONG_TOOL, observed="user actually wanted news")

    stats = aggregate(log.iterate())
    print(f"recorded {stats.total} decisions")
    print(f"  by option picked: {stats.by_option_picked}")
    print(f"  outcome distribution: {stats.outcome_distribution}")
    print(f"  wrong_tool_rate: {stats.wrong_tool_rate:.2%}")
    print(f"  hallucinated_option_rate: {stats.hallucinated_option_rate:.2%}")
    print(f"  structured_rationale_rate: {stats.structured_rationale_rate:.2%}")
    print(f"  rationale_length_avg: {stats.rationale_length_avg:.1f} chars")


if __name__ == "__main__":
    main()
