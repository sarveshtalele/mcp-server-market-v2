#!/usr/bin/env python3
"""Cross-platform launcher — replaces run_all.bat and the .ps1 helpers.

    python scripts/dev.py all        # gateway + backend + frontend
    python scripts/dev.py backend    # FastAPI (REST + MCP + AG-UI) on :8000
    python scripts/dev.py gateway    # agentgateway on :3111
    python scripts/dev.py frontend   # Next.js on :3000
    python scripts/dev.py seed       # rebuild the synthetic dataset

Start order matters only a little: the backend connects to the gateway lazily,
and the gateway retries its target, so either can come up first. `all` starts
the gateway, waits for the backend to answer /health, then starts the frontend.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
GATEWAY_DIR = BACKEND / "mcp_server" / "gateway"
LOG_DIR = GATEWAY_DIR / "logs"

IS_WINDOWS = os.name == "nt"
VENV_PYTHON = BACKEND / ".venv" / ("Scripts" if IS_WINDOWS else "bin") / (
    "python.exe" if IS_WINDOWS else "python"
)
GATEWAY_BIN = GATEWAY_DIR / "bin" / ("agentgateway.exe" if IS_WINDOWS else "agentgateway")


def python_exe() -> str:
    """Prefer the project venv; fall back to the interpreter running this."""
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _port_open(host: str, port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.4)
        return probe.connect_ex((host, port)) == 0


def _wait_for_http(url: str, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.5)
    return False


def run_backend(background: bool = False) -> subprocess.Popen | int:
    command = [
        python_exe(),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        os.environ.get("HOST", "127.0.0.1"),
        "--port",
        os.environ.get("PORT", "8000"),
    ]
    if background:
        return subprocess.Popen(command, cwd=BACKEND)
    return subprocess.call(command, cwd=BACKEND)


def run_gateway(background: bool = False) -> subprocess.Popen | int:
    if not GATEWAY_BIN.exists():
        print(
            "agentgateway is not installed.\n"
            "  python scripts/get_gateway.py\n"
            "It is the chokepoint every MCP consumer goes through, so the audit "
            "log is empty without it."
        )
        return 1
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    command = [str(GATEWAY_BIN), "-f", str(GATEWAY_DIR / "config.yaml")]
    if background:
        stdout = (LOG_DIR / "stdout.log").open("a")
        stderr = (LOG_DIR / "stderr.log").open("a")
        return subprocess.Popen(command, stdout=stdout, stderr=stderr)
    return subprocess.call(command)


def run_frontend(background: bool = False) -> subprocess.Popen | int:
    npm = shutil.which("npm")
    if npm is None:
        print("npm not found on PATH — install Node.js 18+ to run the web UI.")
        return 1
    if not (FRONTEND / "node_modules").exists():
        print("Installing frontend dependencies (first run)...")
        subprocess.call([npm, "install"], cwd=FRONTEND)
    command = [npm, "run", "dev"]
    if background:
        return subprocess.Popen(command, cwd=FRONTEND)
    return subprocess.call(command, cwd=FRONTEND)


def run_seed() -> int:
    return subprocess.call([python_exe(), "-m", "core.seed", "--reset"], cwd=BACKEND)


def run_all() -> int:
    processes: list[subprocess.Popen] = []
    try:
        if _port_open("127.0.0.1", 3111):
            print("gateway  : already running on :3111")
        else:
            gateway = run_gateway(background=True)
            if isinstance(gateway, int):
                return gateway
            processes.append(gateway)
            print(f"gateway  : starting on :3111  (logs in {LOG_DIR})")

        backend = run_backend(background=True)
        processes.append(backend)
        print("backend  : starting on :8000")
        if not _wait_for_http("http://127.0.0.1:8000/health"):
            print("backend did not become healthy — check the output above.")
            return 1
        print("backend  : ready")

        processes.append(run_frontend(background=True))
        print("frontend : starting on :3000")
        print("\nControl Room: http://localhost:3000")
        print("API docs    : http://127.0.0.1:8000/docs")
        print("Audit API   : http://127.0.0.1:8000/observability/calls")
        print("\nCtrl+C to stop everything.\n")

        while True:
            for process in processes:
                if process.poll() is not None:
                    print(f"A process exited with code {process.returncode}; stopping.")
                    return process.returncode or 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                try:
                    if IS_WINDOWS:
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        process.terminate()
                    process.wait(timeout=10)
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["all", "backend", "gateway", "frontend", "seed"],
    )
    args = parser.parse_args()

    if not VENV_PYTHON.exists() and args.target in ("all", "backend", "seed"):
        # Built outside the f-string: backslashes are not allowed inside an
        # f-string expression before Python 3.12, and this project targets 3.11.
        pip_path = "backend\\.venv\\Scripts\\pip" if IS_WINDOWS else "backend/.venv/bin/pip"
        print(
            f"No virtualenv at {BACKEND / '.venv'} - falling back to {sys.executable}.\n"
            "Create one with:\n"
            "  python -m venv backend/.venv\n"
            f"  {pip_path} install -r backend/requirements-dev.txt\n"
        )

    print(f"platform: {platform.system()} {platform.machine()}")

    return {
        "all": run_all,
        "backend": run_backend,
        "gateway": run_gateway,
        "frontend": run_frontend,
        "seed": run_seed,
    }[args.target]()


if __name__ == "__main__":
    sys.exit(main())
