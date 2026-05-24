# agent-decision-log

[![PyPI](https://img.shields.io/badge/pypi-not%20published-lightgrey.svg)](#install)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#install)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Deps](https://img.shields.io/badge/runtime%20deps-0-brightgreen.svg)](#install)

Structured decision log for AI agents. Record **why** each branch in the agent's reasoning was chosen, not just **what** was called.

Every agent loop already produces a stream of calls. agent-decision-log adds the missing layer: for each decision point, capture the candidate options the model considered, the rationale text, the slice of context that justified the choice, and the outcome once the chosen tool actually runs. Auditors and owners can then trace a behavior back through reasoning, not just calls.

Zero runtime dependencies. Python 3.10+. Pluggable sinks (in-memory, JSONL on disk, or your own). Replay a recorded session against a new prompt or model to see which decisions flipped.

## Install

```bash
pip install agent-decision-log
```

(Not yet published to PyPI. For now, clone the repo and `pip install -e .`.)

## 30-second quickstart

```python
from agent_decision_log import DecisionLog, JsonlSink, Outcome, aggregate

log = DecisionLog(sink=JsonlSink("decisions.jsonl"))

# Inside an agent loop, before calling the chosen tool:
decision = log.record(
    turn=4,
    options=["get_weather", "get_news", "fetch_url"],
    chosen="get_weather",
    rationale="user asked about today's forecast in turn 3",
    context_window=["turn3: user: what's the weather like today?"],
    expected_outcome="returns weather data for the user's location",
)

# After the tool runs:
log.attach_outcome(decision.id, Outcome.SUCCESS, observed="returned 72F NYC")

# Or, if the picked tool turned out wrong:
# log.attach_outcome(decision.id, Outcome.WRONG_TOOL, observed="user actually wanted news")

# Audit a window of decisions:
stats = aggregate(log.iterate())
print(stats.by_option_picked)         # {'get_weather': 1}
print(stats.outcome_distribution)     # {'success': 1}
print(stats.wrong_tool_rate)          # 0.0
print(stats.hallucinated_option_rate) # 0.0
```

## Replay after a prompt change

You changed a system prompt or upgraded a model. Replay walks each recorded decision, calls your fresh agent function with the same context and option list, and tells you which choices flipped.

```python
from agent_decision_log import replay

def my_new_agent(context, options):
    # Call your real agent here; return the chosen option name.
    ...

report = replay(log.iterate(), my_new_agent)
print(report.match_rate)   # how often the new agent agrees with the old log
for row in report.diff_rows():
    print(row.turn, row.original_chosen, "->", row.replayed_chosen)
```

## API

| Symbol | What it is |
| --- | --- |
| `DecisionLog(sink=None)` | Facade. Defaults to in-memory sink. |
| `log.record(turn, options, chosen, rationale, context_window, expected_outcome, metadata)` | Record a single decision. Returns a `Decision`. |
| `log.attach_outcome(decision_id, outcome, observed=None)` | Attach a post-hoc outcome. |
| `log.get(decision_id)` / `log.iterate()` | Read back persisted decisions. |
| `Outcome` | Enum: `SUCCESS`, `PARTIAL`, `WRONG_TOOL`, `TOOL_ERROR`, `HALLUCINATED_OPTION`, `UNKNOWN`. |
| `RationaleQuality` | Enum: `STRUCTURED`, `FREE_TEXT`, `MISSING`. |
| `InMemorySink`, `JsonlSink`, `Sink` | Built-in sinks plus the protocol for your own. |
| `aggregate(decisions)` | Returns a `Stats` snapshot: by-option, outcome distribution, wrong-tool rate, hallucinated-option rate, rationale quality, average options considered. |
| `replay(decisions, agent_fn)` | Returns a `ReplayReport` with match rate and a flat list of flipped decisions. |

## What this is NOT

- **Not a call recorder.** If you want full LLM request and response payloads, use [agentsnap](https://github.com/MukundaKatta/agentsnap). agent-decision-log records the reasoning slice, not the wire bytes.
- **Not a performance tracker.** If you want latency percentiles, cost per call, or per-run cost rollups, use [agenttrace](https://github.com/MukundaKatta/agenttrace). agent-decision-log does not measure how fast or how expensive a decision was.
- **Not a tool-arg validator.** If you want to catch malformed tool calls before they execute, use [agentvet](https://github.com/MukundaKatta/agentvet). agent-decision-log assumes the chosen tool was already validated.
- **Not a guardrail.** It is observability and audit, not enforcement. It does not block a decision. It records that one was made.

## How it fits in the agent stack

agent-decision-log is the **why** layer above call and run telemetry.

| Library | What it captures | Sample question it answers |
| --- | --- | --- |
| [agentsnap](https://github.com/MukundaKatta/agentsnap) | Full call payloads (prompt, response, tool input/output). | "What exactly did the model see and return on turn 4?" |
| [agenttrace](https://github.com/MukundaKatta/agenttrace) | Latency and cost rolled up per run. | "How expensive was this user's session and where did the time go?" |
| **agent-decision-log (this)** | **Why each branch was chosen, with options and outcome.** | **"Why did the agent call get_weather instead of get_news?"** |
| [agentvet](https://github.com/MukundaKatta/agentvet) | Tool-arg validation before execution. | "Are these arguments shaped right before we run the tool?" |
| [prompt-shield](https://github.com/MukundaKatta/prompt-shield) | Input filtering on prompts and tool args. | "Is this prompt or tool input safe to pass through?" |

The four telemetry libs compose. A typical setup: agentsnap records calls, agenttrace tracks cost and latency, agent-decision-log records reasoning, agentvet validates tool args. Then prompt-shield sits in front for input filtering.

## Design notes

- **Single decision record, six fields.** turn, options, chosen, rationale, context window, expected outcome. Anything richer goes in `metadata`. Keeping the schema small means third-party sinks stay shallow.
- **Sinks are a Protocol.** Bring your own backend in one file: implement `append`, `get`, `iterate`, `update_outcome`. Two built-ins ship: `InMemorySink` for tests and short-lived agents, `JsonlSink` for local persistence and replay.
- **Hallucinated options are first-class.** If `chosen` is not in `options`, the library promotes the outcome to `HALLUCINATED_OPTION` even if the caller marked it as a success. Dashboards stay honest when the wiring code is sloppy.
- **Rationale quality is a cheap bucket.** `STRUCTURED` if the text contains markers like "turn N", "because", "tool:", `FREE_TEXT` if non-empty, `MISSING` otherwise. Helps spot decisions that are opaque to audit.
- **Replay is read-only.** It calls your agent function with the recorded context and options, diffs the new choice against the old, and never mutates the log. Use it to compare prompts, models, or guardrail changes.

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

Around 50 tests across decision dataclasses, both sinks, the log facade, aggregate stats, replay, and a real round-trip end-to-end.

## License

MIT. See [LICENSE](LICENSE).
