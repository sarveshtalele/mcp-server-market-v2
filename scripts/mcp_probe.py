#!/usr/bin/env python3
"""Connect to the MCP server as a client and print what it offers.

The quickest way to confirm your setup works, and a worked example of writing
your own MCP client against this server.

    python scripts/mcp_probe.py                       # through the gateway
    python scripts/mcp_probe.py --url http://127.0.0.1:8000/mcp
    python scripts/mcp_probe.py --as claude-desktop   # pretend to be a host

The default URL is the **gateway** on :3111. Point it at the backend directly
only when you are debugging the backend itself — a direct connection bypasses
the allowlist and is attributed differently in the audit log.

Whatever `--as` you pass shows up as the source in the Control Room's Audit Log,
which makes this a handy way to see attribution working without installing four
AI hosts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))  # run from anywhere: the client lives in backend/

try:
    from mcp import Client, Implementation
except ModuleNotFoundError:  # pragma: no cover - exercised by running outside the venv
    # The SDK is installed in the project virtualenv, not system Python. Re-run
    # ourselves under that interpreter rather than making the reader remember
    # which python to invoke.
    import os
    import subprocess

    venv_python = BACKEND / ".venv" / (
        "Scripts" if os.name == "nt" else "bin"
    ) / ("python.exe" if os.name == "nt" else "python")
    if not venv_python.exists():
        raise SystemExit(
            f"The MCP SDK is not installed for {sys.executable}, and there is no "
            f"virtualenv at {BACKEND / '.venv'}.\n"
            "Create one first — see README section 2.1."
        ) from None
    # Compare sys.prefix, not the interpreter path: a virtualenv's bin/python is
    # usually a symlink to the base interpreter, so resolved paths match even
    # when we are running outside the venv.
    if Path(sys.prefix).resolve() == (BACKEND / ".venv").resolve():
        raise  # already inside the venv: a genuinely missing dependency
    raise SystemExit(
        subprocess.call([str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])
    )

DEFAULT_URL = "http://127.0.0.1:3111/mcp"
PROTOCOL_VERSION = "2026-07-28"


async def probe(url: str, client_name: str, symbol: str) -> int:
    try:
        async with Client(
            url,
            client_info=Implementation(name=client_name, version="1.0.0"),
            mode=PROTOCOL_VERSION,
            raise_exceptions=True,
        ) as client:
            print(f"connected to      {url}")
            print(f"identifying as    {client_name}")
            print(f"protocol version  {client.protocol_version}")
            info = client.server_info
            if info is not None:
                print(f"server            {info.name} {info.version}")
            print()

            tools = await client.list_tools()
            print(f"tools ({len(tools.tools)}):")
            for tool in tools.tools:
                print(f"  {tool.name}")
            cacheable = tools.model_dump(by_alias=True)
            print(
                f"\ntools/list cache  ttlMs={cacheable.get('ttlMs')} "
                f"cacheScope={cacheable.get('cacheScope')} "
                f"resultType={cacheable.get('resultType')}"
            )

            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            prompts = await client.list_prompts()
            print(f"\nresources ({len(resources.resources)}):")
            for resource in resources.resources:
                print(f"  {resource.uri}")
            for template in templates.resource_templates:
                print(f"  {template.uri_template}")
            print(f"\nprompts ({len(prompts.prompts)}):")
            for prompt in prompts.prompts:
                print(f"  {prompt.name}")

            if not resources.resources:
                print(
                    "\nnote: no resources or prompts listed. agentgateway does not\n"
                    "      proxy them — use the read_market_resource tool, which\n"
                    "      passes through and stays audited."
                )

            print(f"\ncalling get_company(symbol={symbol!r}):")
            result = await client.call_tool("get_company", {"symbol": symbol})
            payload = json.loads(result.content[0].text)
            for key in ("symbol", "company_name", "sector", "last_price", "market_cap"):
                if key in payload:
                    print(f"  {key:<14} {payload[key]}")
            if "error" in payload:
                print(f"  error          {payload['error']}")

            print("\nOK — this call is now in the Audit Log at")
            print("     http://localhost:3000/audit")
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic tool
        print(f"\nFAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "\nIs the stack running? Start it with:  python scripts/dev.py all",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help=f"default {DEFAULT_URL}")
    parser.add_argument(
        "--as",
        dest="client_name",
        default="mcp-probe",
        help="client name reported in _meta.clientInfo (drives audit attribution)",
    )
    parser.add_argument("--symbol", default="AAPL")
    args = parser.parse_args()
    return asyncio.run(probe(args.url, args.client_name, args.symbol))


if __name__ == "__main__":
    sys.exit(main())
