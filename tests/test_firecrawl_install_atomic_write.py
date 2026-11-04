"""Static contract for the PowerShell installers' ~/.claude.json writes.

None of these .ps1 files can be executed in CI (no PowerShell on the
Linux/macOS runners that run the main suite; see
docs/WORKFLOW-public-private.md and the windows-smoke workflow for the
executed coverage). These tests assert the source text contains the
temp-then-move write pattern and the -Depth 100 serialisation depth needed
to round-trip an existing ~/.claude.json, for every PowerShell installer
that merges into it.

v2.3.0 established the pattern in extensions/firecrawl/install.ps1. v2.3.1
extended it to the three writers that were still non-atomic: dataforseo's
and ahrefs's installers (which merged the JSON in an embedded Python
script with no -Depth control) and firecrawl's uninstaller (which wrote
`ConvertTo-Json -Depth 10` straight to $McpConfigFile with no temp file).
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# rel path -> (config-path variable, temp-file variable)
WRITERS = {
    "extensions/firecrawl/install.ps1": ("$McpConfigFile", "$TempConfigFile"),
    "extensions/firecrawl/uninstall.ps1": ("$McpConfigFile", "$TempConfigFile"),
    "extensions/dataforseo/install.ps1": ("$McpConfigFile", "$TempConfigFile"),
    "extensions/ahrefs/install.ps1": ("$McpConfigJson", "$TempConfigJson"),
    "extensions/coupler/install.ps1": ("$McpConfigJson", "$TempConfigJson"),
}


@pytest.mark.parametrize("rel,variables", WRITERS.items())
def test_ps1_writes_mcp_config_atomically(rel: str, variables: tuple[str, str]) -> None:
    config_var, temp_var = variables
    text = (ROOT / rel).read_text(encoding="utf-8")

    assert temp_var in text, f"{rel}: missing temp-file variable {temp_var}"
    assert f"Move-Item -Path {temp_var} -Destination {config_var} -Force" in text, (
        f"{rel}: missing the atomic Move-Item swap"
    )
    # The final Set-Content must target the temp file, not the real config
    # path directly, so a crash mid-write cannot leave it truncated.
    assert f"[System.IO.File]::WriteAllText({temp_var}, $jsonText, (New-Object System.Text.UTF8Encoding $false))" in text, (
        f"{rel}: the temp file must be written without a BOM"
    )
    assert "Set-Content" not in text or f"Set-Content {config_var}" not in text
    if "-NotePropertyName mcpServers" in text:
        assert "[pscustomobject]@{}" in text, f"{rel}: mcpServers must be created as an object, not a hashtable"


@pytest.mark.parametrize("rel", WRITERS.keys())
def test_ps1_uses_depth_100(rel: str) -> None:
    text = (ROOT / rel).read_text(encoding="utf-8")

    assert "ConvertTo-Json -Depth 100" in text, f"{rel}: not serialising with -Depth 100"
    assert "ConvertTo-Json -Depth 10 " not in text, f"{rel}: still uses the shallower -Depth 10"
    assert "ConvertTo-Json -Depth 10\n" not in text, f"{rel}: still uses the shallower -Depth 10"


def test_dataforseo_and_ahrefs_no_longer_shell_out_to_python_for_the_merge() -> None:
    # Before v2.3.1 both installers piped a heredoc into `python -` to merge
    # the MCP entry, so the write's atomicity (and its -Depth control)
    # depended on hand-rolled `tempfile.mkstemp` + `os.replace` logic instead
    # of the same ConvertTo-Json/Move-Item pattern every other writer uses.
    for rel in ("extensions/dataforseo/install.ps1", "extensions/ahrefs/install.ps1"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "tempfile.mkstemp" not in text, f"{rel}: still merges via an embedded Python script"
        assert "| python -" not in text, f"{rel}: still pipes a heredoc into python"


def test_ahrefs_install_ps1_no_longer_requires_python() -> None:
    # The merge script was the only reason install.ps1 needed Python; the
    # native ConvertTo-Json merge needs only Node/npx.
    text = (ROOT / "extensions/ahrefs/install.ps1").read_text(encoding="utf-8")
    assert 'Test-Cmd python' not in text
    assert 'throw "Python 3 is required."' not in text
