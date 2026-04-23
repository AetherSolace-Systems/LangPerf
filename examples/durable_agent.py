"""Durable trajectory across process boundaries — queue-based example.

Demonstrates a multi-segment trajectory for an agent that suspends
between steps. In a real app each segment would run in a different
process (webhook, worker, scheduled job); here we simulate by
sequentially entering three `with langperf.trajectory(...)` blocks
that share one stable run_id.

Run with:
    export LANGPERF_API_TOKEN=lp_...
    python examples/durable_agent.py
"""
from __future__ import annotations

import time
import uuid

import langperf


def step_one() -> None:
    """Imagine this fires in process A, then the process exits."""
    with langperf.node(kind="tool", name="collect_inputs"):
        time.sleep(0.05)
    with langperf.node(kind="llm", name="draft_plan"):
        time.sleep(0.05)


def step_two() -> None:
    """Imagine this fires in process B, waking on a webhook."""
    with langperf.node(kind="tool", name="await_human_ack"):
        time.sleep(0.05)
    with langperf.node(kind="llm", name="revise_plan"):
        time.sleep(0.05)


def step_three() -> None:
    """Imagine this fires in process C, the final step."""
    with langperf.node(kind="tool", name="execute"):
        time.sleep(0.05)
    with langperf.node(kind="llm", name="summarize"):
        time.sleep(0.05)


def main() -> None:
    langperf.init()

    # Your app persists this run_id with its workflow state.
    run_id = str(uuid.uuid4())
    print(f"run_id = {run_id}")

    # Segment 1 — kickoff. In a real app the process would exit here.
    with langperf.trajectory("durable_demo", id=run_id, final=False):
        step_one()

    # Simulated pause — in a real app, minutes/hours later.
    time.sleep(0.5)

    # Segment 2 — resume. Still not final.
    with langperf.trajectory("durable_demo", id=run_id, final=False):
        step_two()

    time.sleep(0.5)

    # Segment 3 — final. Stamps langperf.completed=True on the row.
    with langperf.trajectory("durable_demo", id=run_id, final=True):
        step_three()

    langperf.flush()
    print("Done. Check the LangPerf UI for trajectory", run_id)


if __name__ == "__main__":
    main()
