"""
Tests for the v2 Checkpoint 5 deliverables:
    scripts/parasite_risk.py
    extensions/<name>/  (structure check for all 5 new extensions)
    skills/seo-geo/references/llmstxt-evidence.md  (evidence file exists)
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import parasite_risk  # noqa: E402


# ---------------------------------------------------------------------------
# parasite_risk
# ---------------------------------------------------------------------------


def _row(url: str, *, third=0, commerce=0, affiliate=0) -> dict:
    return {
        "url": url,
        "third_party_hits": third,
        "commerce_hits": commerce,
        "affiliate_link_hits": affiliate,
    }


def test_subfolder_extraction() -> None:
    assert parasite_risk._subfolder("https://news.example.com/reviews/x") == "/reviews/"
    assert parasite_risk._subfolder("https://news.example.com/") == "/"
    assert parasite_risk._subfolder("https://news.example.com") == "/"


def test_classify_flags_high_risk_review_section() -> None:
    rows = [
        _row("https://news.example.com/reviews/a", commerce=5, affiliate=12),
        _row("https://news.example.com/reviews/b", commerce=6, affiliate=14),
        _row("https://news.example.com/world/u", commerce=0, affiliate=0),
    ]
    report = parasite_risk._classify(rows)
    assert report["/reviews/"]["risk"] == "high"
    assert "commercial-intent-skew" in report["/reviews/"]["flags"]
    assert "affiliate-density" in report["/reviews/"]["flags"]
    assert report["/world/"]["risk"] == "low"


def test_classify_flags_high_on_third_party_authorship() -> None:
    rows = [
        _row("https://example.com/partner/a", third=2),
        _row("https://example.com/partner/b", third=3),
    ]
    report = parasite_risk._classify(rows)
    assert report["/partner/"]["risk"] == "high"
    assert "third-party-authorship-density" in report["/partner/"]["flags"]


def test_classify_drift_detection() -> None:
    rows = [
        _row("https://example.com/news/a", commerce=0),
        _row("https://example.com/news/b", commerce=0),
        _row("https://example.com/about/x", commerce=0),
        _row("https://example.com/contact/y", commerce=0),
        _row("https://example.com/deals/p", commerce=1),  # below 2.0 absolute
    ]
    report = parasite_risk._classify(rows)
    assert "commercial-intent-drift" in report["/deals/"]["flags"]
    # Drift bumps a low-risk section to medium even when its absolute
    # commerce rate is below the 2.0 hard threshold (1.0 here vs. the
    # 0.25 site-wide mean = 4x mean drift).
    assert report["/deals/"]["risk"] in ("medium", "high")


def test_audit_page_counts_pattern_hits() -> None:
    html = (
        "<p>Partner Content from Acme</p>"
        "<a href='https://amzn.to/3xyz?tag=aff123'>Buy Now</a>"
        "<a href='https://example.com/x?utm_source=affil'>compare prices</a>"
    )
    row = parasite_risk._audit_page("https://x.example/", html)
    assert row["third_party_hits"] >= 1
    assert row["commerce_hits"] >= 1
    assert row["affiliate_link_hits"] >= 1


# ---------------------------------------------------------------------------
# Extension structural integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,skill_dir",
    [
        ("ahrefs", "seo-ahrefs"),
        ("seranking", "seo-seranking"),
        ("profound", "seo-profound"),
        ("bing-webmaster", "seo-bing"),
        ("unlighthouse", "seo-unlighthouse"),
    ],
)
def test_extension_has_install_skill_and_docs(name: str, skill_dir: str) -> None:
    base = _REPO_ROOT / "extensions" / name
    assert (base / "install.sh").is_file(), f"{name}/install.sh missing"
    assert (base / "install.ps1").is_file(), f"{name}/install.ps1 missing"
    assert (base / "skills" / skill_dir / "SKILL.md").is_file(), (
        f"{name}/skills/{skill_dir}/SKILL.md missing"
    )
    assert (base / "uninstall.sh").is_file(), f"{name}/uninstall.sh missing"
    docs_dir = base / "docs"
    assert docs_dir.is_dir(), f"{name}/docs/ missing"
    # At least one *-SETUP.md file in docs.
    assert any(p.suffix == ".md" for p in docs_dir.iterdir()), (
        f"{name}/docs/ has no Markdown file"
    )


@pytest.mark.parametrize(
    "name", ["ahrefs", "seranking", "profound", "bing-webmaster", "unlighthouse"],
)
def test_extension_install_script_is_executable(name: str) -> None:
    install = _REPO_ROOT / "extensions" / name / "install.sh"
    mode = install.stat().st_mode
    assert mode & stat.S_IXUSR, f"{name}/install.sh must be executable for chmod"


def test_every_extension_install_and_uninstall_is_executable() -> None:
    """All extensions ship executable install.sh + uninstall.sh — including v1 ones."""
    ext_root = _REPO_ROOT / "extensions"
    failures = []
    for ext in sorted(p for p in ext_root.iterdir() if p.is_dir()):
        for script_name in ("install.sh", "uninstall.sh"):
            script = ext / script_name
            if not script.exists():
                continue
            mode = script.stat().st_mode
            if not (mode & stat.S_IXUSR):
                failures.append(f"{ext.name}/{script_name}")
    assert not failures, (
        "Extension scripts missing user-exec bit (chmod +x):\n  "
        + "\n  ".join(failures)
    )


@pytest.mark.parametrize(
    "name,skill_dir",
    [
        ("ahrefs", "seo-ahrefs"),
        ("seranking", "seo-seranking"),
        ("profound", "seo-profound"),
        ("bing-webmaster", "seo-bing"),
        ("unlighthouse", "seo-unlighthouse"),
    ],
)
def test_extension_skillmd_has_required_frontmatter(
    name: str, skill_dir: str,
) -> None:
    skillmd = (_REPO_ROOT / "extensions" / name / "skills"
               / skill_dir / "SKILL.md")
    text = skillmd.read_text(encoding="utf-8")
    head = text.split("---", 2)[1] if text.startswith("---") else ""
    assert f"name: {skill_dir}" in head, f"{name}: frontmatter name must be {skill_dir}"
    assert "description:" in head, f"{name}: missing description"
    assert "metadata:" in head, f"{name}: missing metadata block"
    import json as _json
    _expected = _json.loads(
        (_REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]
    assert f'version: "{_expected}"' in head, (
        f"{name}: SKILL.md must declare version {_expected} (from plugin.json)"
    )


# ---------------------------------------------------------------------------
# llms.txt evidence reference
# ---------------------------------------------------------------------------


def test_llmstxt_evidence_file_exists_and_cites_primary_sources() -> None:
    path = _REPO_ROOT / "skills" / "seo-geo" / "references" / "llmstxt-evidence.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for source in ("John Mueller", "Gary Illyes", "SE Ranking", "OtterlyAI"):
        assert source in text, f"evidence file must cite {source}"
    # Must explicitly state non-consumption.
    assert "not currently consumed" in text.lower() \
        or "no AI system" in text.lower()
