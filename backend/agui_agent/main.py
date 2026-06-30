"""AG-UI agent HTTP service.

Exposes a single AG-UI endpoint (POST /agui) that the CopilotKit runtime
connects to via HttpAgent. Streams AG-UI events as Server-Sent Events.

Run:
    uvicorn agui_agent.main:app --reload --port 8001
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from ag_ui.core import RunAgentInput
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agui_agent.agent import SETAgent
from core.config import settings

agent = SETAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is required to run the AG-UI agent.")
    await agent.startup()
    yield
    await agent.shutdown()


app = FastAPI(title="SET Market AG-UI Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/agui")
async def agui_endpoint(input_data: RunAgentInput, request: Request) -> StreamingResponse:
    """AG-UI run endpoint consumed by the CopilotKit HttpAgent."""
    accept = request.headers.get("accept")
    return StreamingResponse(
        agent.run(input_data, accept),
        media_type="text/event-stream",
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "tools": agent.mcp.tool_names}
