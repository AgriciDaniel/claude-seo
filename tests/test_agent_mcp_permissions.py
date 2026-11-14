"""MCP agent permission and fail-closed regressions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = (
    ROOT / "agents" / "seo-dataforseo.md",
    ROOT / "extensions" / "dataforseo" / "agents" / "seo-dataforseo.md",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dataforseo_agent_mirrors_allow_only_sanctioned_mcp_path():
    for path in AGENTS:
        text = _text(path)
        frontmatter = text.split("---", 2)[1]
        tools_line = next(line for line in frontmatter.splitlines() if line.startswith("tools:"))
        assert "mcp__dataforseo__*" in tools_line
        assert "Bash" not in tools_line


def test_dataforseo_agent_mirrors_fail_closed_without_mcp():
    required = (
        "fail closed",
        "Never inspect credential or",
        "never bypass MCP with curl, raw HTTP, or another client",
    )
    for path in AGENTS:
        text = _text(path)
        for phrase in required:
            assert phrase in text


def test_dataforseo_agent_bodies_stay_mirrored():
    public_body = _text(AGENTS[0]).split("---", 2)[2]
    extension_body = _text(AGENTS[1]).split("---", 2)[2]
    assert public_body == extension_body


def test_dataforseo_installers_use_matching_mcp_server_name():
    # install.sh still merges the entry with a Python dict subscript;
    # install.ps1 merges it natively with Add-Member (v2.3.1, atomic
    # ConvertTo-Json write). Either way the server must be registered as
    # exactly "dataforseo" to match the agents' `mcp__dataforseo__*` grant.
    assert "['dataforseo']" in _text(ROOT / "extensions/dataforseo/install.sh")
    assert "-NotePropertyName 'dataforseo'" in _text(ROOT / "extensions/dataforseo/install.ps1")


def _tools_line(path: Path) -> str:
    frontmatter = _text(path).split("---", 2)[1]
    return next(line for line in frontmatter.splitlines() if line.startswith("tools:"))


def test_maps_agent_keeps_bash_and_mcp_separate():
    # #459 bug 6: seo-maps has Bash and reads untrusted pages, so it gets no
    # MCP grant. It must say so instead of probing a tool it cannot call.
    path = ROOT / "agents" / "seo-maps.md"
    tools_line = _tools_line(path)
    assert "Bash" in tools_line
    assert "mcp__" not in tools_line
    text = _text(path)
    assert "you have no MCP tools" in text
    assert "try `business_data_business_listings_search`" not in text
    assert "Never reach DataForSEO with curl, raw HTTP, or another client" in text
    assert "Capability tier used" in text


def test_hub_passes_paid_maps_data_to_the_maps_agent():
    hub = _text(ROOT / "skills" / "seo" / "SKILL.md")
    assert "through the seo-dataforseo agent or your own DataForSEO MCP tools" in hub
    assert "pass that data in the seo-maps prompt" in hub
    assert "must say which tier was used" in hub


def test_posthog_agent_is_read_only_and_names_both_tool_spellings():
    path = ROOT / "extensions" / "posthog" / "agents" / "seo-posthog.md"
    tools_line = _tools_line(path)
    assert "mcp__PostHog__exec" in tools_line and "mcp__posthog__exec" in tools_line
    assert "Bash" not in tools_line
    text = _text(path)
    assert "Read-only, with no exceptions." in text
    assert "never send a query that is not" in text
    # The installer registers the server in lowercase, so every place that
    # names the tool must accept that spelling too.
    assert "mcp add --transport http posthog " in _text(ROOT / "extensions/posthog/install.sh")
    for rel in ("skills/seo/SKILL.md", "extensions/posthog/skills/seo-posthog/SKILL.md",
                "extensions/posthog/docs/POSTHOG-SETUP.md"):
        doc = _text(ROOT / rel)
        assert "mcp__posthog__exec" in doc and "mcp__PostHog__exec" in doc, rel


def test_posthog_docs_recommend_read_only_access():
    setup = _text(ROOT / "extensions/posthog/docs/POSTHOG-SETUP.md")
    skill = _text(ROOT / "extensions/posthog/skills/seo-posthog/SKILL.md")
    assert "Use read-only access." in setup
    security = skill.split("## Security", 1)[1]
    assert "read-only PostHog login or API key" in security
