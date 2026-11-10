"""Line-level llms.txt format notes in scripts/agentic_check.py.

The notes are checked against the llmstxt.org proposal and never change the
Lighthouse-style headline verdict. No live network: fetches are patched.
"""

from __future__ import annotations

import random
import re
import sys
import time
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

BOM = chr(0xFEFF)
LINE_SEPARATOR = chr(0x2028)
LONG_DASHES = (chr(0x2013), chr(0x2014))

# Shaped like the mock example on llmstxt.org.
SPEC_SHAPED = """# Title

> Optional description goes here

Optional details go here

- A plain list before the first H2 is allowed.

## Section name

- [Link title](https://example.com/a.md): Optional link details
- [Second](https://example.com/b.md): More details

## Optional

- [Link title](https://example.com/c.md): Secondary
"""

# Passes all three Lighthouse rules (an H1, a Markdown link, 50+ characters).
MALFORMED = """Welcome to our site

# Acme
# Acme again

Some text.

> A late summary.

### Details

## Docs
* [Star](https://acme.test/1): starred
- [No colon](https://acme.test/2) the notes
- See [late link](https://acme.test/3)
- just words
- [Spaced] (https://acme.test/4)
- Docs: https://acme.test/5
- [Mail](mailto:a@acme.test)
- [Again](https://acme.test/1): repeat
- [About](/about): about

## optional extras

## Empty
"""


def notes(text, **kwargs):
    return ac.llms_format_notes(text, **kwargs)["format_notes"]


def ids(text, **kwargs):
    return [note["id"] for note in notes(text, **kwargs)]


def test_a_file_shaped_like_the_spec_example_has_no_notes():
    result = ac.llms_format_notes(SPEC_SHAPED, base_url="https://example.com/llms.txt",
                                  content_type="text/plain; charset=utf-8")
    assert result == {"format_notes": [], "format_note_counts": {}}


def test_only_the_title_is_required():
    found = notes("# Just a name\n")
    assert [note["id"] for note in found] == ["no-summary-blockquote", "no-link-list"]
    assert {note["level"] for note in found} == {"info"}


def test_missing_title_is_the_only_error_level():
    assert [level for level, _ in ac.LLMS_FORMAT_RULES.values()].count("error") == 1
    first = notes("Welcome\n# Name\n")[0]
    assert (first["id"], first["level"], first["line"]) == ("missing-h1-title", "error", 1)
    assert first["detail"] == "Welcome"


@pytest.mark.parametrize("text", ["", "   \n\n", "```\n# inside a code block\n```\n"])
def test_a_file_with_no_content_reports_the_missing_title(text):
    found = notes(text)
    assert found[0]["id"] == "missing-h1-title" and found[0]["line"] is None


def test_a_byte_order_mark_is_allowed():
    assert ids(BOM + "# Name\n\n> Summary.\n") == ["no-link-list"]


def test_a_second_h1_is_a_warning_on_its_own_line():
    found = {note["id"]: note for note in notes("# One\n\n> S\n\n# Two\n")}
    assert found["multiple-h1"]["level"] == "warn" and found["multiple-h1"]["line"] == 5
    assert found["multiple-h1"]["detail"] == "H1 on lines 1, 5"


def test_summary_position():
    assert "summary-not-after-title" in ids("# Name\n\nText first.\n\n> Late summary.\n")
    assert "summary-not-after-title" not in ids("# Name\n> Right after.\n> Second line.\n")
    assert "no-summary-blockquote" not in ids("# Name\n\n> After a blank line.\n")


def test_only_h2_may_split_the_file():
    found = notes("# Name\n\n> S\n\n### Details\n\nText.\n\n## Docs\n- [A](https://a.test/): a\n")
    assert [(note["id"], note["line"]) for note in found] == [("heading-in-details", 5)]


def test_headings_inside_code_blocks_are_ignored():
    text = "# Name\n\n> S\n\n```\n# not a title\n### nor this\n```\n\n## Docs\n- [A](https://a.test/): a\n"
    assert ids(text) == []


def test_file_list_items_are_flagged_with_their_line():
    text = ("# Name\n\n> S\n\n## Docs\n"
            "* [Star](https://a.test/1): starred\n"
            "- [No colon](https://a.test/2) the notes\n"
            "- See [late link](https://a.test/3)\n"
            "- just words\n"
            "- [Spaced] (https://a.test/4)\n"
            "- Docs: https://a.test/5\n"
            "- [Mail](mailto:a@a.test)\n"
            "- [Again](https://a.test/1): repeat\n")
    found = notes(text)
    assert {(note["id"], note["line"]) for note in found} >= {
        ("bullet-not-dash", 6), ("notes-without-colon", 7), ("link-not-at-start", 8),
        ("item-without-link", 9), ("malformed-link", 10), ("malformed-link", 11),
        ("invalid-url", 12), ("duplicate-link", 13)}
    levels = {note["id"]: note["level"] for note in found}
    assert levels["malformed-link"] == "warn"
    assert levels["item-without-link"] == levels["link-not-at-start"] == "info"
    assert levels["duplicate-link"] == "info"
    duplicate = next(note for note in found if note["id"] == "duplicate-link")
    assert duplicate["detail"].startswith("repeats line 6")


def test_long_files_show_five_of_each_note_and_count_the_rest():
    text = "# Name\n\n> S\n\n## Docs\n" + "".join(
        f"- [P{i}](https://a.test/{i}) - dash notes\n" for i in range(40))
    result = ac.llms_format_notes(text)
    shown = [note for note in result["format_notes"] if note["id"] == "notes-without-colon"]
    assert len(shown) == ac.LLMS_NOTES_PER_ID == 5
    assert result["format_note_counts"]["notes-without-colon"] == 40


def test_relative_links_are_info_and_resolve_against_the_file_for_duplicates():
    text = "# Name\n\n> S\n\n## Docs\n- [About](/about): about\n- [Same](https://brand.test/about): same\n"
    found = notes(text, base_url="https://brand.test/llms.txt")
    assert [(note["id"], note["level"], note["line"]) for note in found] == [
        ("relative-url", "info", 6), ("duplicate-link", "info", 7)]
    assert "empty-section" not in ids("# Name\n\n> S\n\n## Docs\n- [About](/about): about\n")


def test_duplicates_ignore_host_case_and_fragment():
    text = ("# Name\n\n> S\n\n## Docs\n- [A](https://A.test/x#top): a\n- [B](https://a.test/x): b\n"
            "- [C](https://a.test/x?v=2): c\n")
    assert [(note["id"], note["line"]) for note in notes(text)] == [("duplicate-link", 7)]


def test_sections_optional_and_guidance():
    assert "empty-section" in ids("# Name\n\n> S\n\n## Empty\n\n## Docs\n- [A](https://a.test/): a\n")
    assert "optional-heading-variant" in ids("# Name\n\n> S\n\n## optional links\n- [A](https://a.test/): a\n")
    assert "optional-heading-variant" not in ids(SPEC_SHAPED)
    assert "optional-heading-variant" not in ids("# Name\n\n> S\n\n## Optionality\n- [A](https://a.test/): a\n")
    without = notes("# Name\n\n> S\n\n## Docs\n- [A](https://a.test/a)\n- [B](https://a.test/b)\n")
    assert [(note["id"], note["detail"]) for note in without] == [("links-without-notes", "2 of 2 links")]
    assert "oversize" in ids("# Name\n\n> S\n\n" + ("Words. " * 20000))
    octet = notes("# Name\n\n> S\n", content_type="application/octet-stream")
    assert ("content-type", "info", "application/octet-stream") in [
        (note["id"], note["level"], note.get("detail")) for note in octet]
    assert "content-type" not in ids("# Name\n\n> S\n", content_type="text/markdown; charset=utf-8")


@pytest.mark.parametrize(("line", "expected"), [
    ("# C#", (1, "C#")),
    ("# Name ##", (1, "Name")),
    ("## Docs", (2, "Docs")),
    ("#", (1, "")),
    ("#hashtag", None),
    ("####### seven", None),
    ("plain", None),
])
def test_heading_reader(line, expected):
    assert ac._llms_heading(line) == expected


def test_link_destinations_markdown_allows():
    text = ("# Name\n\n> S\n\n## Docs\n"
            "- [Wiki](https://en.wikipedia.org/wiki/Foo_(bar)): note\n"
            "- [Angle](<https://a.test/y>): angle\n"
            '- [Titled](https://a.test/z "Title"): titled\n')
    assert ids(text, base_url="https://a.test/llms.txt") == []


def test_numbered_items_and_nested_fences():
    found = notes("# Name\n\n> S\n\n## Docs\n1. [One](https://a.test/1): one\n"
                  "```\n~~~\n## inside a code block\n```\n")
    assert [(note["id"], note["line"]) for note in found] == [("bullet-not-dash", 6)]


def test_line_numbers_follow_cr_lf_and_crlf_only():
    text = ("# Name\r\n\r\n> S\r\n\r\n## Docs\r- text with " + LINE_SEPARATOR
            + " inside\n- [Spaced] (https://a.test/4)\n")
    found = notes(text)
    assert [(note["id"], note["line"]) for note in found] == [
        ("empty-section", 5), ("item-without-link", 6), ("malformed-link", 7),
        ("no-link-list", None)]


def test_hostile_lines_do_not_crash_or_stall():
    long_run = " " * 200_000
    text = ("# Name\n\n> S\n\n"
            f"# a{long_run}b\n"
            "## Docs\n"
            "- [x](http://[::1)\n"
            f"- [{'a' * 200_000}\n"
            f"- [t]({'(' * 50_000}\n"
            f"- [t](https://a.test/{'x' * 200_000})\n")
    started = time.monotonic()
    result = ac.llms_format_notes(text, base_url="http://[bad")
    assert time.monotonic() - started < 5
    found = {(note["id"], note["line"]) for note in result["format_notes"]}
    assert ("invalid-url", 7) in found and ("malformed-link", 8) in found
    assert all(len(note.get("detail", "")) <= 80 for note in result["format_notes"])


# One fetched file is at most agentic_check.MAX_BODY (2,000,000 bytes). The
# Lighthouse-style regexes used to be quadratic: 40,000 blank lines took 1.8 s,
# so a full-size file of them would have run for over an hour.
HOSTILE_CHARS = 2_000_000
HOSTILE_FILES = [
    ("", "\n"), ("", "#"), ("", "- ["), ("", " "),
    ("", "["), ("", "\r"), ("", " \n"), ("", "\t\n#"), ("", "[x]("), ("", "](x"),
    ("#", "\n"), (">", "\n"), ("##", "\n"), ("# ", " "), ("# T\n\n", "["),
    ("# T\n\n> S\n\n## Docs\n", "- ["), ("# T\n## Docs\n", "- [x]("),
    ("# T\n## Docs\n- [t](", "(a"), ("# T\n## Docs\n", "- [t](u \""),
    ("# T\n## Docs\n", "\n"), ("# T\n", "## S\n"), ("# T\n## Docs\n", "- x\n"),
]


@pytest.mark.parametrize(("prefix", "unit"), HOSTILE_FILES)
def test_a_full_size_hostile_file_is_read_in_linear_time(prefix, unit):
    text = prefix + unit * (HOSTILE_CHARS // len(unit))

    started = time.monotonic()
    verdict = ac._lighthouse_llms_txt(200, text)
    verdict_seconds = time.monotonic() - started
    started = time.monotonic()
    fmt = ac.llms_format_notes(text)
    notes_seconds = time.monotonic() - started

    assert verdict_seconds < 2, f"Lighthouse-style verdict took {verdict_seconds:.1f} s"
    assert notes_seconds < 2, f"llms_format_notes took {notes_seconds:.1f} s"
    assert verdict["lighthouse"] == "fail"
    assert len(fmt["format_notes"]) <= len(ac.LLMS_FORMAT_RULES) * ac.LLMS_NOTES_PER_ID
    assert HOSTILE_CHARS >= ac.MAX_BODY


def _lighthouse_reference(content):
    """The verdict as first written, with the Lighthouse 13.5.0 regexes verbatim.

    Quadratic on hostile input, so only ever given short strings here.
    """
    errors = []
    if not re.search(r"^\s*#\s+.+", content, re.M):
        errors.append('missing an H1 header ("# Title")')
    if not re.search(r"\[.+\]\(.+\)", content):
        errors.append("contains no Markdown links")
    if len(content) < 50:
        errors.append("shorter than 50 characters")
    notes_ = []
    lines = [ln for ln in content.splitlines() if ln.strip()]
    if lines and not lines[0].lstrip().startswith("# "):
        notes_.append("llmstxt.org expects the H1 to be the first line")
    if not re.search(r"^\s*>\s+\S", content, re.M):
        notes_.append("no blockquote summary ('> ...') as llmstxt.org recommends")
    if not re.search(r"^\s*##\s+\S", content, re.M):
        notes_.append("no H2 sections grouping the links")
    if re.search(r"^\s*<(!doctype|html)", content, re.I):
        notes_.append("served HTML, not Markdown (likely a soft 404); not a Lighthouse rule")
    return {"lighthouse": "pass" if not errors else "fail", "errors": errors, "notes": notes_}


def test_linear_verdict_agrees_with_the_original_regexes_on_random_files():
    pieces = ["#", "##", " ", "  ", "\n", "\n\n", "\r", "\r\n", "\t", "\x0b", "\x0c", "\x1c",
              "\x85", "\xa0", LINE_SEPARATOR, "[", "]", "(", ")", "](", ">", "<", "a", "Title",
              "<!DOCTYPE", "<html", "- ", "x" * 50]
    rng = random.Random(260)
    for _ in range(30_000):
        text = "".join(rng.choice(pieces) for _ in range(rng.randint(0, 14)))
        assert ac._lighthouse_llms_txt(200, text) == _lighthouse_reference(text), repr(text)
    for text in (SPEC_SHAPED, MALFORMED, "", "#", "# ", "#  ", "# \n", "#\n\nx", " # x", "x # y",
                 "[a](b)", "[](b)", "[a]()", "[a]\n(b)", "[a](b\n)", "x[[a](b))", "\n\n<html>"):
        assert ac._lighthouse_llms_txt(200, text) == _lighthouse_reference(text), repr(text)


def test_every_rule_has_a_level_and_a_plain_message():
    for note_id, (level, message) in ac.LLMS_FORMAT_RULES.items():
        assert level in ("error", "warn", "info"), note_id
        assert message.endswith((".", ".'")), note_id
        assert not any(dash in message for dash in LONG_DASHES), note_id
        assert "rank" not in message.lower(), "a format note is never a ranking claim"


# --------------------------------------------------------------------------- headline verdict


def test_malformed_file_keeps_the_lighthouse_pass_and_lists_the_format_notes():
    result = ac.evaluate_llms_txt(200, MALFORMED, base_url="https://acme.test/llms.txt",
                                  content_type="text/html; charset=utf-8")
    assert result["lighthouse"] == "pass" and result["errors"] == []
    found = {(note["id"], note["line"]) for note in result["format_notes"]}
    assert found >= {
        ("missing-h1-title", 1), ("multiple-h1", 4), ("summary-not-after-title", 8),
        ("heading-in-details", 10), ("bullet-not-dash", 13), ("notes-without-colon", 14),
        ("link-not-at-start", 15), ("item-without-link", 16), ("malformed-link", 17),
        ("malformed-link", 18), ("invalid-url", 19), ("duplicate-link", 20),
        ("relative-url", 21), ("optional-heading-variant", 23), ("empty-section", 23),
        ("empty-section", 25), ("content-type", None)}
    assert len(result["format_note_counts"]) >= 10
    assert "proposal" in result["format_basis"] and "not a ratified standard" in result["format_basis"]
    assert all(isinstance(note, str) for note in result["notes"]), "the old notes list is unchanged"


@pytest.mark.parametrize(("status", "content"), [
    (None, None), (404, None), (500, None),
    (200, "<!doctype html><html># x [a](b) padding padding padding padding</html>"),
])
def test_no_format_notes_without_a_real_file(status, content):
    result = ac.evaluate_llms_txt(status, content)
    assert result["format_notes"] == [] and result["format_note_counts"] == {}
    assert result["format_basis"] == ac.LLMS_FORMAT_BASIS


def _rec(status, text="", headers=None, final_url="https://e.test/llms.txt"):
    return {"url": "u", "status": status, "headers": headers or {}, "text": text,
            "final_url": final_url, "error": None}


def test_audit_llms_puts_format_notes_in_the_evidence_without_changing_the_status():
    body = "# Acme\n\n## Docs\n* [About](/about)\n- [About again](https://e.test/about): same page\n"
    with patch.object(ac, "fetch", return_value=_rec(200, body, {"content-type": "text/plain"})):
        checks, data = ac.audit_llms("https://e.test")
    check = checks[0]
    assert check["id"] == "llms-txt" and check["status"] == "pass" and check["fix"] is None
    assert check["title"] == "llms.txt follows the Lighthouse rules"
    assert [(note["id"], note["line"]) for note in check["evidence"]["format_notes"]] == [
        ("no-summary-blockquote", 1), ("bullet-not-dash", 4), ("relative-url", 4),
        ("duplicate-link", 5)]
    assert data["format_note_counts"] == {"no-summary-blockquote": 1, "bullet-not-dash": 1,
                                          "relative-url": 1, "duplicate-link": 1}
    assert data["lighthouse"] == "pass" and data["notes"]


def test_audit_llms_missing_file_has_an_empty_list():
    with patch.object(ac, "fetch", return_value=_rec(404)):
        checks, data = ac.audit_llms("https://e.test")
    assert checks[0]["status"] == "info" and data["format_notes"] == []


def test_text_output_mentions_format_notes_as_hygiene(capsys):
    with patch.object(ac, "fetch", return_value=_rec(200, MALFORMED, {"content-type": "text/plain"})):
        checks, _ = ac.audit_llms("https://e.test")
    ac._print_text({"url": "https://e.test", "checks": checks, "summary": {}})
    out = capsys.readouterr().out
    assert "format note(s) against the llmstxt.org proposal" in out
    assert "not a ranking factor" in out
