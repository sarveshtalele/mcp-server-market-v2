"""Shared fixtures.

Both databases are redirected to a temporary directory **before** any backend
module is imported, so a test run can never touch the developer's seeded
``stock_market.db`` or their audit history.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# --- must happen before importing anything that reads settings --------------
_TMP = Path(tempfile.mkdtemp(prefix="mcp-market-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test_market.db').as_posix()}"
os.environ["OBSERVABILITY_DATABASE_URL"] = f"sqlite:///{(_TMP / 'test_obs.db').as_posix()}"
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest  # noqa: E402
from mcp import Client, Implementation  # noqa: E402

from core.seed import seed  # noqa: E402
from mcp_server.server import build_server  # noqa: E402
from modules.observability.models import McpCall  # noqa: E402
from modules.observability.store import ObsSessionLocal, init_obs_db  # noqa: E402

# Symbols the golden fixtures are pinned to.
GOLDEN_SYMBOLS = ["AAPL", "JPM", "BAC", "WFC", "MSFT", "NVDA"]


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """Seed a throwaway copy of the synthetic dataset once per run."""
    seed(reset=True)
    init_obs_db()


@pytest.fixture(scope="session")
def mcp_server():
    """A freshly built MCP server instance."""
    return build_server()


def connected(server, **kwargs):
    """In-memory MCP client — no HTTP, no gateway, full protocol semantics.

    Deliberately a helper rather than an async fixture: the SDK's transport uses
    an anyio task group, and pytest-asyncio finalises async-generator fixtures in
    a different task than it created them in, which trips anyio's cancel-scope
    check ("Attempted to exit cancel scope in a different task"). Entering and
    exiting inside the test body keeps both in one task.
    """
    kwargs.setdefault("client_info", Implementation(name="pytest-client", version="1.0"))
    kwargs.setdefault("raise_exceptions", True)
    return Client(server, **kwargs)


@pytest.fixture
def obs_db():
    """A clean audit table for each test that inspects it."""
    with ObsSessionLocal() as db:
        db.query(McpCall).delete()
        db.commit()
    with ObsSessionLocal() as db:
        yield db


@pytest.fixture(scope="session")
def live_server(_database):
    """A real uvicorn server, so transport behaviour is tested for real.

    The MCP endpoint's Origin/Host validation, the 405 answers and the audit
    recorder are all ASGI-layer behaviour; an in-memory client would skip them.
    """
    import socket
    import threading
    import time

    import uvicorn

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    os.environ["PORT"] = str(port)
    from core.config import get_settings

    get_settings.cache_clear()
    import core.config as config_module

    config_module.settings = get_settings()

    import app.main as app_module

    config = uvicorn.Config(app_module.app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 30
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("live server did not start")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)
