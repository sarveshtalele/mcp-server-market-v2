"""Terminal chatbot — an MCP client that drives the LLM with the MCP tools.

Quick way to test the MCP server without the web frontend:

    python -m mcp_client.cli_chat

Talks to the OpenAI-compatible proxy configured in backend/.env
(ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL).
"""
from __future__ import annotations

import asyncio
import json
import sys

from openai import AsyncOpenAI

from core.config import settings
from mcp_client.session import MCPToolClient

SYSTEM_PROMPT = (
    "You are a stock-exchange market analyst assistant. "
    "Use the provided tools to fetch company listings and filings and to run "
    "financial calculations. Only state numbers returned by the tools — never "
    "invent figures. All monetary values are in US dollars (USD). "
    "Present results clearly and concisely."
)
MAX_TOOL_ROUNDS = 6


async def run_turn(
    llm: AsyncOpenAI,
    client: MCPToolClient,
    messages: list[dict],
    tools: list[dict],
) -> str:
    """Run one user turn, resolving any tool calls in a loop."""
    for _ in range(MAX_TOOL_ROUNDS):
        response = await llm.chat.completions.create(
            model=settings.llm_model,
            max_tokens=settings.max_tokens,
            tools=tools,
            messages=messages,
        )
        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        if finish != "tool_calls" or not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            return msg.content or ""

        # Append the assistant turn (with tool_calls), then resolve them.
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"  [tool] {tc.function.name}({args})")
            result = await client.call_tool(tc.function.name, args)
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )
    return "(stopped: too many tool rounds)"


async def main() -> None:
    # Windows consoles default to cp1252 and choke on non-ASCII characters etc.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    if not settings.llm_api_key or not settings.openai_base_url:
        raise SystemExit("Set LLM_API_KEY and LLM_BASE_URL in backend/.env.")

    llm = AsyncOpenAI(
        api_key=settings.llm_api_key, base_url=settings.openai_base_url
    )
    client = MCPToolClient()
    await client.connect()
    print(f"Connected to MCP server. Tools: {', '.join(client.tool_names)}")
    print(f"Model: {settings.llm_model}")
    print("Ask about companies (type 'exit' to quit).\n")

    tools = client.openai_tools()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    try:
        while True:
            user = input("You: ").strip()
            if user.lower() in {"exit", "quit"}:
                break
            if not user:
                continue
            messages.append({"role": "user", "content": user})
            answer = await run_turn(llm, client, messages, tools)
            print(f"\nAssistant: {answer}\n")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
