"""Tests for the seo-agentic scripts.

Coverage:
    scripts/lighthouse_agentic.py: the Lighthouse 13.5.0 fraction rules, run
        against a real PSI result (tests/fixtures) and synthetic edge cases.
    scripts/agentic_check.py: RFC 9309 group selection, Content-Signal parsing,
        Lighthouse llms-txt parity, ARD conformance, Link header parsing,
        WebMCP markup detection, SSRF refusal. No live network.
    scripts/agentic_fix.py: robots.txt Content-Signal insertion, llms.txt,
        ai-catalog.json and WebMCP drafts.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
pytest.importorskip("bs4")
import agentic_check as ac  # noqa: E402
import agentic_fix as af  # noqa: E402
import lighthouse_agentic as la  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "lighthouse_agentic_13_5_psi.json"


# --------------------------------------------------------------------------- Lighthouse


@pytest.fixture()
def lhr():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_real_psi_result_is_four_of_four(lhr):
    frac = la.calculate_fraction(lhr)
    assert frac["display"] == "4/4"
    assert frac["informative"] == 2
    statuses = {r["id"]: r["status"] for r in la.explain(lhr)["audits"]}
    assert statuses["ard-schema"] == "not-applicable"
    assert statuses["webmcp-form-coverage"].startswith("informative")
    assert statuses["webmcp-registered-tools"].startswith("informative")


def test_real_psi_result_lists_tools_and_unannotated_form(lhr):
    rows = {r["id"]: r for r in la.explain(lhr)["audits"]}
    names = {t["name"] for t in rows["webmcp-registered-tools"]["tools"]}
    assert "search_skills" in names
    assert rows["webmcp-form-coverage"]["forms_missing_annotations"]


def test_annotating_every_form_makes_form_coverage_count(lhr):
    data = copy.deepcopy(lhr)
    data["audits"]["webmcp-form-coverage"].update(scoreDisplayMode="binary", score=1,
                                                  displayValue=None, details=None)
    assert la.calculate_fraction(data)["display"] == "5/5"


def test_schema_warning_score_counts_as_failure(lhr):
    data = copy.deepcopy(lhr)
    data["audits"]["webmcp-schema-validity"]["score"] = 0.5
    assert la.calculate_fraction(data)["display"] == "3/4"


def test_error_audit_counts_and_fails(lhr):
    data = copy.deepcopy(lhr)
    data["audits"]["llms-txt"].update(scoreDisplayMode="error", score=None)
    assert la.calculate_fraction(data)["display"] == "3/4"


def test_ard_warning_only_score_still_passes(lhr):
    data = copy.deepcopy(lhr)
    data["audits"]["ard-schema"].update(scoreDisplayMode="binary", score=0.9)
    assert la.calculate_fraction(data)["display"] == "5/5"


def test_paths_offer_form_annotation_and_catalog(lhr):
    audits = {p["audit"] for p in la.explain(lhr)["paths"]}
    assert {"webmcp-form-coverage", "ard-schema"} <= audits


def test_psi_wrapper_and_missing_category(lhr):
    assert la.extract_lhr({"lighthouseResult": lhr}) is lhr
    report = la.summarize({"categories": {}, "audits": {}}, "file")
    assert report["error"] and not report["fraction"]["available"]


def test_version_note_when_lighthouse_moves(lhr):
    data = copy.deepcopy(lhr)
    data["lighthouseVersion"] = "13.6.0"
    assert "13.6.0" in la.summarize(data, "file")["version_note"]


# --------------------------------------------------------------------------- robots.txt


ROBOTS = """User-agent: *
Content-Signal: search=yes, ai-input=yes, ai-train=no
Disallow: /private

User-agent: GPTBot
User-agent: ClaudeBot
Disallow: /

User-agent: OAI-SearchBot
Allow: /
Agentmap: /catalog.json
Sitemap: https://example.com/sitemap.xml
"""


def test_named_group_replaces_star_group():
    parsed = ac.parse_robots(ROBOTS)
    gpt = ac.select_group(parsed, "gptbot")
    assert gpt["matched"] == "named"
    assert not ac.is_allowed(gpt["rules"], "/")
    assert gpt["content_signal"] == []  # nothing inherits from *
    other = ac.select_group(parsed, "PerplexityBot")
    assert other["matched"] == "star" and other["content_signal"]
    assert parsed["agentmap"] == ["/catalog.json"]
    assert parsed["sitemap"] == ["https://example.com/sitemap.xml"]


@pytest.mark.parametrize(("rules", "path", "allowed"), [
    ([("disallow", "/")], "/", False),
    ([("disallow", "")], "/", True),
    ([("disallow", "/"), ("allow", "/")], "/", True),  # tie: allow wins
    ([("disallow", "/*.pdf$")], "/a.pdf", False),
    ([("disallow", "/*.pdf$")], "/a.pdf?x", True),
    ([("disallow", "/private"), ("allow", "/private/ok")], "/private/ok/1", True),
])
def test_longest_match(rules, path, allowed):
    assert ac.is_allowed(rules, path) is allowed


def test_content_signal_parsing():
    assert ac.parse_content_signal("search=yes, ai-input=no, ai-train=no")["issues"] == []
    assert ac.parse_content_signal("search=yes, use=reference")["issues"] == []
    issues = ac.parse_content_signal("search=maybe, foo=yes, use=always")["issues"]
    assert len(issues) == 3


def _rec(status, text="", headers=None):
    return {"url": "u", "status": status, "headers": headers or {}, "text": text,
            "final_url": "https://example.com/", "error": None}


def test_audit_robots_flags_content_signal_gap_and_blocked_search():
    robots = ROBOTS.replace("User-agent: OAI-SearchBot\nAllow: /", "User-agent: OAI-SearchBot\nDisallow: /")
    with patch.object(ac, "fetch", return_value=_rec(200, robots)):
        checks, data = ac.audit_robots("https://example.com")
    by_id = {c["id"]: c for c in checks}
    assert by_id["content-signal"]["status"] == "warn"
    assert "GPTBot" in by_id["content-signal"]["evidence"]["named_groups_without_signal"]
    assert by_id["robots-ai-groups"]["status"] == "warn"
    assert "OAI-SearchBot" in by_id["robots-ai-groups"]["evidence"]["search_crawlers_blocked_at_root"]


def test_robots_5xx_is_a_p0_failure():
    with patch.object(ac, "fetch", return_value=_rec(503)):
        checks, _ = ac.audit_robots("https://example.com")
    assert checks[0]["status"] == "fail" and checks[0]["priority"] == "P0"


# --------------------------------------------------------------------------- llms.txt


GOOD_LLMS = "# Example\n\n> A site.\n\n## Docs\n\n- [Guide](https://example.com/guide): how to\n"


@pytest.mark.parametrize(("status", "content", "expected"), [
    (404, None, "not-applicable"),
    (500, None, "fail"),
    (None, None, "fail"),
    (200, GOOD_LLMS, "pass"),
    (200, "No heading here but a [link](https://x.y) and enough text to pass length", "fail"),
    (200, "# Title only, long enough to pass the fifty character rule", "fail"),
    (200, "# T\n[a](b)", "fail"),
    (200, "<!doctype html><html># x [a](b) padding padding padding padding</html>", "fail"),
])
def test_llms_txt_matches_lighthouse(status, content, expected):
    assert ac.evaluate_llms_txt(status, content)["lighthouse"] == expected


# --------------------------------------------------------------------------- ARD


VALID_CATALOG = {
    "specVersion": "1.0",
    "entries": [{
        "identifier": "urn:air:example.com:docs",
        "displayName": "Docs",
        "type": "application/mcp-server-card+json",
        "url": "https://example.com/mcp/server-card",
        "representativeQueries": ["a", "b"],
    }],
}


def test_valid_catalog():
    result = ac.validate_ai_catalog(json.dumps(VALID_CATALOG))
    assert result == {"errors": [], "warnings": [], "entries": 1}


def test_catalog_errors():
    bad = copy.deepcopy(VALID_CATALOG)
    entry = bad["entries"][0]
    entry["identifier"] = "docs"
    entry["data"] = {}
    entry["representativeQueries"] = ["only one"]
    bad["collections"] = []
    result = ac.validate_ai_catalog(json.dumps(bad))
    assert len(result["errors"]) == 3
    assert result["warnings"]
    assert ac.validate_ai_catalog("{not json")["errors"]
    assert ac.validate_ai_catalog('{"entries": []}')["errors"] == ["missing required 'specVersion'"]


def test_ard_not_applicable_without_signal():
    with patch.object(ac, "fetch", return_value=_rec(404)):
        checks, data = ac.audit_ard("https://example.com", [], {})
    assert checks[0]["status"] == "na" and not data["signalled"]


def test_ard_signalled_but_missing_fails():
    with patch.object(ac, "fetch", return_value=_rec(404)):
        checks, data = ac.audit_ard("https://example.com", ["/catalog.json"], {})
    assert checks[0]["status"] == "fail"
    assert data["catalog_url"] == "https://example.com/catalog.json"


# --------------------------------------------------------------------------- markup


def test_link_header_parsing():
    links = ac.parse_link_header('</p.md>; rel="alternate"; type="text/markdown", '
                                 '</ai-catalog.json>; rel=ai-catalog')
    assert links[0]["rel"] == ["alternate"] and links[0]["type"] == "text/markdown"
    assert links[1]["rel"] == ["ai-catalog"]


def test_webmcp_markup_detects_legacy_entry_point():
    html = ('<html><body><form id="f" toolname="x"><input name="q"></form><form id="g"></form>'
            '<script>navigator.modelContext.registerTool({name:"a"})</script></body></html>')
    data: dict = {}
    checks = ac._webmcp_markup(ac._soup(html), "https://example.com/", data)
    ids = {c["id"]: c for c in checks}
    assert ids["webmcp-tools"]["status"] == "pass"
    assert ids["webmcp-entry-point"]["status"] == "warn"
    assert ids["webmcp-form-annotations"]["evidence"]["unannotated"] == ["g"]
    assert data["webmcp"]["registerTool_call_sites"] == 1


def test_js_shell_detection():
    shell = '<html><body><div id="root"></div><script src="/app.js"></script></body></html>'
    assert ac.visible_words(shell) == 0 and ac.JS_SHELL.search(shell)


def test_fetch_refuses_private_targets():
    record = ac.fetch("http://127.0.0.1/robots.txt")
    assert record["status"] is None and "url_safety" in record["error"]


def test_well_known_soft_404_is_flagged():
    with patch.object(ac, "fetch", return_value=_rec(200, "<html>", {"content-type": "text/html"})):
        checks, data = ac.audit_well_known("https://example.com")
    assert all(c["status"] == "warn" for c in checks)
    assert all(row.get("soft_404") for row in data.values())


# --------------------------------------------------------------------------- fix drafts


def test_add_content_signal_to_every_group_without_touching_rules():
    robots = "User-agent: *\nDisallow: /a\n\nUser-agent: GPTBot\nContent-Signal: ai-train=no\nDisallow: /\n"
    result = af.add_content_signal(robots, "search=yes, ai-train=no")
    lines = result["robots_txt"].splitlines()
    assert lines[:3] == ["User-agent: *", "Content-Signal: search=yes, ai-train=no", "Disallow: /a"]
    assert result["groups_changed"] == [["*"]]
    assert result["robots_txt"].count("Disallow") == 2


def test_add_content_signal_creates_group_when_missing():
    result = af.add_content_signal("Sitemap: https://example.com/s.xml\n", "search=yes")
    assert result["robots_txt"] == ("Sitemap: https://example.com/s.xml\n\n"
                                    "User-agent: *\nContent-Signal: search=yes\n")
    assert af.add_content_signal("", "search=yes")["robots_txt"] == (
        "User-agent: *\nContent-Signal: search=yes\n")


def test_add_content_signal_rejects_bad_signal():
    with pytest.raises(ValueError):
        af.add_content_signal("", "search=perhaps")


def test_llms_draft_passes_lighthouse_rules():
    html = ('<html><head><title>Acme</title><meta name="description" content="Tools."></head>'
            '<body><nav><a href="/docs">Docs</a><a href="https://other.test/">Out</a></nav></body></html>')
    draft = af.draft_llms_txt("https://acme.test/", html)
    assert draft.startswith("# Acme") and "(https://acme.test/docs)" in draft
    assert "other.test" not in draft
    assert ac.evaluate_llms_txt(200, draft)["lighthouse"] == "pass"


def test_ai_catalog_draft_validates():
    result = af.draft_ai_catalog("Example.com", ["Docs MCP|application/mcp-server-card+json|https://e.test/c"])
    assert result["validation"]["errors"] == []
    assert result["catalog"]["entries"][0]["identifier"] == "urn:air:example-com:docs-mcp"


def test_webmcp_draft_binds_to_form_and_marks_consequential():
    html = """<form id="contact" method="post" action="/send">
      <label for="e">Email</label><input id="e" name="email" type="email" required>
      <select name="topic"><option value="sales">Sales</option></select>
      <input name="agree" type="checkbox"><input name="csrf" type="hidden">
      <input name="pw" type="password"></form>"""
    tools = af.draft_webmcp("https://e.test/", html)
    assert len(tools) == 1
    tool = tools[0]
    assert tool["consequential"] and tool["tool_name"] == "contact"
    js = tool["imperative_js"]
    assert "form.requestSubmit()" in js and "document.modelContext" in js
    assert '"consequentialHint": true' in js
    assert "csrf" not in js and '"pw"' not in js
    assert '"enum": [\n' in js or '"enum": ["sales"]' in js.replace("\n", "").replace("  ", "")


def test_fix_output_never_overwrites(tmp_path, monkeypatch):
    target = tmp_path / "robots.txt"
    target.write_text("keep", encoding="utf-8")
    src = tmp_path / "in.txt"
    src.write_text("User-agent: *\nDisallow:\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["agentic_fix.py", "robots", "--file", str(src),
                                      "--output", str(target)])
    with pytest.raises(SystemExit):
        af.main()
    assert target.read_text(encoding="utf-8") == "keep"


def test_runtime_allows_new_scripts():
    import runtime
    for name in ("agentic_check.py", "agentic_fix.py", "lighthouse_agentic.py"):
        assert name in runtime.ALLOWED_CORE_SCRIPTS
        assert os.path.isfile(ROOT / "scripts" / name)


# --------------------------------------------------------------------------- review regressions


def test_bom_robots_parses_and_fix_keeps_policy():
    bom = "\ufeffUser-agent: *\nDisallow: /\n"
    assert len(ac.parse_robots(bom)["groups"]) == 1
    draft = af.add_content_signal(bom, "search=yes")["robots_txt"]
    assert "Allow: /" not in draft and draft.startswith("User-agent: *\nContent-Signal")
    assert not ac.is_allowed(ac.select_group(ac.parse_robots(draft), "GPTBot")["rules"], "/")


def test_orphan_rules_stay_inert_when_a_group_is_added():
    draft = af.add_content_signal("Disallow: /private\n", "search=yes")["robots_txt"]
    group = ac.select_group(ac.parse_robots(draft), "GPTBot")
    assert group["rules"] == [] and "Allow" not in draft


@pytest.mark.parametrize("status", [503, 403, None])
def test_robots_fix_refuses_to_draft_after_failed_fetch(status, monkeypatch):
    monkeypatch.setattr(af, "fetch", lambda url: _rec(status) if status else
                        {**_rec(None), "error": "network"})
    monkeypatch.setattr(sys, "argv", ["agentic_fix.py", "robots", "https://example.com"])
    if status == 403:  # a 4xx means "no robots.txt": drafting a new file is correct
        af.main()
    else:
        with pytest.raises(SystemExit):
            af.main()


def test_decode_survives_unknown_charset_and_defaults_to_utf8():
    assert ac._decode(b"ok", "text/plain; charset=utf8mb4") == "ok"
    assert ac._decode("\u00e9".encode(), "text/plain") == "\u00e9"
    assert ac._decode("\ufeff# T".encode(), "text/plain") == "# T"


def test_bom_llms_txt_passes_like_lighthouse():
    text = "\ufeff# Title\n\n- [Guide](https://example.com/g) with enough padding"
    assert ac.evaluate_llms_txt(200, text)["lighthouse"] == "pass"


def test_webmcp_draft_uses_document_order_and_escapes_script_end():
    html = """<div><form><input name="a"></form></div>
              <div><form><label for="b">&lt;/script&gt;x</label><input id="b" name="b"></form></div>"""
    tools = af.draft_webmcp("https://e.test/", html)
    assert "document.forms[1]" in tools[1]["imperative_js"]
    body = tools[1]["imperative_js"].rsplit("</script>", 1)[0]
    assert "</script" not in body


def test_radio_group_becomes_one_enum_field():
    html = """<form id="f"><input type="radio" name="r" value="a" required>
              <input type="radio" name="r" value="b"></form>"""
    field = af._form_fields(af_soup(html).find("form"))
    assert len(field) == 1 and field[0]["schema"]["enum"] == ["a", "b"] and field[0]["required"]


def af_soup(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml")


def test_ua_matrix_inconclusive_when_baseline_challenged(monkeypatch):
    monkeypatch.setattr(ac, "fetch", lambda url, headers=None: _rec(403))
    checks, _ = ac.audit_ua_matrix("https://example.com/")
    assert "Inconclusive" in checks[0]["fix"]


def test_generic_words_on_normal_page_are_not_a_challenge():
    assert not ac._challenged(_rec(200, "Please complete the captcha. Access denied for guests."))
    assert ac._challenged(_rec(200, "<title>Just a moment...</title>"))


def test_from_json_bad_file_exits_cleanly(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lighthouse_agentic.py", "--from-json", str(bad)])
    with pytest.raises(SystemExit) as exc:
        la.main()
    assert exc.value.code == 1


def test_priority_table_checks_always_emit_a_row():
    html = "<html><body><p>plain page</p></body></html>"
    data: dict = {}
    ids = {c["id"]: c["status"] for c in ac._webmcp_markup(ac._soup(html), "https://e.test/", data)}
    assert ids == {"webmcp-tools": "info", "webmcp-entry-point": "na", "webmcp-form-annotations": "na"}
    with patch.object(ac, "fetch", return_value=_rec(200, "User-agent: *\nAllow: /\n")):
        checks, _ = ac.audit_robots("https://example.com")
    assert {c["id"]: c["status"] for c in checks}["robots-user-agents"] == "pass"


def test_agent_ux_falls_back_to_raw_html_without_a_renderer(monkeypatch):
    import agent_ux_check

    def fake_render(url, mode="auto", **_kwargs):
        if mode == "always":
            return {"url": url, "status_code": None, "error": "Executable doesn't exist"}
        return {"url": url, "status_code": 200, "error": None,
                "content": "<html><body><main><div onclick='x()'>Buy</div>"
                           "<p>" + "word " * 60 + "</p></main></body></html>"}

    monkeypatch.setattr(agent_ux_check, "render_page", fake_render)
    report = agent_ux_check.audit("https://e.test/")
    assert report["score_status"] == "unavailable" and report["score"] is None
    assert report["html_only_fallback"] is True and report["html_findings"]


def test_decode_uses_meta_charset_when_the_header_has_none():
    body = '<html><head><meta charset="iso-8859-1"></head><body>Caf\xe9</body></html>'.encode("iso-8859-1")
    assert "Café" in ac._decode(body, "text/html")


def test_catch_all_200_is_diagnosed_as_missing_404(monkeypatch):
    html = _rec(200, "<!doctype html><html><body>app</body></html>", {"content-type": "text/html"})
    monkeypatch.setattr(ac, "fetch", lambda url, headers=None: html)
    checks, data = ac.audit_ard("https://e.test", [], {})
    assert checks[0]["status"] == "fail" and checks[0]["priority"] == "P1"
    assert "real 404" in checks[0]["fix"] and data["soft_404"]
    checks, _ = ac.audit_not_found("https://e.test")
    assert checks[0]["id"] == "http-404" and checks[0]["status"] == "warn"
    checks, _ = ac.audit_llms("https://e.test")
    assert "real 404" in checks[0]["fix"]


def test_real_404_passes_the_probe(monkeypatch):
    monkeypatch.setattr(ac, "fetch", lambda url, headers=None: _rec(404))
    checks, data = ac.audit_not_found("https://e.test")
    assert checks[0]["status"] == "pass" and data["catch_all_200"] is False


TOKENS = ["GPTBot", "CCBot", "ClaudeBot", "OAI-SearchBot", "Googlebot", "PerplexityBot", "*"]


def _policy(text: str) -> dict:
    parsed = ac.parse_robots(text)
    return {t: ac.is_allowed(ac.select_group(parsed, t)["rules"], "/") for t in TOKENS}


@pytest.mark.parametrize("robots", [
    "User-agent: GPTBot\n# training bots\nUser-agent: CCBot\nDisallow: /\n",
    "User-agent: GPTBot\n\nUser-agent: CCBot\nDisallow: /\n",
    "User-agent: *\nAllow: /\n\nUser-agent: GPTBot\n# c\n\nUser-agent: ClaudeBot\nDisallow: /\n# tail\nUser-agent: OAI-SearchBot\nAllow: /\n",
    "﻿User-agent: GPTBot\r\nUser-agent: CCBot\r\nDisallow: /\r\n",
])
def test_content_signal_never_changes_who_is_allowed(robots: str) -> None:
    """The drafter's promise: Allow/Disallow outcomes are identical after the edit."""
    draft = af.add_content_signal(robots, "search=yes, ai-train=no")["robots_txt"]
    assert _policy(draft) == _policy(robots), draft
    parsed = ac.parse_robots(draft)
    for group in parsed["groups"]:
        assert group["content_signal"], f"group without signal: {group['agents']}"


def test_content_signal_policy_equivalence_randomized() -> None:
    """500 generated robots.txt files: the drafter never changes an outcome."""
    import random

    rng = random.Random(20260923)
    agents = ["GPTBot", "CCBot", "ClaudeBot", "OAI-SearchBot", "PerplexityBot", "*"]
    fillers = ["", "# note", "   ", "Sitemap: https://e.test/s.xml"]
    rules = ["Disallow: /", "Allow: /", "Disallow:", "Disallow: /private", "Crawl-delay: 5"]
    for _ in range(500):
        lines = []
        for _ in range(rng.randint(1, 4)):
            for _ in range(rng.randint(1, 3)):
                lines.append(f"User-agent: {rng.choice(agents)}")
                if rng.random() < 0.4:
                    lines.append(rng.choice(fillers))
            for _ in range(rng.randint(0, 3)):
                lines.append(rng.choice(rules))
                if rng.random() < 0.3:
                    lines.append(rng.choice(fillers))
        robots = rng.choice(["\n", "\r\n"]).join(lines) + "\n"
        draft = af.add_content_signal(robots, "search=yes")["robots_txt"]
        assert _policy(draft) == _policy(robots), robots
