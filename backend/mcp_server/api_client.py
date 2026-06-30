"""Generic async HTTP client for the Data API.

Module tools fetch data *over HTTP* (not via direct DB access), so the API
boundary is real. This client is intentionally generic — a module calls
``await api.get("/<its-router>/<path>")`` — so new modules need no client changes.
"""
from __future__ import annotations

from typing import Any

import httpx

from core.config import settings


class DataAPIError(RuntimeError):
    """Raised when the Data API returns a non-2xx response."""


class DataAPIClient:
    def __init__(self, base_url: str | None = None, timeout: float = 15.0) -> None:
        self.base_url = (base_url or settings.data_api_base_url).rstrip("/")
        self.timeout = timeout

    async def get(self, path: str, params: dict | None = None) -> Any:
        """GET {base_url}{path}; raise DataAPIError on failure, else return JSON."""
        url = f"{self.base_url}{path}"
        # Drop None-valued params for clean query strings.
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params=clean or None)
        if resp.status_code == 404:
            detail = _safe_detail(resp)
            raise DataAPIError(f"Not found: {path} ({detail})")
        if resp.status_code >= 400:
            raise DataAPIError(f"API error {resp.status_code} for {path}: {resp.text}")
        return resp.json()


def _safe_detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("detail"))
    except Exception:  # noqa: BLE001
        return resp.text[:200]
