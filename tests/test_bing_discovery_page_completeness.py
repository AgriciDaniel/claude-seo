"""Reading the last discovery page does not read its preceding pages."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bing_webmaster as bing  # noqa: E402


def _service(monkeypatch, total_pages, empty=False):
    calls = []

    def request(endpoint, _key, params):
        calls.append((endpoint, dict(params)))
        if endpoint == "GetLinkCounts":
            data = {
                "Links": [] if empty else [{"Url": "https://example.com/target", "Count": 1}],
                "TotalPages": total_pages,
            }
        else:
            assert endpoint == "GetUrlLinks"
            data = {
                "Details": [{"Url": "https://ref.example/article", "AnchorText": "sample"}],
                "TotalPages": 1,
            }
        return {"status": "success", "data": {"d": data}, "error": None}

    monkeypatch.setattr(bing, "_bing_request", request)
    return calls


@pytest.mark.parametrize("page,total_pages", [(1, 2), (2, 3), (4, 5)])
def test_last_discovery_page_is_partial_even_if_details_finish(monkeypatch, page, total_pages):
    calls = _service(monkeypatch, total_pages)
    result = bing.get_link_details("https://example.com/", "fixture", page=page)
    assert result["status"] == "partial"
    assert result["data"]["complete"] is False
    assert result["data"]["count_page"] == page
    assert result["data"]["total_returned"] == 1
    assert result["data"]["warnings"]
    assert [(endpoint, params["page"]) for endpoint, params in calls] == [
        ("GetLinkCounts", page), ("GetUrlLinks", 0),
    ]


def test_empty_last_page_does_not_claim_the_site_has_no_links(monkeypatch):
    calls = _service(monkeypatch, 3, empty=True)
    result = bing.get_link_details("https://example.com/", "fixture", page=2)
    assert result["status"] == "partial"
    assert result["data"]["complete"] is False
    assert result["data"]["links"] == []
    assert len(calls) == 1


@pytest.mark.parametrize("page,total_pages,complete", [(0, 1, True), (0, 3, False), (1, 3, False)])
def test_single_page_and_earlier_page_controls(monkeypatch, page, total_pages, complete):
    _service(monkeypatch, total_pages)
    result = bing.get_link_details("https://example.com/", "fixture", page=page)
    assert result["data"]["complete"] is complete
    assert result["status"] == ("success" if complete else "partial")
    assert result["data"]["links"][0]["anchor_text"] == "sample"


def test_json_cli_preserves_last_page_partial_status(monkeypatch, capsys):
    _service(monkeypatch, 3)
    monkeypatch.setattr(bing, "validate_url", lambda value: True)
    monkeypatch.setattr(bing, "get_bing_api_key", lambda: "fixture")
    monkeypatch.setattr(sys, "argv", [
        "bing_webmaster.py", "links", "https://example.com/", "--page", "2", "--json",
    ])
    assert bing.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "partial"
    assert result["data"]["complete"] is False
