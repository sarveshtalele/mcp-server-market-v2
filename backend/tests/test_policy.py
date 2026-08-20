"""SPECS GOV-3 — editing the gateway allowlist from the Control Room.

The allowlist is the governance boundary, and this code rewrites the gateway's
own config file. The tests below care about two things above all: that a bad
request cannot inject anything into that file, and that a failed write cannot
leave it half-formed — a corrupt config means the gateway will not start.
"""

from __future__ import annotations

import shutil

import httpx2
import pytest

from modules.observability import policy


@pytest.fixture
def gateway_config(tmp_path, monkeypatch):
    """A disposable copy of the real config, so tests never touch the shipped one."""
    source = policy.config_path()
    if not source.exists():
        pytest.skip(f"no gateway config at {source}")
    target = tmp_path / "config.yaml"
    shutil.copy(source, target)
    monkeypatch.setattr(policy, "config_path", lambda: target)
    return target


KNOWN = [
    "get_company",
    "search_companies",
    "list_sectors",
    "get_filings",
    "read_market_resource",
]


def test_reads_the_shipped_allowlist() -> None:
    allowed = policy.read_allowlist()
    assert "get_company" in allowed
    assert "read_market_resource" in allowed


def test_write_then_read_round_trips(gateway_config) -> None:
    policy.write_allowlist(["get_company", "list_sectors"], KNOWN)
    assert policy.read_allowlist() == ["get_company", "list_sectors"]


def test_write_preserves_the_rest_of_the_config(gateway_config) -> None:
    """The comments explain why the gateway is configured as it is.

    A YAML round-trip would strip them, which is why this edits line-wise.
    """
    before = gateway_config.read_text()
    policy.write_allowlist(["get_company"], KNOWN)
    after = gateway_config.read_text()

    for marker in (
        "binds:",
        "port: 3111",
        "host: http://127.0.0.1:8000/mcp",
        "mcpAuthorization:",
        "allowOrigins:",
        "# agentgateway — the single chokepoint",
    ):
        assert marker in after, f"{marker!r} was lost"
    assert len(after) < len(before)  # rules were removed, nothing else


def test_duplicates_are_collapsed(gateway_config) -> None:
    policy.write_allowlist(["get_company", "get_company"], KNOWN)
    assert policy.read_allowlist() == ["get_company"]


def test_unknown_tool_is_rejected(gateway_config) -> None:
    before = gateway_config.read_text()
    with pytest.raises(policy.PolicyError, match="unknown tool"):
        policy.write_allowlist(["get_company", "not_a_tool"], KNOWN)
    assert gateway_config.read_text() == before, "the file must be left untouched"


@pytest.mark.parametrize(
    "injection",
    [
        "get_company\"'\n                      - 'true",  # break out of the quoting
        "tool name with spaces",
        "../../etc/passwd",
        "",
    ],
)
def test_malformed_names_cannot_reach_the_file(gateway_config, injection) -> None:
    """A caller must not be able to write arbitrary YAML into the gateway config."""
    before = gateway_config.read_text()
    with pytest.raises(policy.PolicyError):
        policy.write_allowlist([injection], KNOWN + [injection])
    assert gateway_config.read_text() == before


def test_empty_allowlist_denies_rather_than_dangling(gateway_config) -> None:
    """`rules:` with nothing under it is invalid YAML for the gateway."""
    policy.write_allowlist([], KNOWN)
    text = gateway_config.read_text()
    assert policy.read_allowlist() == []
    assert "- 'false'" in text


def test_editing_can_be_disabled(gateway_config, monkeypatch) -> None:
    from core.config import settings

    monkeypatch.setattr(settings, "allow_policy_edit", False)
    before = gateway_config.read_text()
    with pytest.raises(policy.PolicyError, match="disabled"):
        policy.write_allowlist(["get_company"], KNOWN)
    assert gateway_config.read_text() == before


# --- the HTTP surface ------------------------------------------------------


def test_policy_endpoint_lists_every_tool(live_server) -> None:
    payload = httpx2.get(f"{live_server}/observability/policy", timeout=10).json()
    assert payload["editable"] is True
    names = [t["name"] for t in payload["tools"]]
    assert len(names) == 11
    assert names == sorted(names)
    assert all(isinstance(t["allowed"], bool) for t in payload["tools"])


def test_put_policy_rejects_an_unknown_tool(live_server) -> None:
    response = httpx2.put(
        f"{live_server}/observability/policy",
        json={"allowed": ["nope"]},
        timeout=10,
    )
    assert response.status_code == 400
    assert "unknown tool" in response.json()["detail"]


def test_put_policy_round_trips_and_asks_for_a_restart(live_server) -> None:
    """The gateway reads its config at startup, so a write is not yet in force."""
    original = httpx2.get(f"{live_server}/observability/policy", timeout=10).json()
    allowed_before = [t["name"] for t in original["tools"] if t["allowed"]]

    try:
        response = httpx2.put(
            f"{live_server}/observability/policy",
            json={"allowed": ["get_company", "list_sectors"]},
            timeout=10,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["restart_required"] is True
        assert "Restart agentgateway" in body["message"]
        assert [t["name"] for t in body["tools"] if t["allowed"]] == [
            "get_company",
            "list_sectors",
        ]
    finally:
        httpx2.put(
            f"{live_server}/observability/policy",
            json={"allowed": allowed_before},
            timeout=10,
        )

    restored = httpx2.get(f"{live_server}/observability/policy", timeout=10).json()
    assert [t["name"] for t in restored["tools"] if t["allowed"]] == allowed_before
