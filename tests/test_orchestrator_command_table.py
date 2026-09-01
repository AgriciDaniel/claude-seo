"""Regression: the /seo orchestrator Quick Reference must list every extension command.

Optional extensions ship in ``extensions/<name>/skills/seo-<token>/`` and are
activated by a separate installer, so they are easy to document everywhere
(README, CLAUDE.md, AGENTS.md, docs/COMMANDS.md) while being forgotten in the
one table the model actually routes from. ``scripts/consistency_check.py``
matches ``/seo <cmd>`` anywhere in the file, so a prose mention alone satisfies
it; this test asserts the command has a row in the Quick Reference table itself.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ORCHESTRATOR = REPO / "skills" / "seo" / "SKILL.md"

COMMAND_CELL = re.compile(r"`/seo\s+([a-z][a-z0-9-]*)")


def quick_reference_commands():
    """Command tokens appearing in the first column of the Quick Reference table."""
    lines = ORCHESTRATOR.read_text(encoding="utf-8").splitlines()
    commands = set()
    in_section = False
    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            in_section = line.strip() == "## Quick Reference"
            continue
        if in_section and line.startswith("|"):
            first_cell = line.split("|")[1]
            match = COMMAND_CELL.search(first_cell)
            if match:
                commands.add(match.group(1))
    return commands


def extension_commands():
    """Command tokens for every optional extension that installs its own sub-skill."""
    return {path.parent.name[len("seo-"):]
            for path in REPO.glob("extensions/*/skills/seo-*/SKILL.md")}


def test_quick_reference_table_parses():
    commands = quick_reference_commands()
    assert {"audit", "page", "technical"} <= commands, (
        "Quick Reference table not found or not parseable in skills/seo/SKILL.md"
    )


def test_every_extension_command_has_a_quick_reference_row():
    expected = extension_commands()
    assert expected, "no extension sub-skills discovered under extensions/*/skills/"
    missing = sorted(expected - quick_reference_commands())
    assert missing == [], (
        "extension commands missing from the /seo Quick Reference table: "
        + ", ".join(f"/seo {cmd}" for cmd in missing)
    )


def test_extension_rows_are_marked_as_extensions():
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    unmarked = []
    for cmd in sorted(extension_commands()):
        row = re.search(rf"^\|\s*`/seo {re.escape(cmd)}\b.*$", text, re.MULTILINE)
        if row and "(extension)" not in row.group(0):
            unmarked.append(cmd)
    assert unmarked == [], (
        "extension rows must be labelled `(extension)`: " + ", ".join(unmarked)
    )
