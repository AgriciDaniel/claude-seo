from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_AUDIT_AGENTS: tuple[str, ...] = (
    "seo-technical",
    "seo-content",
    "seo-schema",
    "seo-sitemap",
    "seo-performance",
    "seo-visual",
    "seo-geo",
    "seo-sxo",
)


@dataclass(frozen=True)
class AgentTreeCheck:
    ok: bool
    missing: list[str]
    broken_symlinks: list[str]


def check_agent_tree(agent_dir: Path) -> AgentTreeCheck:
    missing: list[str] = []
    broken_symlinks: list[str] = []

    for name in REQUIRED_AUDIT_AGENTS:
        candidate = agent_dir / f"{name}.md"
        if candidate.is_symlink() and not candidate.exists():
            broken_symlinks.append(candidate.name)
            continue
        if not candidate.is_file():
            missing.append(candidate.name)

    return AgentTreeCheck(
        ok=not missing and not broken_symlinks,
        missing=missing,
        broken_symlinks=broken_symlinks,
    )
