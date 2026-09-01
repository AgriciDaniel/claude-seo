"""Contract checks for the optional Creaitor GEO MCP extension."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "extensions/creaitor/skills/seo-creaitor/SKILL.md"
MANIFEST = SKILL.parent / "references/mcp-tools.json"
EXPECTED_TOOLS = {
    "list_domains": "geo:read",
    "list_queries": "geo:read",
    "create_query": "geo:write",
    "update_query": "geo:write",
    "run_query": "geo:execute",
    "get_results": "geo:read",
    "get_analytics": "geo:read",
    "get_citations": "geo:read",
    "get_sources": "geo:read",
    "export_citations": "geo:execute",
    "list_audits": "geo:read",
    "run_audit": "geo:execute",
    "get_audit": "geo:read",
    "list_recommendations": "geo:read",
    "update_recommendation": "geo:write",
    "list_competitors": "geo:read",
    "get_health_score": "geo:read",
    "generate_llms_txt": "geo:execute",
}


def _resolver_module():
    path = ROOT / "extensions/creaitor/scripts/resolve_domain.py"
    spec = importlib.util.spec_from_file_location("creaitor_resolver", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_vendor_tool_manifest_is_complete_and_pins_production() -> None:
    manifest = _manifest()
    assert manifest["endpoint"] == "https://app.creaitor.ai/api/v2/mcp"
    assert manifest["tools"] == EXPECTED_TOOLS
    assert "geo-api-v2.md" in manifest["source"]


def test_skill_routing_uses_only_manifest_tools_with_correct_abilities() -> None:
    text = SKILL.read_text(encoding="utf-8")
    routing = text.split("## Routing", 1)[1].split("## Execution rules", 1)[0]
    seen = set()
    for line in routing.splitlines():
        if not line.startswith("| `/seo creaitor"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        assert len(cells) == 3, f"malformed routing row: {line}"
        tools = re.findall(r"`([a-z][a-z0-9_]*)`", cells[1])
        ability = cells[2].strip("`")
        assert tools, f"routing row has no MCP tool: {line}"
        for tool in tools:
            assert tool in EXPECTED_TOOLS, f"unknown Creaitor MCP tool: {tool}"
            assert EXPECTED_TOOLS[tool] == ability, (
                f"{tool} requires {EXPECTED_TOOLS[tool]}, row declares {ability}"
            )
            seen.add(tool)
    assert seen <= set(EXPECTED_TOOLS)
    assert {"list_domains", "get_analytics", "run_audit", "generate_llms_txt"} <= seen


def test_installers_pin_production_endpoint_without_override() -> None:
    for rel in ("extensions/creaitor/install.sh", "extensions/creaitor/install.ps1"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "https://app.creaitor.ai/api/v2/mcp" in text
        assert "CREAITOR_MCP_URL" not in text


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://WWW.Example.com/path?q=1", "example.com"),
        ("https://example.com/?q=a%20b", "example.com"),
        ("https://bücher.example./", "xn--bcher-kva.example"),
        ("http://example.com:80/", "example.com"),
        ("https://example.com:443/", "example.com"),
    ],
)
def test_domain_resolver_normalizes_safe_http_urls(value: str, expected: str) -> None:
    assert _resolver_module().normalize(value, require_absolute=True) == expected


@pytest.mark.parametrize(
    "value",
    [
        "example.com",
        "ftp://example.com",
        "https://good.example@evil.example",
        "https://127.0.0.1",
        "https://[::1]",
        "https://example.com:8443",
        "https://example%2ecom",
        "https://example.com%2f@evil.example",
    ],
)
def test_domain_resolver_rejects_ambiguous_or_dangerous_urls(value: str) -> None:
    with pytest.raises(ValueError):
        _resolver_module().normalize(value, require_absolute=True)


@pytest.mark.skipif(not os.environ.get("CREAITOR_GEO_TOKEN"), reason="no live Creaitor token")
def test_live_mcp_tools_match_checked_in_manifest() -> None:
    """Optional authenticated drift check for maintainers/CI secret environments."""
    token = os.environ["CREAITOR_GEO_TOKEN"]
    endpoint = _manifest()["endpoint"]

    def call(method: str, params: dict | None = None) -> dict:
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {},
        }).encode()
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())

    call("initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "claude-seo-contract", "version": "1"},
    })
    result = call("tools/list")
    live = {tool["name"] for tool in result["result"]["tools"]}
    assert live == set(EXPECTED_TOOLS)
