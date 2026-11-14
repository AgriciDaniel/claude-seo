"""seo_updates.py must say when --limit cut the list (issue #459).

The filtered list was sliced to ``--limit`` (default 10) with nothing in the
output to show it. An audit asking for a date window got the 10 newest
entries, saw no core update among them and concluded there was none. The
output now carries the full match count and a ``truncated`` flag, ``--limit
0`` returns everything, and the skills that need the full window ask for it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import seo_updates  # noqa: E402

# 14 documentation entries newer than the one core update: the default limit
# of 10 hides the core update completely.
LEDGER = {
    "source_of_truth": "https://status.search.google.com/",
    "last_verified": "2026-01-20",
    "updates": [
        {"date": "2025-12-01", "kind": "core", "name": "December 2025 core update",
         "source": "https://status.search.google.com/x", "notes": "n"},
        *[
            {"date": f"2026-01-{day:02d}", "kind": "documentation", "name": f"Doc change {day}",
             "source": "https://developers.google.com/x", "notes": "n"}
            for day in range(1, 15)
        ],
    ],
}


def _run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(seo_updates, "_load", lambda: json.loads(json.dumps(LEDGER)))
    monkeypatch.setattr(sys, "argv", ["seo_updates.py", *argv])
    code = seo_updates.main()
    return code, capsys.readouterr()


def test_default_limit_reports_the_cut_in_json(monkeypatch, capsys) -> None:
    code, out = _run(monkeypatch, capsys, "--since", "2025-12", "--json")
    data = json.loads(out.out)
    assert code == 0
    assert data["count"] == 10 and len(data["updates"]) == 10
    assert data["total_matching"] == 15
    assert data["truncated"] is True
    assert all(u["kind"] != "core" for u in data["updates"])  # why the flag matters


def test_limit_zero_returns_every_match(monkeypatch, capsys) -> None:
    _code, out = _run(monkeypatch, capsys, "--since", "2025-12", "--limit", "0", "--json")
    data = json.loads(out.out)
    assert data["count"] == data["total_matching"] == 15
    assert data["truncated"] is False
    assert any(u["kind"] == "core" for u in data["updates"])


def test_a_list_that_fits_is_not_marked_truncated(monkeypatch, capsys) -> None:
    _code, out = _run(monkeypatch, capsys, "--kind", "core", "--json")
    data = json.loads(out.out)
    assert data["count"] == data["total_matching"] == 1
    assert data["truncated"] is False


def test_explicit_limit_is_still_honoured(monkeypatch, capsys) -> None:
    _code, out = _run(monkeypatch, capsys, "--limit", "3", "--json")
    data = json.loads(out.out)
    assert data["count"] == 3 and data["total_matching"] == 15 and data["truncated"] is True


def test_text_output_notes_the_cut(monkeypatch, capsys) -> None:
    _code, out = _run(monkeypatch, capsys, "--since", "2025-12")
    notes = [line for line in out.out.splitlines() if line.startswith("Note:")]
    assert len(notes) == 1
    assert "10 of 15" in notes[0] and "--limit 0" in notes[0]


def test_text_output_has_no_note_when_nothing_is_cut(monkeypatch, capsys) -> None:
    _code, out = _run(monkeypatch, capsys, "--kind", "core")
    assert "Note:" not in out.out


def test_negative_limit_is_rejected(monkeypatch, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, capsys, "--limit", "-1", "--json")
    assert exc.value.code == 2


@pytest.mark.parametrize("skill", ["seo-audit", "seo-content", "seo-geo"])
def test_skills_that_need_the_whole_window_ask_for_it(skill: str) -> None:
    text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    calls = re.findall(r"seo_updates\.py[^\n`]*", text)
    assert calls, f"{skill} no longer calls seo_updates.py"
    for call in calls:
        assert "--limit 0" in call, f"{skill}: {call!r} can be cut at 10 entries"
