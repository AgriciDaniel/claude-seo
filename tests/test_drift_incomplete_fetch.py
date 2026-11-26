"""Drift must not persist or compare the prefix of a size-limited fetch."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import drift_baseline as capture  # noqa: E402
import drift_compare as compare  # noqa: E402
from fetch_page import _as_render_result  # noqa: E402
from parse_html import parse_html  # noqa: E402
from url_safety import read_bounded  # noqa: E402

URL = "https://example.com/old"
FINAL = "https://example.com/docs/"
HTML = '<title>Complete page</title><h1>Complete heading</h1><a href="guide">Guide</a>'


@pytest.fixture
def handoff(monkeypatch, tmp_path):
    state = {
        "html": HTML,
        "metadata": {"url": FINAL, "status_code": 200, "too_large": False,
                     "output_written": True, "error": None},
        "returncode": 0,
        "stderr": f"URL: {URL}\nStatus: 200\n",
        "calls": [], "paths": [],
    }
    monkeypatch.setattr(capture, "DB_DIR", str(tmp_path / "db"))
    monkeypatch.setattr(capture, "DB_PATH", str(tmp_path / "db/baselines.db"))

    def run(command, **kwargs):
        state["calls"].append(command)
        if command[1].endswith("fetch_page.py"):
            path = Path(command[command.index("--output") + 1])
            state["paths"].append(path)
            metadata = state["metadata"]
            if not isinstance(metadata, dict) or metadata.get("output_written"):
                path.write_text(state["html"], encoding="utf-8")
            return SimpleNamespace(
                returncode=state["returncode"], stderr=state["stderr"],
                stdout=state.get("stdout", json.dumps(metadata)),
            )
        assert command[1].endswith("parse_html.py")
        html = Path(command[2]).read_text(encoding="utf-8")
        base = command[command.index("--url") + 1]
        return SimpleNamespace(returncode=0, stdout=json.dumps(parse_html(html, base)), stderr="")

    monkeypatch.setattr(capture.subprocess, "run", run)
    return state


def capped_response(state):
    prefix = b"<title>Complete page</title>"
    response = SimpleNamespace(iter_content=lambda chunk_size: iter([prefix, HTML.encode()]))
    raw, too_large = read_bounded(response, len(prefix))
    assert raw == prefix and too_large
    state["html"] = raw.decode()
    state["metadata"] = {
        **_as_render_result({"url": FINAL, "status_code": 200, "content": raw.decode(),
                             "too_large": too_large, "error": None}, mode_used="raw"),
        "output_written": True,
    }


def test_size_capped_producer_response_is_rejected_before_html_parsing(handoff):
    capped_response(handoff)
    result = capture.fetch_page_data(URL)
    assert result["error"] and "size" in result["error"].lower()
    assert result["html"] is None and result["parsed"] is None
    assert len(handoff["calls"]) == 1
    assert all(not path.exists() for path in handoff["paths"])


def test_size_capped_response_is_not_saved_as_a_good_baseline(handoff):
    capped_response(handoff)
    result = capture.capture_baseline(URL, skip_cwv=True)
    assert result.get("error")
    with capture.init_db() as conn:
        assert conn.execute("SELECT count(*) FROM baselines").fetchone()[0] == 0


def test_size_capped_comparison_does_not_persist_false_removal_findings(handoff):
    baseline = capture.capture_baseline(URL, skip_cwv=True)
    assert baseline["status"] == "ok"
    capped_response(handoff)
    result = compare.run_comparison(URL, skip_cwv=True)
    assert result.get("error")
    with capture.init_db() as conn:
        assert conn.execute("SELECT count(*) FROM comparisons").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM baselines").fetchone()[0] == 1


@pytest.mark.parametrize("status", [203, 404, None])
def test_complete_response_uses_json_status_and_final_url(handoff, status):
    handoff["metadata"]["status_code"] = status
    result = capture.fetch_page_data(URL)
    assert result["error"] is None
    assert result["status_code"] == status
    assert result["html"] == HTML
    assert result["parsed"]["links"]["internal"][0]["href"] == FINAL + "guide"
    assert "--json" in handoff["calls"][0]
    assert all(not path.exists() for path in handoff["paths"])


def test_json_preview_truncation_does_not_mean_the_saved_html_is_incomplete(handoff):
    handoff["metadata"].update(
        content="<", raw_content="<",
        truncation={"limit": 1, "fields": {"content": {"truncated": True}}},
    )
    result = capture.fetch_page_data(URL)
    assert result["error"] is None
    assert result["html"] == HTML
    assert result["parsed"]["h1"] == ["Complete heading"]


@pytest.mark.parametrize("stdout", ["", "{broken", "[]", "null"])
def test_invalid_fetch_metadata_is_not_treated_as_a_complete_response(handoff, stdout):
    handoff["stdout"] = stdout
    result = capture.fetch_page_data(URL)
    assert result["error"]
    assert result["html"] is None and result["parsed"] is None
    assert len(handoff["calls"]) == 1
    assert all(not path.exists() for path in handoff["paths"])


@pytest.mark.parametrize("returncode", [0, 1])
def test_structured_fetch_error_is_preserved(handoff, returncode):
    handoff["metadata"]["error"] = "Fetch exceeded the wall-clock deadline"
    handoff["returncode"] = returncode
    handoff["stderr"] = ""
    result = capture.fetch_page_data(URL)
    assert "wall-clock deadline" in result["error"]
    assert result["parsed"] is None


def test_failed_fetch_without_json_keeps_its_stderr_error(handoff):
    handoff.update(returncode=1, stdout="", stderr="Fetch process failed")
    result = capture.fetch_page_data(URL)
    assert "Fetch process failed" in result["error"]
    assert result["parsed"] is None


@pytest.mark.parametrize("missing", ["too_large", "output_written"])
def test_missing_completeness_or_output_receipt_rejects_the_snapshot(handoff, missing):
    handoff["metadata"].pop(missing)
    result = capture.fetch_page_data(URL)
    assert result["error"]
    assert result["parsed"] is None
    assert len(handoff["calls"]) == 1
