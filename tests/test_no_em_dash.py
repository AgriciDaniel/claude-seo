"""House-style gate: no em dash (U+2014) in the shipped instruction/code surface.

The 2026-09-28 house-style pass removed every em dash from skills/, agents/,
scripts/, schema/, data/, extensions/, docs/, README.md, CLAUDE.md and
AGENTS.md, rewriting each into plain punctuation (comma, period, colon,
parentheses or conjunction) so the codebase reads consistently. This test is
the regression gate: it fails if a future edit reintroduces one.

Two kinds of exception exist:

1. Paths that are synced upstream and hash-locked (skills/seo-flow/references/
   prompts/** and skills/seo-flow/references/flow-prompts.lock). Those files
   are never touched by this house-style rule.
2. A small allowlist of occurrences that are functional, not stylistic: a
   character class in a regex that detects or strips em dashes, and one
   generated-file header string that must keep matching the (excluded,
   hash-locked) lock file it writes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# U+2014 EM DASH, written as an escape so this file itself carries no literal
# em dash character.
EM_DASH = "\u2014"
EN_DASH = "\u2013"
# Escaped forms that still render an em dash in generated HTML, PDF or text.
ESCAPED_FORMS = ("&mdash;", "&#8212;", "\\u2014")

TARGET_PREFIXES = (
    "skills/",
    "agents/",
    "scripts/",
    "schema/",
    "data/",
    "extensions/",
    "docs/",
)
TARGET_FILES = {"README.md", "CLAUDE.md", "AGENTS.md"}

EXCLUDED_PREFIXES = ("skills/seo-flow/references/prompts/",)
EXCLUDED_FILES = {"skills/seo-flow/references/flow-prompts.lock"}

# (relative path, exact line content) pairs that are allowed to keep an em
# dash because it is functional, not prose.
ALLOWLIST = {
    (
        "scripts/metadata_template.py",
        '_BRAND_SEPARATOR_RE = re.compile(r"\\s[|' + EN_DASH + EM_DASH + '-]\\s")',
    ),
    (
        "scripts/metadata_template.py",
        '    return description[len(core):].strip(" -' + EN_DASH + EM_DASH + ':|.")',
    ),
    (
        "scripts/sync_flow.py",
        '        "# flow-prompts.lock ' + EM_DASH + ' SHA-256 baseline for synced FLOW prompts",',
    ),
}


def _tracked_target_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    files = []
    for rel in out:
        if rel in TARGET_FILES:
            files.append(rel)
            continue
        if not rel.startswith(TARGET_PREFIXES):
            continue
        if rel in EXCLUDED_FILES or any(rel.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        files.append(rel)
    return files


def test_no_em_dash_in_tracked_target_files() -> None:
    hits = []
    for rel in _tracked_target_files():
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if EM_DASH not in line and not any(form in line for form in ESCAPED_FORMS):
                continue
            if (rel, line) in ALLOWLIST:
                continue
            hits.append(f"{rel}:{lineno}: {line.strip()}")

    assert not hits, "em dash (U+2014, or an escape that renders one) found outside the allowlist:\n" + "\n".join(hits)


def test_allowlist_entries_still_present() -> None:
    """Guard against the allowlist going stale (entries that no longer exist)."""
    missing = []
    for rel, line in ALLOWLIST:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        if line not in text.splitlines():
            missing.append(f"{rel}: {line!r}")
    assert not missing, "allowlisted line(s) no longer found, update ALLOWLIST:\n" + "\n".join(missing)


def test_excluded_paths_are_still_excluded_for_a_reason() -> None:
    """The FLOW prompt mirror is upstream-synced and hash-locked; sanity-check it exists."""
    lock = ROOT / "skills/seo-flow/references/flow-prompts.lock"
    prompts_dir = ROOT / "skills/seo-flow/references/prompts"
    assert lock.exists(), "flow-prompts.lock should exist; if it was removed, drop the exclusion too"
    assert prompts_dir.is_dir(), "seo-flow prompts mirror should exist; if it was removed, drop the exclusion too"
