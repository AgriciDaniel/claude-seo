"""Non-rule records must not split a robots.txt user-agent group."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import agentic_check as checker  # noqa: E402
import agentic_fix as drafter  # noqa: E402

OTHER_RECORDS = [
    "Sitemap: https://example.com/sitemap.xml",
    "Agentmap: /catalog.json",
    "Crawl-delay: 5",
    "Unknown-field: value",
    ": unnamed",
    "Content-Signal: search=yes, ai-train=no",
]


def robots(record, rules="Disallow: /"):
    return (
        "User-agent: OAI-SearchBot\n" + record + "\n\n"
        "User-agent: Claude-SearchBot\n" + rules + "\n"
    )


@pytest.mark.parametrize("record", OTHER_RECORDS)
def test_other_records_do_not_split_crawler_rules(record):
    parsed = checker.parse_robots(robots(record))
    assert len(parsed["groups"]) == 1
    for token in ("OAI-SearchBot", "Claude-SearchBot"):
        selected = checker.select_group(parsed, token)
        assert selected["matched"] == "named"
        assert not checker.is_allowed(selected["rules"], "/")


@pytest.mark.parametrize("record", OTHER_RECORDS[:-1])
def test_drafter_adds_one_signal_for_the_whole_group(record):
    result = drafter.add_content_signal(robots(record), "search=yes")
    assert result["groups_changed"] == [["OAI-SearchBot", "Claude-SearchBot"]]
    assert result["robots_txt"].count("Content-Signal:") == 1
    assert record in result["robots_txt"]
    parsed = checker.parse_robots(result["robots_txt"])
    assert len(parsed["groups"]) == 1
    assert parsed["groups"][0]["content_signal"] == ["search=yes"]


def test_existing_signal_covers_both_agents():
    original = robots("Content-Signal: search=yes")
    result = drafter.add_content_signal(original, "ai-train=no")
    assert result["groups_changed"] == []
    assert result["robots_txt"] == original


def test_audit_reports_both_search_crawlers_blocked(monkeypatch):
    monkeypatch.setattr(checker, "fetch", lambda url: {
        "status": 200, "error": None, "headers": {},
        "text": robots("Sitemap: https://example.com/sitemap.xml"),
    })
    checks, data = checker.audit_robots("https://example.com")
    findings = {check["id"]: check for check in checks}
    blocked = findings["robots-ai-groups"]["evidence"]["search_crawlers_blocked_at_root"]
    assert blocked == ["OAI-SearchBot", "Claude-SearchBot"]
    assert data["group_count"] == 1
    assert data["parsed"]["sitemap"] == ["https://example.com/sitemap.xml"]


@pytest.mark.parametrize("rule", ["Allow: /", "Disallow:", "Disallow: /private"])
def test_access_rules_still_end_the_user_agent_block(rule):
    original = (
        "User-agent: OAI-SearchBot\n" + rule + "\n"
        "Sitemap: https://example.com/sitemap.xml\n"
        "User-agent: Claude-SearchBot\nDisallow: /\n"
    )
    parsed = checker.parse_robots(original)
    assert len(parsed["groups"]) == 2
    assert checker.is_allowed(checker.select_group(parsed, "OAI-SearchBot")["rules"], "/")
    assert not checker.is_allowed(checker.select_group(parsed, "Claude-SearchBot")["rules"], "/")
