"""SPECS AGENT-1 — one real end-to-end run through the agent.

Everything else mocks or bypasses the model. This drives the actual configured
LLM through the AG-UI endpoint and asserts the event contract holds: text
streams, a tool is chosen and executed, and exactly one usage event closes the
run.

Skipped unless credentials are configured, so the default suite stays free and
deterministic:

    pytest -m llm

Costs tokens and depends on the model choosing to call a tool, so it asserts the
protocol shape rather than the wording of the answer.
"""

from __future__ import annotations

import json
import os
import uuid

import httpx2
import pytest

from core.config import settings

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")


def _backend_up() -> bool:
    try:
        return httpx2.get(f"{BACKEND_URL}/health", timeout=2).status_code == 200
    except Exception:  # noqa: BLE001 - any failure means "not available"
        return False


# Loud skips naming the missing prerequisite: a silent skip reads like a pass.
pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(
        not settings.llm_api_key,
        reason="LLM_API_KEY is not set in backend/.env — see README section 2.4",
    ),
    pytest.mark.skipif(
        not _backend_up(),
        reason=f"no backend at {BACKEND_URL} — start it with `python scripts/dev.py all`",
    ),
]


def _run(prompt: str) -> list[dict]:
    """POST one AG-UI run and collect the decoded events."""
    payload = {
        "threadId": f"pytest-{uuid.uuid4().hex[:8]}",
        "runId": uuid.uuid4().hex,
        "state": {},
        "messages": [{"id": uuid.uuid4().hex, "role": "user", "content": prompt}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    events: list[dict] = []
    with httpx2.stream(
        "POST",
        f"{BACKEND_URL}/agui",
        json=payload,
        headers={"Accept": "text/event-stream"},
        timeout=180,
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body:
                events.append(json.loads(body))
    return events


def test_a_run_emits_the_agui_contract() -> None:
    """AGENT-1.1 / AGENT-1.4."""
    events = _run("Show me AAPL's company profile.")
    types = [event["type"] for event in events]

    assert types[0] == "RUN_STARTED"
    assert "RUN_ERROR" not in types, [
        e.get("message") for e in events if e["type"] == "RUN_ERROR"
    ]
    assert types[-1] == "RUN_FINISHED"

    usage = [e for e in events if e["type"] == "CUSTOM" and e.get("name") == "usage"]
    assert len(usage) == 1, "exactly one usage event closes a run"
    value = usage[0]["value"]
    assert value["totalTokens"] > 0
    assert value["elapsedMs"] > 0
    assert value["protocolVersion"] == "2026-07-28"


def test_the_model_answers_from_tools_not_memory() -> None:
    """Invariant #3 — the answer must come from a tool call.

    The seeded prices are synthetic, so a model answering from pretrained
    knowledge would be both wrong and unable to produce a tool result.
    """
    events = _run("What is AAPL's last price and market cap?")
    tool_calls = [e for e in events if e["type"] == "TOOL_CALL_START"]
    results = [e for e in events if e["type"] == "TOOL_CALL_RESULT"]

    assert tool_calls, "the model answered without calling a tool"
    assert results, "a tool was started but never returned"
    assert any("AAPL" in (e.get("content") or "") for e in results)


def test_reasoning_is_never_forwarded() -> None:
    """Invariant — chain-of-thought must not reach the UI."""
    events = _run("Compare JPM and BAC on profitability.")
    for event in events:
        assert "reasoning" not in json.dumps(event).lower(), event["type"]
