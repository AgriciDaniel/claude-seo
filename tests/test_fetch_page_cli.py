"""CLI output contracts for raw and rendered page fetching."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_page  # noqa: E402
import render_page  # noqa: E402


@pytest.fixture(params=["never", "auto", "always"])
def fetch_result(request, monkeypatch):
    result = {
        "url": "https://example.com/final",
        "status_code": 200,
        "content": '<p>Café "hello"\n世界</p>' + "x" * 12000,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "redirect_chain": ["https://example.com"],
        "redirect_details": [{"url": "https://example.com", "status_code": 301}],
        "error": None,
    }
    if request.param == "never":
        monkeypatch.setattr(fetch_page, "fetch_page", lambda *a, **kw: result)
    else:
        result.update(mode_used="rendered", is_spa=True, render_ms=12.5)
        monkeypatch.setattr(render_page, "render_page", lambda *a, **kw: result)
    monkeypatch.setattr(sys, "argv", ["fetch_page.py", "https://example.com", "--render", request.param])
    return result


@pytest.mark.parametrize("save_html", [False, True])
def test_json_preserves_full_result(fetch_result, save_html, tmp_path, capsys):
    sys.argv += ["--json"]
    output = tmp_path / "page.html"
    if save_html:
        sys.argv += ["--output", str(output)]
    with pytest.raises(SystemExit) as exc:
        fetch_page.main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {**fetch_result, "output_written": save_html}
    assert captured.err == ""
    assert output.exists() == save_html
    if save_html:
        assert output.read_text(encoding="utf-8") == fetch_result["content"]


def test_json_fetch_error_preserves_existing_file(fetch_result, tmp_path, capsys):
    fetch_result.update(error="Request timed out", content=None, status_code=None)
    output = tmp_path / "page.html"
    output.write_text("existing", encoding="utf-8")
    sys.argv += ["--json", "--output", str(output)]
    with pytest.raises(SystemExit) as exc:
        fetch_page.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {**fetch_result, "output_written": False}
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
