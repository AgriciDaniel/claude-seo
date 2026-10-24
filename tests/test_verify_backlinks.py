"""
Tests for link matching and status handling in scripts/verify_backlinks.py.

Network calls are mocked: `safe_requests_head` and `fetch_page` are replaced
with fakes so each test controls the HEAD status, the GET status, headers and
the HTML. The real `parse_html` runs on the fake HTML.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_backlinks  # noqa: E402

SOURCE = "https://blog.example.org/post"
TARGET = "https://target.example/tool"


class FakeHeadResponse:
    def __init__(self, status_code, url=SOURCE, redirected=False):
        self.status_code = status_code
        self.url = url
        self.history = [object()] if redirected else []


def _page(html, status_code=200, headers=None, url=SOURCE):
    return {
        "url": url,
        "status_code": status_code,
        "content": html,
        "headers": headers or {},
        "redirect_chain": [],
        "error": None,
    }


@pytest.fixture
def fake_network(monkeypatch):
    """Install fakes; tests set `state["head"]` and `state["page"]`."""
    state = {"head": FakeHeadResponse(200), "page": None, "get_calls": 0}

    def fake_head(url, **kwargs):
        head = state["head"]
        if isinstance(head, Exception):
            raise head
        return head

    def fake_fetch(url, **kwargs):
        state["get_calls"] += 1
        return state["page"]

    monkeypatch.setattr(verify_backlinks, "DOMAIN_DELAY", 0)
    monkeypatch.setattr(verify_backlinks, "validate_url", lambda url: True)
    monkeypatch.setattr(verify_backlinks, "safe_requests_head", fake_head)
    monkeypatch.setattr(verify_backlinks, "fetch_page", fake_fetch)
    return state


def _html(body, head=""):
    return f"<html><head>{head}</head><body>{body}</body></html>"


def test_exact_link_wins_over_earlier_same_domain_link(fake_network):
    fake_network["page"] = _page(_html(
        '<nav><a href="https://target.example/" rel="nofollow">Home</a></nav>'
        '<p>Try <a href="https://target.example/tool">the tool</a>.</p>'
    ))
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "verified"
    assert result["match_type"] == "exact_url"
    assert result["anchor_text"] == "the tool"
    assert result["rel_attributes"] == ["follow"]


def test_domain_match_still_reported_when_no_exact_link(fake_network):
    fake_network["page"] = _page(_html(
        '<a href="https://sub.target.example/x">sub</a>'
        '<a href="https://target.example/other" rel="sponsored">other</a>'
    ))
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["match_type"] == "domain_match"
    assert result["anchor_text"] == "other"
    assert result["rel_attributes"] == ["sponsored"]


def test_link_without_rel_and_no_page_directive_is_not_page_nofollow(fake_network):
    fake_network["page"] = _page(_html('<a href="https://target.example/tool">t</a>'))
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["rel_attributes"] == ["follow"]
    assert result["page_nofollow"] is False


@pytest.mark.parametrize("content", ["noindex, nofollow", "NOFOLLOW", "none"])
def test_meta_robots_nofollow_is_reported(fake_network, content):
    fake_network["page"] = _page(_html(
        '<a href="https://target.example/tool">t</a>',
        head=f'<meta name="robots" content="{content}">',
    ))
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "verified"
    assert result["page_nofollow"] is True
    assert result["rel_attributes"] == ["follow"]


@pytest.mark.parametrize("value", ["nofollow", "noarchive, NoFollow", "none"])
def test_x_robots_tag_nofollow_is_reported(fake_network, value):
    fake_network["page"] = _page(
        _html('<a href="https://target.example/tool">t</a>'),
        headers={"x-robots-tag": value},
    )
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["page_nofollow"] is True


@pytest.mark.parametrize("value", ["otherbot: nofollow", "otherbot: noindex, nofollow"])
def test_x_robots_tag_scoped_to_another_crawler_is_ignored(fake_network, value):
    fake_network["page"] = _page(
        _html('<a href="https://target.example/tool">t</a>'),
        headers={"X-Robots-Tag": value},
    )
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["page_nofollow"] is False


def test_x_robots_tag_valued_directive_is_not_a_crawler_scope(fake_network):
    fake_network["page"] = _page(
        _html('<a href="https://target.example/tool">t</a>'),
        headers={"X-Robots-Tag": "max-snippet: 50, nofollow"},
    )
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["page_nofollow"] is True


def test_x_robots_tag_date_with_commas_is_not_a_crawler_scope(fake_network):
    fake_network["page"] = _page(
        _html('<a href="https://target.example/tool">t</a>'),
        headers={"X-Robots-Tag": "unavailable_after: Wed, 03 Nov 2026 15:00:00 GMT, nofollow"},
    )
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["page_nofollow"] is True


@pytest.mark.parametrize("head_status", [403, 405, 501])
def test_head_rejected_falls_back_to_get(fake_network, head_status):
    fake_network["head"] = FakeHeadResponse(head_status)
    fake_network["page"] = _page(_html('<a href="https://target.example/tool">t</a>'))
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "verified"
    assert result["http_status"] == 200
    assert fake_network["get_calls"] == 1


def test_head_request_error_falls_back_to_get(fake_network):
    fake_network["head"] = verify_backlinks.requests.exceptions.ConnectionError("reset")
    fake_network["page"] = _page(_html('<a href="https://target.example/tool">t</a>'))
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "verified"


def test_head_ssrf_block_does_not_fall_back_to_get(fake_network):
    fake_network["head"] = verify_backlinks.URLSafetyError("private address")
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "error"
    assert "SSRF" in result["error"]
    assert fake_network["get_calls"] == 0


def test_head_404_is_lost_without_get(fake_network):
    fake_network["head"] = FakeHeadResponse(404)
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "lost"
    assert fake_network["get_calls"] == 0


def test_get_fallback_404_is_lost(fake_network):
    fake_network["head"] = FakeHeadResponse(405)
    fake_network["page"] = _page("Not found", status_code=404)
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "lost"
    assert result["http_status"] == 404


def test_get_fallback_still_blocked_is_error(fake_network):
    fake_network["head"] = FakeHeadResponse(403)
    fake_network["page"] = _page(_html("Access denied"), status_code=403)
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "error"
    assert result["http_status"] == 403
    assert result["target_found"] is False


def test_head_only_falls_back_to_get_for_existence(fake_network):
    fake_network["head"] = FakeHeadResponse(405)
    fake_network["page"] = _page(_html("hello"))
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET, head_only=True)
    assert result["status"] == "exists"
    assert result["http_status"] == 200


def test_head_only_redirect_is_moved(fake_network):
    fake_network["head"] = FakeHeadResponse(
        200, url="https://blog.example.org/new-post", redirected=True
    )
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET, head_only=True)
    assert result["status"] == "moved"
    assert result["redirect_url"] == "https://blog.example.org/new-post"


def test_head_only_url_normalization_alone_is_not_moved(fake_network):
    fake_network["head"] = FakeHeadResponse(200, url=SOURCE + "/")
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET, head_only=True)
    assert result["status"] == "exists"
    assert result["redirect_url"] is None


def test_full_check_on_redirected_page_reports_redirect_url(fake_network):
    final = "https://blog.example.org/new-post"
    fake_network["head"] = FakeHeadResponse(200, url=final, redirected=True)
    fake_network["page"] = _page(_html('<a href="https://target.example/tool">t</a>'), url=final)
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "verified"
    assert result["redirect_url"] == final
