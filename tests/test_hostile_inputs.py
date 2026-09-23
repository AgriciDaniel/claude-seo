"""Hostile or malformed input must yield a finding, never a traceback (audit 2026-09-23).

Each case was reproduced by the post-release code audit against the scripts
added or changed on the v2.4.0 branch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

pytest.importorskip("requests")
pytest.importorskip("bs4")
import agentic_check as ac  # noqa: E402
import keywordseverywhere_api as ke  # noqa: E402
import lighthouse_agentic as la  # noqa: E402
import ucp_check  # noqa: E402

DEEP = "[" * 100000 + "]" * 100000


def _rec(status, text="", headers=None):
    return {"url": "u", "status": status, "headers": headers or {}, "text": text,
            "final_url": "https://e.test/", "error": None}


def test_deeply_nested_catalog_is_a_finding_not_a_crash():
    result = ac.validate_ai_catalog(DEEP)
    assert result["errors"]


def test_deeply_nested_well_known_document_is_a_finding(monkeypatch):
    monkeypatch.setattr(ac, "fetch", lambda url, headers=None: _rec(200, DEEP, {"content-type": "application/json"}))
    checks, _ = ac.audit_well_known("https://e.test")
    assert all(c["status"] == "fail" for c in checks)


def test_ucp_profile_hostile_shapes_do_not_crash():
    assert ucp_check.parse_profile(DEEP)["issues"]
    profile = {"ucp": {"version": "2026-08-25", "services": {"dev.ucp.shopping": [
        {"version": "2026-08-25", "transport": "rest", "endpoint": {"url": "x"}},
        {"version": "2026-08-25", "transport": "rest", "endpoint": "https://e.test/api"}]},
        "capabilities": {"dev.ucp.shopping.cart": [{"version": "v", "spec": "s", "schema": "s"}]}}}
    parsed = ucp_check.parse_profile(json.dumps(profile))
    assert "endpoint-not-a-string" in parsed["services"][0]["issues"]
    with patch.object(ucp_check, "safe_requests_get") as get, \
         patch.object(ucp_check, "validate_url_strict", return_value=("https://e.test/.well-known/ucp", "1.2.3.4")), \
         patch.object(ucp_check, "probe_endpoint", return_value={"url": "p"}):
        get.return_value.status_code = 200
        get.return_value.content = json.dumps(profile).encode()
        get.return_value.headers = {"Content-Type": "application/json"}
        report = ucp_check.audit_site("https://e.test", probe_endpoints=True)
    assert report["profile_present"]


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, ""

    def json(self):
        return self._body


@pytest.mark.parametrize("body", [[1, 2], {"results": [1, "x", None]}, {"results": "nope"}])
def test_keywordseverywhere_odd_success_bodies(body):
    with patch.object(ke, "_post", return_value=_Resp(200, body)):
        result = ke.get_rank(["example.com"], "opr_live_testkey")
    assert result["status"] in ("error", "success")
    assert "Traceback" not in json.dumps(result)


def test_keywordseverywhere_never_echoes_a_malformed_key():
    result = ke.get_rank(["example.com"], "SECRETKEY123\n")
    assert "SECRETKEY123" not in json.dumps(result)


@pytest.mark.parametrize("data", [
    {"lighthouseResult": None},
    {"categories": {"agentic-browsing": {"auditRefs": [{"id": "x"}]}}, "audits": {"x": "not-a-dict"}},
    {"categories": {"agentic-browsing": {"auditRefs": [{"id": "x"}]}},
     "audits": {"x": {"scoreDisplayMode": "binary", "score": "high"}}},
])
def test_lighthouse_reader_survives_malformed_results(data):
    report = la.summarize(la.extract_lhr(data), "file")
    assert isinstance(report, dict)


def test_lighthouse_reader_accepts_a_bom_file(tmp_path, monkeypatch, capsys):
    fixture = (ROOT / "tests/fixtures/lighthouse_agentic_13_5_psi.json").read_text(encoding="utf-8")
    path = tmp_path / "report.json"
    path.write_text("﻿" + fixture, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lighthouse_agentic.py", "--from-json", str(path), "--json"])
    with pytest.raises(SystemExit) as exc:
        la.main()
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["fraction"]["display"] == "4/4"


def test_agentic_decoder_matches_the_shared_decoder_on_utf16():
    body = "﻿Café".encode("utf-16-le")
    body = b"\xff\xfe" + body[2:]
    assert ac._decode(body, "text/html") == "Café"


# Second verification pass (same day): remaining crash shapes and robots edge cases.

def test_ucp_list_transport_is_an_issue_not_a_crash():
    profile = {"ucp": {"version": "2026-08-25", "services": {"dev.ucp.shopping": [
        {"version": "2026-08-25", "transport": ["rest"], "endpoint": "https://e.test/a"}]},
        "capabilities": {"dev.ucp.shopping.cart": [{"version": "v", "spec": "s", "schema": "s"}]}}}
    parsed = ucp_check.parse_profile(json.dumps(profile))
    assert "unknown-transport" in parsed["services"][0]["issues"]


def test_keywordseverywhere_deep_json_success_body():
    class Deep(_Resp):
        def json(self):
            return json.loads(DEEP)
    with patch.object(ke, "_post", return_value=Deep(200, None)):
        result = ke.get_rank(["example.com"], "opr_live_testkey")
    assert result["status"] == "error"


@pytest.mark.parametrize("category", [
    {"auditRefs": None}, {"auditRefs": ["x", 3]}, ["not", "a", "dict"],
])
def test_lighthouse_malformed_category_shapes(category):
    report = la.summarize(la.extract_lhr({"categories": {"agentic-browsing": category},
                                          "audits": {}}), "file")
    assert isinstance(report, dict)


def test_robots_colon_only_line_ends_a_user_agent_block_in_both_tools():
    import agentic_fix as af
    robots = "User-agent: A\n: junk\nUser-agent: B\nDisallow: /\n"
    draft = af.add_content_signal(robots, "search=yes")["robots_txt"]
    groups = ac.parse_robots(draft)["groups"]
    assert all(g["content_signal"] for g in groups), draft


def test_robots_unicode_line_separator_inside_a_comment_stays_a_comment():
    import agentic_fix as af
    robots = "User-agent: *\n# note Disallow: /\nAllow: /\n"
    draft = af.add_content_signal(robots, "search=yes")["robots_txt"]
    assert " " in draft  # the comment is not split into a live rule
    parsed = ac.parse_robots(robots)
    assert ac.is_allowed(ac.select_group(parsed, "GPTBot")["rules"], "/")
