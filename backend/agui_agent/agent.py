"""The streaming agent core.

Bridges three things:
  * An OpenAI-compatible LLM (a LiteLLM proxy) for reasoning + streaming text
  * The MCP server (tools, via MCPToolClient)
  * The AG-UI protocol (events the frontend understands)

For each user run it emits:
  RUN_STARTED
    -> [TEXT_MESSAGE_START / CONTENT* / END]      (streamed assistant text)
    -> [TOOL_CALL_START / ARGS / END / RESULT]*    (tool calls -> generative UI)
  RUN_FINISHED   (or RUN_ERROR on failure)

Note: the proxy's Claude models are reasoning models. Their chain-of-thought
arrives as `delta.reasoning_content` and is intentionally NOT forwarded to the
UI — only the final `delta.content` is streamed as assistant text.
"""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator

from ag_ui.core import (
    CustomEvent,
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from openai import AsyncOpenAI

from core.config import settings
from core.logging_config import get_logger
from mcp_client.session import MCPToolClient

log = get_logger("agent")

SYSTEM_PROMPT = (
    "You are a stock-exchange market analyst assistant. "
    "Use the available tools to fetch company listings and filings and to compute "
    "financial ratios, growth and comparisons. Only report numbers returned by the "
    "tools — never invent figures. All monetary values are in US dollars (USD). "
    "After calling tools, summarise the findings for the user in clear prose; the "
    "raw tool data is rendered separately as interactive cards."
)
# Cap the tool-resolution loop to avoid runaway calls.
MAX_TOOL_ROUNDS = 6
# Cap how much prompt/response text lands in logs (they can carry tool data).
_LOG_PREVIEW_CHARS = 300


def _truncate(text: str, limit: int = _LOG_PREVIEW_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + f"...[+{len(text) - limit} chars]"


class ExchangeAgent:
    """Holds long-lived LLM + MCP clients and runs AG-UI streams."""

    def __init__(self) -> None:
        self.llm = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.openai_base_url,
        )
        self.mcp = MCPToolClient()
        self._tools: list[dict] = []

    async def startup(self) -> None:
        await self.mcp.connect()
        self._tools = self.mcp.openai_tools()

    async def shutdown(self) -> None:
        await self.mcp.close()

    @staticmethod
    def _to_openai_messages(input_data: RunAgentInput) -> list[dict]:
        """Map AG-UI chat history to OpenAI messages, prepending the system prompt."""
        out: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in input_data.messages:
            role = getattr(m, "role", None)
            content = getattr(m, "content", None)
            if role in ("user", "assistant") and content:
                out.append({"role": role, "content": content})
        if len(out) == 1:
            out.append({"role": "user", "content": "Hello"})
        return out

    async def run(
        self, input_data: RunAgentInput, accept_header: str | None
    ) -> AsyncIterator[str]:
        """Yield encoded AG-UI SSE events for one run."""
        encoder = EventEncoder(accept=accept_header)
        thread_id = input_data.thread_id
        run_id = input_data.run_id
        run_t0 = time.perf_counter()
        full_response = ""
        usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        tool_call_count = 0

        yield encoder.encode(
            RunStartedEvent(
                type=EventType.RUN_STARTED, thread_id=thread_id, run_id=run_id
            )
        )

        try:
            messages = self._to_openai_messages(input_data)
            last_user = next(
                (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
            )
            log.info("run %s prompt: %r", run_id, _truncate(str(last_user)))

            for _ in range(MAX_TOOL_ROUNDS):
                turn: dict = {"text": "", "tool_calls": [], "finish": None}
                async for chunk in self._stream_turn(encoder, messages, turn):
                    yield chunk
                full_response += turn["text"]
                if turn["usage"]:
                    for key in usage_totals:
                        usage_totals[key] += turn["usage"].get(key) or 0

                if turn["finish"] != "tool_calls" or not turn["tool_calls"]:
                    break

                tool_call_count += len(turn["tool_calls"])

                # Record the assistant turn (text + tool_calls) in history.
                messages.append(
                    {
                        "role": "assistant",
                        "content": turn["text"] or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["args"] or "{}",
                                },
                            }
                            for tc in turn["tool_calls"]
                        ],
                    }
                )

                # Execute each tool and feed the result back as a tool message.
                for tc in turn["tool_calls"]:
                    async for chunk in self._run_tool(encoder, tc):
                        yield chunk
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tc["result"],
                        }
                    )

            elapsed_ms = (time.perf_counter() - run_t0) * 1000
            log.info(
                "run %s finished in %.1f ms - response %d chars, %d token(s) (%d in / %d out), %d tool call(s): %r",
                run_id,
                elapsed_ms,
                len(full_response),
                usage_totals["total_tokens"],
                usage_totals["prompt_tokens"],
                usage_totals["completion_tokens"],
                tool_call_count,
                _truncate(full_response),
            )
            yield encoder.encode(
                CustomEvent(
                    type=EventType.CUSTOM,
                    name="usage",
                    value={
                        "elapsedMs": round(elapsed_ms, 1),
                        "promptTokens": usage_totals["prompt_tokens"],
                        "completionTokens": usage_totals["completion_tokens"],
                        "totalTokens": usage_totals["total_tokens"],
                        "toolCalls": tool_call_count,
                    },
                )
            )
            yield encoder.encode(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id
                )
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            elapsed_ms = (time.perf_counter() - run_t0) * 1000
            log.error("run %s failed after %.1f ms: %s", run_id, elapsed_ms, exc)
            yield encoder.encode(
                RunErrorEvent(type=EventType.RUN_ERROR, message=str(exc))
            )

    # -- internal helpers --------------------------------------------------
    async def _stream_turn(
        self, encoder: EventEncoder, messages: list[dict], turn: dict
    ) -> AsyncIterator[str]:
        """Stream one assistant turn; yield text events; collect tool calls.

        Mutates `turn` with text, tool_calls and finish_reason.
        """
        message_id = uuid.uuid4().hex
        text_open = False
        acc: dict[int, dict] = {}  # tool-call index -> {id, name, args}
        turn_t0 = time.perf_counter()
        turn["usage"] = None

        stream = await self.llm.chat.completions.create(
            model=settings.llm_model,
            max_tokens=settings.max_tokens,
            stream=True,
            tools=self._tools,
            messages=messages,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            # The usage summary arrives on its own final chunk (empty choices).
            if getattr(chunk, "usage", None):
                turn["usage"] = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if getattr(delta, "content", None):
                if not text_open:
                    text_open = True
                    yield encoder.encode(
                        TextMessageStartEvent(
                            type=EventType.TEXT_MESSAGE_START,
                            message_id=message_id,
                            role="assistant",
                        )
                    )
                turn["text"] += delta.content
                yield encoder.encode(
                    TextMessageContentEvent(
                        type=EventType.TEXT_MESSAGE_CONTENT,
                        message_id=message_id,
                        delta=delta.content,
                    )
                )

            for tc in getattr(delta, "tool_calls", None) or []:
                slot = acc.setdefault(tc.index, {"id": None, "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments

            if choice.finish_reason:
                turn["finish"] = choice.finish_reason

        if text_open:
            yield encoder.encode(
                TextMessageEndEvent(
                    type=EventType.TEXT_MESSAGE_END, message_id=message_id
                )
            )

        turn["tool_calls"] = [
            {
                "id": slot["id"] or uuid.uuid4().hex,
                "name": slot["name"],
                "args": slot["args"],
                "result": None,
            }
            for _, slot in sorted(acc.items())
            if slot["name"]
        ]

        elapsed_ms = (time.perf_counter() - turn_t0) * 1000
        log.info(
            "llm turn -> %.1f ms, finish=%s, %d char(s), %d tool_call(s), usage=%s: %r",
            elapsed_ms,
            turn["finish"],
            len(turn["text"]),
            len(turn["tool_calls"]),
            turn["usage"],
            _truncate(turn["text"]),
        )

    async def _run_tool(self, encoder: EventEncoder, tc: dict) -> AsyncIterator[str]:
        """Emit AG-UI tool-call events and execute the tool via MCP."""
        tool_call_id = tc["id"]
        yield encoder.encode(
            ToolCallStartEvent(
                type=EventType.TOOL_CALL_START,
                tool_call_id=tool_call_id,
                tool_call_name=tc["name"],
            )
        )
        yield encoder.encode(
            ToolCallArgsEvent(
                type=EventType.TOOL_CALL_ARGS,
                tool_call_id=tool_call_id,
                delta=tc["args"] or "{}",
            )
        )
        yield encoder.encode(
            ToolCallEndEvent(type=EventType.TOOL_CALL_END, tool_call_id=tool_call_id)
        )

        try:
            args = json.loads(tc["args"]) if tc["args"] else {}
        except json.JSONDecodeError:
            args = {}

        t0 = time.perf_counter()
        result = await self.mcp.call_tool(tc["name"], args)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        tc["result"] = result
        tc["ms"] = round(elapsed_ms, 1)
        log.info("tool %s(%s) -> %d chars in %.1f ms", tc["name"], args, len(result), elapsed_ms)

        yield encoder.encode(
            ToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT,
                message_id=uuid.uuid4().hex,
                tool_call_id=tool_call_id,
                content=result,
            )
        )
