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


def _page(html, status_code=200, headers=None, url=SOURCE, redirect_chain=None):
    return {
        "url": url,
        "status_code": status_code,
        "content": html,
        "headers": headers or {},
        "redirect_chain": redirect_chain or [],
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


@pytest.mark.parametrize("head_status", [403, 404, 405, 410, 501])
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


def test_head_blocked_redirect_target_does_not_fall_back_to_get(fake_network):
    fake_network["head"] = verify_backlinks.requests.exceptions.ConnectionError(
        "Failed to resolve 'internal' (url_safety: refused to resolve 'internal' "
        "to non-public IP 10.0.0.5)"
    )
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "error"
    assert "SSRF" in result["error"]
    assert fake_network["get_calls"] == 0


@pytest.mark.parametrize("head_only", [False, True])
@pytest.mark.parametrize("head_status", [404, 405, 410, 501])
@pytest.mark.parametrize("get_status", [404, 410])
def test_lost_only_after_get_confirms(fake_network, head_status, get_status, head_only):
    fake_network["head"] = FakeHeadResponse(head_status)
    fake_network["page"] = _page("Gone", status_code=get_status)
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET, head_only=head_only)
    assert result["status"] == "lost"
    assert result["http_status"] == get_status
    assert fake_network["get_calls"] == 1


@pytest.mark.parametrize("head_only", [False, True])
@pytest.mark.parametrize("get_status", [500, 503])
def test_get_5xx_is_server_error_not_lost(fake_network, get_status, head_only):
    fake_network["head"] = FakeHeadResponse(404)
    fake_network["page"] = _page("Unavailable", status_code=get_status)
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET, head_only=head_only)
    assert result["status"] == "server_error"
    assert result["http_status"] == get_status
    assert str(get_status) in result["error"]


@pytest.mark.parametrize("get_status", [403, 429])
def test_get_refused_is_error_with_note(fake_network, get_status):
    fake_network["head"] = FakeHeadResponse(405)
    fake_network["page"] = _page("Denied", status_code=get_status)
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET)
    assert result["status"] == "error"
    assert "refused the checker" in result["error"]


def test_server_error_is_counted_in_summary(fake_network):
    fake_network["page"] = _page("Unavailable", status_code=502)
    summary = verify_backlinks.verify_backlinks(TARGET, [{"source_url": SOURCE}])["data"]["summary"]
    assert summary["server_error"] == 1
    assert summary["error"] == 0
    assert summary["lost"] == 0


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


@pytest.mark.parametrize("head_status", [404, 405, 410, 501])
def test_head_only_get_confirms_existence_without_parsing(fake_network, monkeypatch, head_status):
    def no_parse(*args, **kwargs):
        raise AssertionError("head-only mode must not parse the body")

    monkeypatch.setattr(verify_backlinks, "parse_html", no_parse)
    fake_network["head"] = FakeHeadResponse(head_status)
    fake_network["page"] = _page(_html("hello"))
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET, head_only=True)
    assert result["status"] == "exists"
    assert result["http_status"] == 200
    assert fake_network["get_calls"] == 1


@pytest.mark.parametrize("source, final", [
    ("https://blog.example.org/post", "https://blog.example.org/new-post"),  # path change
    ("https://blog.example.org/post", "https://news.example.org/post"),  # host change
    ("https://blog.example.org/post", "https://blog.example.net/post"),  # host change
])
def test_head_only_redirect_to_other_host_or_path_is_moved(fake_network, source, final):
    fake_network["head"] = FakeHeadResponse(200, url=final, redirected=True)
    result = verify_backlinks.verify_single_backlink(source, TARGET, head_only=True)
    assert result["status"] == "moved"
    assert result["redirect_url"] == final


@pytest.mark.parametrize("source, final", [
    ("http://blog.example.org/post", "https://blog.example.org/post"),  # http to https
    ("https://example.org/post", "https://www.example.org/post"),  # add www
    ("https://www.example.org/post", "https://example.org/post"),  # drop www
    ("http://Example.org/post", "https://WWW.example.org/post/"),  # case, trailing slash
    ("http://example.org", "https://www.example.org/"),  # bare host
])
def test_head_only_scheme_or_www_redirect_is_exists(fake_network, source, final):
    fake_network["head"] = FakeHeadResponse(200, url=final, redirected=True)
    result = verify_backlinks.verify_single_backlink(source, TARGET, head_only=True)
    assert result["status"] == "exists"
    assert result["redirect_url"] == final


def test_head_only_get_fallback_redirect_uses_same_verdict(fake_network):
    fake_network["head"] = FakeHeadResponse(405)
    fake_network["page"] = _page(
        _html("hello"), url="https://www.blog.example.org/post", redirect_chain=[SOURCE]
    )
    result = verify_backlinks.verify_single_backlink(SOURCE, TARGET, head_only=True)
    assert result["status"] == "exists"
    assert result["redirect_url"] == "https://www.blog.example.org/post"


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


def test_relative_link_resolves_against_final_url_after_redirect(fake_network):
    source = "https://old.example.org/post"
    final = "https://target.example/blog/post"
    fake_network["head"] = FakeHeadResponse(200, url=final, redirected=True)
    fake_network["page"] = _page(
        _html('<p>Try <a href="/tool">the tool</a>.</p>'), url=final, redirect_chain=[source]
    )
    result = verify_backlinks.verify_single_backlink(source, TARGET)
    assert result["status"] == "verified"
    assert result["match_type"] == "exact_url"
    assert result["anchor_text"] == "the tool"
    assert result["redirect_url"] == final
