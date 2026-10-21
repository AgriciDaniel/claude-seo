"""CLI output contracts for raw and rendered page fetching.

``--json`` routes both the raw (``--render never``) and rendered
(``--render auto``/``--render always``) fetch paths through
``render_page._json_summary`` so the emitted JSON has one shared key
set and one shared ``--max-text`` truncation contract, regardless of
which path produced the fetch. The raw path is mapped onto the
render_page result shape by ``fetch_page._as_render_result`` first.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("requests")
import fetch_page  # noqa: E402
import render_page  # noqa: E402

_CONTENT = '<p>Café "hello"\n世界</p>' + "x" * 12000

RAW_RESULT = {
    "url": "https://example.com/final",
    "status_code": 200,
    "content": _CONTENT,
    "headers": {"Content-Type": "text/html; charset=utf-8"},
    "redirect_chain": ["https://example.com"],
    "redirect_details": [{"url": "https://example.com", "status_code": 301}],
    "error": None,
}

# A complete render_page() result contract (every key render_page() promises
# in its module docstring), so the "rendered" fixture branch matches the raw
# branch's key set once both go through fetch_page._as_render_result /
# render_page._json_summary.
RENDERED_RESULT = {
    "url": "https://example.com/final",
    "status_code": 200,
    "content": _CONTENT,
    "raw_content": _CONTENT,
    "is_spa": True,
    "extracted_text": "Cafe hello",
    "publication_date": None,
    "accessibility_tree": None,
    "accessibility_error": None,
    "accessibility_partial": False,
    "headers": {"Content-Type": "text/html; charset=utf-8"},
    "redirect_chain": [{"url": "https://example.com", "status_code": 301}],
    "console_errors": [],
    "render_diagnostics": [],
    "render_engine": "playwright-chromium",
    "render_ms": 12.5,
    "mode_used": "rendered",
    "too_large": False,
    "error": None,
}


@pytest.fixture(params=["never", "auto", "always"])
def fetch_result(request, monkeypatch):
    """Mock the raw or rendered fetcher (no network, no browser)."""
    if request.param == "never":
        result = dict(RAW_RESULT)
        monkeypatch.setattr(fetch_page, "fetch_page", lambda *a, **kw: dict(result))
    else:
        result = dict(RENDERED_RESULT)
        monkeypatch.setattr(render_page, "render_page", lambda *a, **kw: dict(result))
    monkeypatch.setattr(
        sys, "argv", ["fetch_page.py", "https://example.com", "--render", request.param]
    )
    return result


def _expected_json(raw_source: dict, *, mode: str, output_written: bool, max_text: int = 0) -> dict:
    """Compute the exact JSON the CLI must emit for a given mocked result."""
    normalized = (
        raw_source if mode != "never" else fetch_page._as_render_result(raw_source, mode_used="raw")
    )
    summary = render_page._json_summary(normalized, max_text=max_text)
    summary["output_written"] = output_written
    return json.loads(json.dumps(summary, default=str))


@pytest.mark.parametrize("save_html", [False, True])
def test_json_preserves_full_result(fetch_result, save_html, tmp_path, capsys, monkeypatch):
    sys.argv += ["--json"]
    output = tmp_path / "page.html"
    if save_html:
        sys.argv += ["--output", str(output)]
    mode = [a for a in sys.argv if a in ("never", "auto", "always")][-1]
    with pytest.raises(SystemExit) as exc:
        fetch_page.main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == _expected_json(
        fetch_result, mode=mode, output_written=save_html
    )
    assert captured.err == ""
    assert output.exists() == save_html
    if save_html:
        assert output.read_text(encoding="utf-8") == fetch_result["content"]


def test_json_output_keys_match_between_raw_and_rendered(monkeypatch, capsys):
    """The headline contract: raw and rendered --json share one key set."""
    monkeypatch.setattr(fetch_page, "fetch_page", lambda *a, **kw: dict(RAW_RESULT))
    monkeypatch.setattr(sys, "argv", ["fetch_page.py", "https://example.com", "--json"])
    with pytest.raises(SystemExit):
        fetch_page.main()
    raw_keys = set(json.loads(capsys.readouterr().out).keys())

    monkeypatch.setattr(render_page, "render_page", lambda *a, **kw: dict(RENDERED_RESULT))
    monkeypatch.setattr(
        sys, "argv", ["fetch_page.py", "https://example.com", "--render", "always", "--json"]
    )
    with pytest.raises(SystemExit):
        fetch_page.main()
    rendered_keys = set(json.loads(capsys.readouterr().out).keys())

    assert raw_keys == rendered_keys


@pytest.mark.parametrize("mode", ["never", "always"])
def test_json_max_text_truncates_content_fields(mode, monkeypatch, capsys):
    if mode == "never":
        monkeypatch.setattr(fetch_page, "fetch_page", lambda *a, **kw: dict(RAW_RESULT))
    else:
        monkeypatch.setattr(render_page, "render_page", lambda *a, **kw: dict(RENDERED_RESULT))
    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch_page.py", "https://example.com", "--render", mode, "--json", "--max-text", "10"],
    )
    with pytest.raises(SystemExit) as exc:
        fetch_page.main()
    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["content"] == _CONTENT[:10]
    assert payload["truncation"]["fields"]["content"]["truncated"] is True
    assert payload["truncation"]["fields"]["content"]["original_chars"] == len(_CONTENT)


def test_json_fetch_error_preserves_existing_file(fetch_result, tmp_path, capsys):
    fetch_result.update(error="Request timed out", content=None, status_code=None)
    output = tmp_path / "page.html"
    output.write_text("existing", encoding="utf-8")
    sys.argv += ["--json", "--output", str(output)]
    mode = [a for a in sys.argv if a in ("never", "auto", "always")][-1]
    with pytest.raises(SystemExit) as exc:
        fetch_page.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == _expected_json(fetch_result, mode=mode, output_written=False)
    assert captured.err == ""
    assert output.read_text(encoding="utf-8") == "existing"


def test_json_http_error_status_is_still_a_completed_fetch(fetch_result, capsys):
    fetch_result["status_code"] = 404
    sys.argv += ["--json"]
    with pytest.raises(SystemExit) as exc:
        fetch_page.main()
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status_code"] == 404


@pytest.mark.parametrize("save_html", [False, True])
def test_text_output_is_unchanged(fetch_result, save_html, tmp_path, capsys):
    output = tmp_path / "page.html"
    if save_html:
        sys.argv += ["--output", str(output)]
    fetch_page.main()
    captured = capsys.readouterr()
    expected = f"Saved to {output}" if save_html else fetch_result["content"]
    assert captured.out == expected + "\n"
    assert "URL: https://example.com/final" in captured.err
    assert "Status: 200" in captured.err
