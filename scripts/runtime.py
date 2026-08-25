#!/usr/bin/env python3
"""Cross-platform runtime for Claude SEO's bundled Python scripts.

This module deliberately uses only the Python standard library. It is launched
by ``bin/claude-seo`` under a base Python, then dispatches work through the
managed virtual environment created by ``setup``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

RUNTIME_SCHEMA = 1
LOCK_STALE_SECONDS = 30 * 60
SCRIPT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.py$")
EXTENSION_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MANUAL_EXTENSION_SKILLS = {"banana": "seo-image-gen"}
ALLOWED_CORE_SCRIPTS = frozenset(
    {
        "agent_ux_check.py", "analyze_visual.py", "backlinks_auth.py",
        "bing_webmaster.py", "capture_screenshot.py", "commoncrawl_graph.py",
        "content_humanize.py", "content_quality.py", "content_verify.py",
        "crux_history.py", "dataforseo_costs.py", "dataforseo_merchant.py",
        "dataforseo_normalize.py", "domain_history.py", "drift_baseline.py",
        "drift_compare.py", "drift_history.py", "drift_report.py", "fetch_page.py",
        "ga4_report.py", "gbp_deprecation_lint.py", "google_auth.py",
        "google_report.py", "gsc_inspect.py", "gsc_query.py", "indexing_notify.py",
        "indexnow_submit.py", "iptc_ai_label.py", "keyword_planner.py",
        "lcp_subparts.py", "moz_api.py", "nlp_analyze.py", "pagespeed_check.py",
        "parasite_risk.py", "parse_html.py", "preload_check.py", "render_page.py",
        "portability_check.py", "consistency_check.py",
        "schema_ecommerce_validate.py", "schema_generate.py", "seo_updates.py",
        "sitemap_discovery.py", "sync_flow.py", "ucp_check.py", "unlighthouse_run.py",
        "url_safety.py", "validate_backlink_report.py", "verify_backlinks.py",
        "youtube_search.py",
    }
)
REDACTIONS = (
    (re.compile(r"(?i)(https?://[^\s:/]+:)[^@\s]+@"), r"\1<redacted>@"),
    (re.compile(r"(?i)(https?://[^\s?]+\?)[^\s]+"), r"\1<redacted>"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<redacted-email>"),
    (re.compile(r"(?i)(token|password|secret|api[_-]?key)([=:\s]+)[^\s]+"), r"\1\2<redacted>"),
)


def _configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _plugin_version(root: Path) -> str:
    for manifest in (root / ".claude-plugin" / "plugin.json", root / "runtime-plugin.json"):
        try:
            value = json.loads(manifest.read_text(encoding="utf-8")).get("version")
            if isinstance(value, str):
                return value
        except (OSError, ValueError):
            pass
    metadata = root / "pyproject.toml"
    try:
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', metadata.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    except OSError:
        pass
    return "unknown"


def _requirements_hash(root: Path) -> str:
    try:
        content = (root / "requirements.txt").read_bytes()
    except OSError:
        return "missing"
    return hashlib.sha256(content).hexdigest()


def _is_plugin(root: Path) -> bool:
    if os.environ.get("CLAUDE_PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return True
    return (root / ".claude-plugin" / "plugin.json").is_file() and not (root / ".git").exists()


def _configured_data_dir(raw: str) -> Path:
    """Resolve a configured data directory and reject destructive broad roots."""
    candidate = Path(raw).expanduser().resolve()
    filesystem_root = Path(candidate.anchor).resolve()
    try:
        user_home = Path.home().resolve()
    except RuntimeError:
        user_home = None
    if candidate == filesystem_root or candidate == user_home:
        raise ValueError("runtime data directory must be a dedicated subdirectory")
    return candidate


def _data_dir(root: Path) -> tuple[Path, str]:
    override = os.environ.get("CLAUDE_SEO_DATA_DIR")
    if override:
        return _configured_data_dir(override), "override"
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return _configured_data_dir(plugin_data), "plugin"
    if _is_plugin(root):
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return (base / "claude-seo").resolve(), "plugin-fallback"
    return root, "manual"


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _state_path(data_dir: Path) -> Path:
    return data_dir / "runtime-state.json"


def _load_state(data_dir: Path) -> dict[str, Any]:
    try:
        value = json.loads(_state_path(data_dir).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _expected(root: Path) -> dict[str, Any]:
    return {
        "runtime_schema": RUNTIME_SCHEMA,
        "plugin_version": _plugin_version(root),
        "requirements_sha256": _requirements_hash(root),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
    }


def _status(root: Path) -> dict[str, Any]:
    data_dir, mode = _data_dir(root)
    venv = data_dir / ".venv"
    python = _venv_python(venv)
    state = _load_state(data_dir)
    expected = _expected(root)
    reasons: list[str] = []
    if not python.is_file():
        reasons.append("managed environment is missing")
    for key in ("runtime_schema", "requirements_sha256", "python"):
        if state.get(key) != expected[key]:
            reasons.append(f"{key} changed")
    browser_dir = data_dir / "ms-playwright"
    try:
        browser_installed = browser_dir.is_dir() and any(
            child.name.startswith(("chromium-", "chromium_headless_shell-"))
            for child in browser_dir.iterdir()
        )
    except OSError:
        browser_installed = False
    return {
        "ready": not reasons,
        "mode": mode,
        "python_version": expected["python"],
        "plugin_version": expected["plugin_version"],
        "browser_ready": bool(state.get("browser_ready")) and browser_installed,
        "reasons": reasons,
        "data_dir": data_dir,
        "venv": venv,
        "python_path": python,
        "state": state,
        "expected": expected,
    }


def _safe_env(status: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(status["data_dir"] / "ms-playwright")
    return env


def _redact(text: str) -> str:
    try:
        home = str(Path.home())
        if home:
            text = text.replace(home, "<home>")
    except RuntimeError:
        pass
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def _run_checked(
    argv: list[str], *, env: dict[str, str], stage: str
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"{stage} failed with exit code {result.returncode}")
    return result


class SetupLock:
    def __init__(self, path: Path):
        self.path = path

    def __enter__(self) -> "SetupLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("x", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()}\n{int(time.time())}\n")
        except FileExistsError:
            try:
                age = time.time() - self.path.stat().st_mtime
            except OSError:
                age = 0
            if age <= LOCK_STALE_SECONDS:
                raise RuntimeError("another Claude SEO setup is already running")
            self.path.unlink(missing_ok=True)
            with self.path.open("x", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()}\n{int(time.time())}\n")
        return self

    def __exit__(self, *_: object) -> None:
        self.path.unlink(missing_ok=True)


def command_setup(args: argparse.Namespace) -> int:
    root = _root()
    status = _status(root)
    data_dir: Path = status["data_dir"]
    final_venv: Path = status["venv"]
    staged = data_dir / f".venv.next-{os.getpid()}"
    backup = data_dir / ".venv.previous"
    temp_state = data_dir / ".runtime-state.next"
    shutil.rmtree(staged, ignore_errors=True)
    env = _safe_env(status)
    browser_ready = False
    previous_moved = False
    swapped = False
    committed = False
    had_previous = final_venv.exists()
    try:
        with SetupLock(data_dir / ".setup.lock"):
            print("Creating isolated Claude SEO environment...")
            _run_checked([sys.executable, "-m", "venv", str(staged)], env=env, stage="virtual environment creation")
            staged_python = _venv_python(staged)
            _run_checked(
                [str(staged_python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(root / "requirements.txt")],
                env=env,
                stage="dependency installation",
            )
            if not args.skip_browser:
                try:
                    _run_checked(
                        [str(staged_python), "-m", "playwright", "install", "chromium"],
                        env=env,
                        stage="Chromium installation",
                    )
                    browser_ready = True
                except RuntimeError as exc:
                    print(f"Browser setup incomplete: {exc}", file=sys.stderr)
            _run_checked(
                [
                    str(staged_python),
                    "-c",
                    "import bs4, lxml, lxml_html_clean, playwright, requests, trafilatura",
                ],
                env=env,
                stage="runtime import validation",
            )
            shutil.rmtree(backup, ignore_errors=True)
            if final_venv.exists():
                final_venv.replace(backup)
                previous_moved = True
            staged.replace(final_venv)
            swapped = True
            state = dict(status["expected"])
            state["browser_ready"] = browser_ready
            temp_state.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temp_state.replace(_state_path(data_dir))
            committed = True
            shutil.rmtree(backup, ignore_errors=True)
    except (OSError, RuntimeError) as exc:
        shutil.rmtree(staged, ignore_errors=True)
        temp_state.unlink(missing_ok=True)
        if not committed:
            if swapped:
                shutil.rmtree(final_venv, ignore_errors=True)
            if previous_moved and had_previous and backup.exists():
                backup.replace(final_venv)
        print(f"Claude SEO setup failed: {_redact(str(exc))}", file=sys.stderr)
        return 1
    if browser_ready or args.skip_browser:
        print("Claude SEO runtime is ready.")
        return 0
    print("Core runtime is ready, but Chromium is unavailable. Run setup again to enable rendered-page features.", file=sys.stderr)
    return 10


def _resolve_script(root: Path, name: str, extension: str | None) -> Path:
    if not SCRIPT_NAME_RE.fullmatch(name):
        raise ValueError("script must be a bundled Python script basename")
    if extension:
        if not EXTENSION_NAME_RE.fullmatch(extension):
            raise ValueError("invalid extension name")
        scripts_dir = root / "extensions" / extension / "scripts"
        if not scripts_dir.is_dir() and extension in MANUAL_EXTENSION_SKILLS:
            scripts_dir = root.parent / MANUAL_EXTENSION_SKILLS[extension] / "scripts"
    else:
        if name not in ALLOWED_CORE_SCRIPTS:
            raise ValueError("script is not in the bundled runtime allowlist")
        scripts_dir = root / "scripts"
    candidate = (scripts_dir / name).resolve()
    scripts_root = scripts_dir.resolve()
    if candidate.parent != scripts_root or not candidate.is_file() or candidate == Path(__file__).resolve():
        raise ValueError("script is not in the bundled runtime allowlist")
    return candidate


def command_run(args: argparse.Namespace) -> int:
    root = _root()
    try:
        script = _resolve_script(root, args.script, args.extension)
    except ValueError as exc:
        print(f"Claude SEO runtime: {exc}", file=sys.stderr)
        return 2
    status = _status(root)
    if not status["ready"]:
        print("Claude SEO runtime is not ready. Run `/seo setup` and retry.", file=sys.stderr)
        return 3
    result = subprocess.run(
        [str(status["python_path"]), str(script), *args.script_args],
        env=_safe_env(status),
    )
    if result.returncode < 0:
        os.kill(os.getpid(), -result.returncode)
        return 128 + (-result.returncode)
    return result.returncode


def command_doctor(args: argparse.Namespace) -> int:
    status = _status(_root())
    public = {
        "ready": status["ready"],
        "mode": status["mode"],
        "plugin_version": status["plugin_version"],
        "python_version": status["python_version"],
        "browser_ready": status["browser_ready"],
        "reasons": status["reasons"],
    }
    if args.json:
        print(json.dumps(public, indent=2, sort_keys=True))
    else:
        print(f"Runtime: {'ready' if public['ready'] else 'setup required'}")
        print(f"Install mode: {public['mode']}")
        print(f"Python: {public['python_version']}")
        print(f"Chromium: {'ready' if public['browser_ready'] else 'not installed'}")
        for reason in public["reasons"]:
            print(f"Reason: {reason}")
    return 0 if status["ready"] else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claude-seo", description="Claude SEO managed Python runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup", help="create or refresh the isolated runtime")
    setup.add_argument("--skip-browser", action="store_true")
    setup.set_defaults(func=command_setup)
    doctor = sub.add_parser("doctor", help="check runtime readiness without changing it")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=command_doctor)
    run = sub.add_parser("run", help="run one bundled Python script")
    run.add_argument("--extension")
    run.add_argument("script")
    run.add_argument("script_args", nargs=argparse.REMAINDER)
    run.set_defaults(func=command_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_utf8()
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Claude SEO runtime failed: {_redact(str(exc))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
