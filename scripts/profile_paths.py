#!/usr/bin/env python3
"""Directory that holds claude-seo's credentials and properties.

CLAUDE_SEO_PROFILE_DIR points google_auth.py, backlinks_auth.py and
matomo_auth.py at one project's google-api.json, oauth-token.json,
backlinks-api.json and matomo.json. Unset or empty, they use
~/.config/claude-seo. A set profile is never combined with the default
directory. The DataForSEO budget files do not follow it: they stay global
so that several projects cannot each spend the daily limit of one account.
A set profile inside a git work tree prints a warning on stderr, because
its credentials would be one `git add` away from a commit.

Usage:
    python profile_paths.py        # {"profile_dir": "<resolved directory>"}
"""

from __future__ import annotations

import enum
import functools
import json
import os
import sys
from pathlib import Path

ENV_VAR = "CLAUDE_SEO_PROFILE_DIR"
_NOT_ABSOLUTE = ENV_VAR + " must be an absolute path or start with ~/, got {raw!r}"


def profile_dir() -> Path:
    """The configured profile directory, or the default one.

    Raises:
        ValueError: the value is relative (it would depend on the working
            directory), starts with a ~ that names no home directory (such
            as ~.config/x or ~root/x, read as ~user), cannot be resolved
            (such as a symlink loop), or is the filesystem root or the
            home directory.
    """
    raw = os.environ.get(ENV_VAR, "")
    if not raw:
        return Path(os.path.expanduser("~")) / ".config" / "claude-seo"
    if raw.startswith("~") and raw[1:2] not in ("", "/", "\\"):
        raise ValueError(_NOT_ABSOLUTE.format(raw=raw))
    try:
        expanded = Path(raw).expanduser()
    except (RuntimeError, KeyError) as exc:
        raise ValueError(_NOT_ABSOLUTE.format(raw=raw)) from exc
    if not expanded.is_absolute():
        raise ValueError(_NOT_ABSOLUTE.format(raw=raw))
    try:
        candidate = expanded.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"{ENV_VAR} cannot be resolved, got {raw!r}") from exc
    if candidate == Path(candidate.anchor).resolve() or _is_home(candidate, _resolved_home()):
        raise ValueError(f"{ENV_VAR} must name a dedicated directory, not {raw!r}")
    return candidate


def profile_dir_or_exit() -> Path:
    """profile_dir() for module import: a rejected value ends the process
    with code 1 and a one-line message, never with a traceback, so a
    misconfigured profile cannot fall back to the default credentials.
    A set profile inside a git work tree prints a warning on stderr."""
    try:
        directory = profile_dir()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if os.environ.get(ENV_VAR):
        _warn_if_in_git_work_tree(directory)
    return directory


def describe_config_dir(config_path: str) -> str:
    """The directory of config_path for --check output, marked when it is
    missing or is a file, so a typo in the profile path is visible."""
    directory = Path(config_path).parent
    return f"{directory}{_dir_state(directory).value}"


def config_dir_fields(config_path: str) -> dict[str, str | bool]:
    """The --check --json fields for the directory of config_path."""
    directory = Path(config_path).parent
    return {
        "config_dir": str(directory),
        "config_dir_exists": _dir_state(directory) is _DirState.OK,
        "config_dir_in_git_work_tree": _git_work_tree(directory) is not None,
    }


class _DirState(enum.Enum):
    OK = ""
    MISSING = " (does not exist)"
    NOT_A_DIRECTORY = " (not a directory)"
    NOT_ACCESSIBLE = " (not accessible)"


def _dir_state(directory: Path) -> _DirState:
    try:
        if not directory.exists():
            return _DirState.MISSING
        if not directory.is_dir():
            return _DirState.NOT_A_DIRECTORY
    except OSError:
        return _DirState.NOT_ACCESSIBLE
    return _DirState.OK


@functools.cache
def _warn_if_in_git_work_tree(directory: Path) -> None:
    """Cached so a script that loads several auth modules warns once."""
    work_tree = _git_work_tree(directory)
    if work_tree is not None:
        print(
            f"Warning: {ENV_VAR} {directory} is inside the git work tree {work_tree}. "
            "Its API keys and OAuth token are one `git add` away from a commit; "
            "move the profile outside the repository.",
            file=sys.stderr,
        )


def _git_work_tree(directory: Path) -> Path | None:
    """The nearest ancestor holding .git, a directory in a normal checkout
    and a file in a linked worktree or submodule. Found without running
    git, which may be missing, and before the profile directory exists."""
    for candidate in (directory, *directory.parents):
        try:
            if (candidate / ".git").exists():
                return candidate
        except OSError:
            continue
    return None


def _resolved_home() -> Path | None:
    try:
        return Path.home().resolve()
    except (OSError, RuntimeError, KeyError):
        return None


def _is_home(candidate: Path, home: Path | None) -> bool:
    if home is None:
        return False
    if candidate == home:
        return True
    try:
        return os.path.samefile(candidate, home)
    except OSError:
        return False


def main() -> int:
    print(json.dumps({"profile_dir": str(profile_dir_or_exit())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
