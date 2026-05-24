# Hermes Agent Challenge submission

**Project**: agent-decision-log
**Repo**: https://github.com/MukundaKatta/agent-decision-log
**License**: MIT
**Python**: 3.10+
**Runtime deps**: 0

---

## Dev.to post draft (paste-ready)

**Title**: I built a decision log for AI agents, because "what was called" is not enough

**Cover blurb**: A small Python library that records why each branch in an agent's reasoning was chosen, with the context the model saw, the option it picked vs. rejected, and the outcome once the tool ran. Zero deps.

**Tags**: ai, python, agents, observability

---

Every team I have helped with an AI agent ends up in the same place. A user complains. Somebody pulls the call trace. The trace shows a clean sequence of tool calls. None of the tool calls look wrong on their own. The user is still right. The agent did the wrong thing.

The trace tells you what was called. It does not tell you why.

I built agent-decision-log to fix exactly that gap. It is a small Python library, around 600 lines of source plus tests, that sits inside your agent loop and records a single structured record at every branch point: the candidate options, the chosen option, the rationale text, the slice of context that justified the pick, and the outcome once the chosen tool runs.

That last word matters. The outcome is attached after the fact, not predicted. The library forces a kind of post-hoc honesty: was this decision actually correct, or did the model commit to a plausible-sounding tool and miss what the user wanted?

## The 30-second example

```python
from agent_decision_log import DecisionLog, JsonlSink, Outcome

log = DecisionLog(sink=JsonlSink("decisions.jsonl"))

# Inside the agent loop, right before calling the chosen tool:
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

# Or, when it picked the wrong branch:
# log.attach_outcome(decision.id, Outcome.WRONG_TOOL,
#                    observed="user actually wanted news")
```

Now you can answer a question that a regular trace cannot answer: "On turn 4, what did the model consider, and why did it land on get_weather?"

## Where it fits

I have been shipping a small family of agent libraries over the last few weeks. Each one captures a different slice of what an agent is doing.

- agentsnap records full call payloads. Prompt in, response out, tool input and output. Great for replaying a single call.
- agenttrace rolls those calls into runs with latency percentiles and cost. Great for cost dashboards.
- agentvet validates tool arguments before execution. Great for catching malformed calls early.
- agent-decision-log records why a branch was chosen, with the context and outcome.

Calls, cost, args, reasoning. Four slices of the same agent run. agent-decision-log is the reasoning slice, and it is the only one that gives you something an auditor or product owner can read without parsing JSON.

## Why "why" needs its own layer

There is an obvious objection. Why not just stuff the rationale into a span attribute or a log line? Two reasons.

First, free-form log lines do not aggregate. If you want to know how many decisions in the last 1000 had no rationale at all, or what fraction of decisions chose an option that was not even in the candidate list, you need a real schema. The library ships one: six fields, all required, all serialized as JSON. You can plug that into a dashboard in an afternoon.

Second, rationale text alone is not auditable. A line that says "I chose this because it seemed right" is not a defensible explanation. The library tags every rationale with one of three quality buckets: STRUCTURED if the text references context or specific turns, FREE_TEXT if it is non-empty prose, MISSING if it is blank. Then it aggregates the buckets. Now "are my agents producing auditable rationales?" is a number, not a vibe.

## The hallucinated-option trap

One small detail I am proud of. If the model picks an option that was not in the candidate list, the library promotes the outcome to HALLUCINATED_OPTION even if the caller said SUCCESS. This sounds like a corner case. It is not.

In real systems the wiring code often classifies any tool call that returns 200 as a success. But the interesting question is whether the model invented a tool name that happens to map to something real. That is the kind of behavior that surfaces only when you actively force the data to stay honest. The library does that for you, in one line of code, because dashboards built on optimistic wiring are how teams get surprised in production.

## Replay after a prompt change

The other piece that pays for itself fast: replay.

You change a system prompt, or you upgrade a model. The unit tests still pass. You want to know which previously-recorded decisions the new setup would have made differently. The library hands you a one-call answer.

```python
from agent_decision_log import replay

def my_new_agent(context, options):
    # Call your real agent here; return the chosen option name.
    ...

report = replay(log.iterate(), my_new_agent)
print(report.match_rate)
for row in report.diff_rows():
    print(row.turn, row.original_chosen, "->", row.replayed_chosen)
```

That is enough to spot regressions on a prompt change before anyone deploys it.

## What it deliberately does not do

It does not record full call payloads. agentsnap already does that, and the two compose cleanly.

It does not track latency or cost. agenttrace already does that, and the two compose cleanly.

It does not block bad decisions. It records that one was made. The point is observability and audit, not enforcement. If you want a guardrail, use a guardrail.

It does not invent a query language. Sinks expose `iterate()`. You pipe that into pandas, DuckDB, or grep. The library stays small on purpose so it can ride along inside agent loops without dragging in a dependency tree.

## What you get out of the box

- A `DecisionLog` facade with a tiny API: `record`, `attach_outcome`, `get`, `iterate`.
- Two built-in sinks: `InMemorySink` for tests and short-lived agents, `JsonlSink` for local persistence and replay.
- A `Sink` Protocol so you can plug in Honeycomb, Datadog, Postgres, Kafka, S3, or whatever you already run.
- An aggregate function that returns counts, ratios, and quality distributions in one call.
- A replay function that diffs a recorded session against a fresh agent.
- Zero runtime dependencies. Python 3.10+. About 50 tests.

## Try it

```bash
git clone https://github.com/MukundaKatta/agent-decision-log
cd agent-decision-log
pip install -e ".[dev]"
pytest -q
python examples/basic_usage.py
python examples/replay_after_prompt_change.py
```

Repo: https://github.com/MukundaKatta/agent-decision-log

If you have an agent in production and you cannot answer "why did it call X instead of Y on turn 4," that is the gap this library fills. Plug it into one branch, ship it, and start asking the question.
