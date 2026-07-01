"""AG-UI agent HTTP service.

Exposes a single AG-UI endpoint (POST /agui) that the browser chat connects to.
Streams AG-UI events as Server-Sent Events.

Run:
    uvicorn agui_agent.main:app --reload --port 8001
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from ag_ui.core import RunAgentInput
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agui_agent.agent import ExchangeAgent
from core.config import settings
from core.logging_config import get_logger

log = get_logger("agui")
agent = ExchangeAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is required to run the AG-UI agent.")
    await agent.startup()
    log.info(
        "AG-UI agent ready on model '%s' - %d MCP tools available.",
        settings.llm_model,
        len(agent.mcp.tool_names),
    )
    yield
    await agent.shutdown()


app = FastAPI(title="Stock Exchange AG-UI Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/agui")
async def agui_endpoint(input_data: RunAgentInput, request: Request) -> StreamingResponse:
    """AG-UI run endpoint consumed by the browser chat.

    Accepts a RunAgentInput (thread/run ids + message history) and returns an
    SSE stream of AG-UI events (text deltas, tool calls, run lifecycle).
    """
    accept = request.headers.get("accept")
    n_msgs = len(input_data.messages)
    log.info("run %s (thread %s) - %d message(s)", input_data.run_id, input_data.thread_id, n_msgs)
    return StreamingResponse(
        agent.run(input_data, accept),
        media_type="text/event-stream",
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "tools": agent.mcp.tool_names}
