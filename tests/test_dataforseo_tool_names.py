"""Every DataForSEO MCP tool a skill names must exist on the pinned server (#317).

tests/fixtures/dataforseo_mcp_2_8_10_tools.txt lists the tool names registered
by dataforseo-mcp-server@2.8.10 (each tool's getName() in the npm package,
extracted 2026-09-23). Skills that named tools the server does not have
(serp_google_images_live_advanced, dataforseo_backlinks_*, and
on_page_content_parsing_live) sent the model after tools that never exist.
Bump the fixture together with the installer pin.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "dataforseo_mcp_2_8_10_tools.txt"
PINNED = "dataforseo-mcp-server@2.8.10"
TOOL_RE = re.compile(
    r"`((?:serp|kw_data|keywords_data|dataforseo_labs|dataforseo_backlinks|backlinks|on_page|"
    r"domain_analytics|business_data|content_analysis|ai_optimization|ai_opt)_[a-z0-9_]*[a-z0-9])`"
)
# Cost-ledger keys and REST endpoints that are not MCP tools.
NOT_MCP = {"backlinks_auth"}


def _tools() -> set[str]:
    return set(FIXTURE.read_text(encoding="utf-8").split())


def test_fixture_matches_the_installer_pin() -> None:
    for rel in ("extensions/dataforseo/install.sh", "extensions/dataforseo/install.ps1"):
        assert PINNED in (ROOT / rel).read_text(encoding="utf-8"), rel
    assert len(_tools()) == 80


def test_every_referenced_mcp_tool_exists_on_the_pinned_server() -> None:
    tools = _tools()
    missing = []
    for path in [*ROOT.glob("skills/**/*.md"), *ROOT.glob("agents/*.md"),
                 *ROOT.glob("extensions/*/skills/**/*.md"), *ROOT.glob("extensions/*/agents/*.md")]:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name in TOOL_RE.findall(line):
                if name not in tools and name not in NOT_MCP:
                    missing.append(f"{path.relative_to(ROOT)}:{line_no}: {name}")
    assert not missing, "tools not on " + PINNED + ":\n" + "\n".join(missing)
