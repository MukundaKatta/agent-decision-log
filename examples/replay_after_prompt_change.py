"""Replay a recorded session against a new agent prompt.

Real workflow: you changed a system prompt or upgraded a model. Replay walks
each recorded decision, calls your fresh agent function with the same context
and option list, and tells you which choices flipped.

Run with:
    python examples/replay_after_prompt_change.py
"""

from __future__ import annotations

from agent_decision_log import DecisionLog, InMemorySink, replay


def seed_recorded_session(log: DecisionLog) -> None:
    log.record(
        turn=0,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="user asked about forecast",
        context_window=("user: today's forecast?",),
    )
    log.record(
        turn=1,
        options=["get_weather", "get_news"],
        chosen="get_weather",
        rationale="model defaulted to weather",
        context_window=("user: any news today?",),
    )
    log.record(
        turn=2,
        options=["fetch_url", "summarize"],
        chosen="fetch_url",
        rationale="user pasted a link",
        context_window=("user: read https://example.com",),
    )


def smarter_agent(context: tuple[str, ...], options: tuple[str, ...]) -> str:
    """A pretend new prompt that reads context more carefully."""
    joined = " ".join(context).lower()
    if "news" in joined and "get_news" in options:
        return "get_news"
    if "forecast" in joined and "get_weather" in options:
        return "get_weather"
    if "http" in joined and "fetch_url" in options:
        return "fetch_url"
    return options[0]


def main() -> None:
    log = DecisionLog(sink=InMemorySink())
    seed_recorded_session(log)

    report = replay(log.iterate(), smarter_agent)
    print(f"replayed {report.total} decisions")
    print(f"  matched:    {report.matched} ({report.match_rate:.2%})")
    print(f"  mismatched: {report.mismatched} ({report.mismatch_rate:.2%})")
    print("flipped decisions:")
    for row in report.diff_rows():
        print(
            f"  turn {row.turn}: {row.original_chosen} -> {row.replayed_chosen}"
            f"  (options: {list(row.options)})"
        )


if __name__ == "__main__":
    main()
