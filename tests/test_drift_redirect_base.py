"""Drift snapshots must resolve relative resources against the fetched page."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import drift_baseline  # noqa: E402
from parse_html import parse_html  # noqa: E402


@pytest.mark.parametrize(
    "final_url",
    ["https://example.com/docs/", "https://www.example.com/docs/", None],
)
def test_snapshot_uses_final_url_for_relative_links(monkeypatch, final_url):
    requested = "https://example.com/old"
    html = '<html><body><a href="guide">Guide</a><img src="hero.png"></body></html>'

    def run(command, **kwargs):
        if command[1].endswith("fetch_page.py"):
            Path(command[command.index("--output") + 1]).write_text(html, encoding="utf-8")
            metadata = f"URL: {final_url}\n" if final_url else ""
            return SimpleNamespace(returncode=0, stdout="", stderr=metadata + "Status: 200\n")
        assert command[1].endswith("parse_html.py")
        base_url = command[command.index("--url") + 1]
        parsed = parse_html(Path(command[2]).read_text(encoding="utf-8"), base_url)
        return SimpleNamespace(returncode=0, stdout=json.dumps(parsed), stderr="")

    monkeypatch.setattr(drift_baseline.subprocess, "run", run)
    result = drift_baseline.fetch_page_data(requested)
    expected = final_url or requested
    expected_prefix = expected.rsplit("/", 1)[0] + "/"
    assert result["error"] is None
    assert result["parsed"]["links"]["internal"][0]["href"] == expected_prefix + "guide"
    assert result["parsed"]["images"][0]["src"] == expected_prefix + "hero.png"
