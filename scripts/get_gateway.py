#!/usr/bin/env python3
"""Download the agentgateway binary for this machine.

Cross-platform replacement for the old Windows-only ``setup.ps1``. Picks the
right release asset for the host OS and CPU, verifies the published SHA-256,
and drops it in ``backend/mcp_server/gateway/bin/`` (gitignored — the binary is
~80 MB and is never committed).

    python scripts/get_gateway.py              # install the pinned version
    python scripts/get_gateway.py --version v1.4.1
    python scripts/get_gateway.py --force      # re-download

Version floor is 1.4.1: 1.4 (released 2026-07-27) added support for the
MCP 2026-07-28 revision and 1.4.1 added compatibility fixes. Older builds
cannot front this server.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_VERSION = "v1.4.1"
REPO = "agentgateway/agentgateway"
GATEWAY_DIR = Path(__file__).resolve().parent.parent / "backend" / "mcp_server" / "gateway"
BIN_DIR = GATEWAY_DIR / "bin"


def asset_name() -> str:
    """Map this machine to a published release asset."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        raise SystemExit(f"Unsupported CPU architecture: {platform.machine()}")

    if system == "windows":
        if arch != "amd64":
            raise SystemExit("agentgateway publishes Windows builds for amd64 only.")
        return "agentgateway-windows-amd64.exe"
    if system == "darwin":
        if arch != "arm64":
            raise SystemExit(
                "agentgateway publishes macOS builds for Apple Silicon (arm64) only. "
                "On an Intel Mac, run the gateway under Docker or use a Linux host."
            )
        return "agentgateway-darwin-arm64"
    if system == "linux":
        return f"agentgateway-linux-{arch}"
    raise SystemExit(f"Unsupported operating system: {platform.system()}")


def target_path() -> Path:
    return BIN_DIR / ("agentgateway.exe" if os.name == "nt" else "agentgateway")


def _download(url: str, destination: Path) -> None:
    try:
        with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            read = 0
            while chunk := response.read(1 << 20):
                handle.write(chunk)
                read += len(chunk)
                if total:
                    percent = read * 100 // total
                    print(f"\r  {percent:3d}%  {read >> 20} / {total >> 20} MB", end="")
        print()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Download failed ({exc.code}): {url}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Download failed: {exc.reason}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--force", action="store_true", help="re-download if present")
    args = parser.parse_args()

    destination = target_path()
    if destination.exists() and not args.force:
        print(f"Already installed: {destination}")
        print("Re-run with --force to download again.")
        return 0

    name = asset_name()
    base = f"https://github.com/{REPO}/releases/download/{args.version}/{name}"
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading agentgateway {args.version} ({name})...")
    _download(base, destination)

    print("Verifying checksum...")
    try:
        with urllib.request.urlopen(f"{base}.sha256") as response:
            expected = response.read().decode().split()[0].strip()
    except urllib.error.URLError:
        print("  ! checksum file unavailable — skipping verification")
    else:
        actual = _sha256(destination)
        if actual != expected:
            destination.unlink(missing_ok=True)
            raise SystemExit(f"Checksum mismatch!\n  expected {expected}\n  got      {actual}")
        print("  checksum OK")

    if os.name != "nt":
        destination.chmod(destination.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP)

    (GATEWAY_DIR / "logs").mkdir(exist_ok=True)
    print(f"\nInstalled: {destination}")
    print("Start it with:  python scripts/dev.py gateway")
    return 0


if __name__ == "__main__":
    sys.exit(main())
