"""SPECS REG-1, REG-2 — the extensibility contract."""

from __future__ import annotations

import shutil
import sys
import textwrap
from pathlib import Path

from core.registry import ModuleSpec, discover_modules, register_all
from mcp_server.server import build_server


def test_all_modules_are_discovered() -> None:
    """REG-1.1."""
    names = [s.name for s in discover_modules()]
    assert names == ["listings", "filings", "analytics", "observability"]


def test_discovery_order_is_deterministic() -> None:
    """REG-1.2 — sorted by (priority, name); tools/list ordering depends on it."""
    first = [s.name for s in discover_modules()]
    second = [s.name for s in discover_modules()]
    assert first == second
    priorities = [s.priority for s in discover_modules()]
    assert priorities == sorted(priorities)


def test_module_capability_flags() -> None:
    by_name = {s.name: s for s in discover_modules()}
    assert by_name["listings"].router is not None
    assert by_name["listings"].register_tools is not None
    assert by_name["listings"].register_resources is not None
    assert by_name["analytics"].router is None  # capability-only module
    assert by_name["analytics"].register_prompts is not None
    assert by_name["observability"].register_tools is None  # router-only module


def test_dropping_in_a_module_wires_it_up(tmp_path: Path) -> None:
    """REG-1.3 / REG-2.1 — zero-touch: no shared file is edited.

    A package is written into modules/ at test time and must appear in the tool
    and resource surface with no other change. If this ever fails, the registry
    contract is broken — fix the registry, not the module.
    """
    package = Path(__file__).resolve().parent.parent / "modules" / "_probe_module"
    package.mkdir(exist_ok=True)
    (package / "__init__.py").write_text(
        textwrap.dedent(
            '''
            """Temporary module used by the registry test."""
            from core.registry import ModuleSpec


            def register_tools(mcp):
                @mcp.tool()
                def probe_tool() -> dict:
                    """Probe."""
                    return {"ok": True}


            def register_resources(mcp):
                @mcp.resource("probe://thing", name="probe")
                def probe_resource() -> dict:
                    """Probe resource."""
                    return {"ok": True}


            MODULE = ModuleSpec(
                name="_probe_module",
                description="probe",
                register_tools=register_tools,
                register_resources=register_resources,
                priority=999,
            )
            '''
        ).strip()
        + "\n"
    )
    try:
        for name in [m for m in sys.modules if m.startswith("modules")]:
            if name.endswith("_probe_module"):
                del sys.modules[name]
        specs = discover_modules()
        assert "_probe_module" in [s.name for s in specs]

        server = build_server()
        assert "probe_tool" in {t.name for t in server._tool_manager.list_tools()}
    finally:
        shutil.rmtree(package, ignore_errors=True)
        sys.modules.pop("modules._probe_module", None)


def test_register_all_counts_hooks() -> None:
    """REG-2 — every hook type is wired by the same mechanism."""
    counts = register_all(build_server())
    assert counts == {"tools": 3, "resources": 2, "prompts": 1}


def test_module_spec_defaults_are_all_optional() -> None:
    spec = ModuleSpec(name="minimal")
    assert spec.router is None
    assert spec.register_tools is None
    assert spec.register_resources is None
    assert spec.register_prompts is None
    assert spec.seed is None
