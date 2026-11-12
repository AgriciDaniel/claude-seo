#!/usr/bin/env python3
"""Verify that the installed OpenCode sees this repository's adapter.

Checks the skill registry, the generated subagent wrappers, and the /seo
command against the real OpenCode runtime. Exits 0 on success, 1 on an
assertion failure, and 2 when OpenCode is missing or is not version 2.
"""

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from build_agents import discover_agents

ROOT = Path(__file__).resolve().parents[2]
VERSION_RE = re.compile(r"\bv?(\d+)\.(\d+)\.(\d+)\b")
SKILL_RETRIES = 3
RETRY_SLEEP_SECONDS = 2


def fail(message: str) -> None:
    print(f"fail: {message}")


def ok(message: str) -> None:
    print(f"ok: {message}")


def run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def payload_of(raw: str) -> object:
    data = json.loads(raw)
    if isinstance(data, dict):
        return data.get("data", data)
    return data


def api_get(path: str) -> object:
    result = run(
        [
            "opencode",
            "api",
            "GET",
            path,
            "-H",
            f"x-opencode-directory: {ROOT}",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"opencode api {path} failed: {result.stderr.strip()}")
    return payload_of(result.stdout)


def record_id(record: dict[str, object]) -> object:
    return record.get("id", record.get("name"))


def check_version() -> int | None:
    result = run(["opencode", "--version"], timeout=30)
    match = VERSION_RE.search(result.stdout + result.stderr)
    if result.returncode != 0 or match is None:
        fail(f"cannot parse the OpenCode version: {result.stdout.strip()!r}")
        return None
    major = int(match.group(1))
    version = ".".join(match.groups())
    if major != 2:
        fail(f"OpenCode {version} is not version 2")
        return None
    ok(f"opencode {version}")
    return major


def check_skills() -> bool:
    core_skill_ids = sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))
    records: list[dict[str, object]] = []
    for attempt in range(1, SKILL_RETRIES + 1):
        raw = api_get("/api/skill")
        records = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        if records:
            break
        if attempt < SKILL_RETRIES:
            time.sleep(RETRY_SLEEP_SECONDS)
    if not records:
        fail(
            "skill registry is empty; location not loaded, restart OpenCode at the repository root"
        )
        return False
    present = {record_id(record) for record in records}
    missing = sorted(set(core_skill_ids) - present)
    if missing:
        fail(f"missing skills: {', '.join(missing)}")
        return False
    seo_record = next((record for record in records if record_id(record) == "seo"), None)
    seo_path = str(seo_record.get("path", "")) if seo_record else ""
    expected_path = str((ROOT / "skills" / "seo" / "SKILL.md").resolve())
    if not seo_path or Path(seo_path).resolve() != Path(expected_path):
        fail(f"seo skill resolves to {seo_path!r}, expected {expected_path!r}")
        return False
    ok(f"{len(core_skill_ids)} core skills, seo resolves to the checkout")
    return True


def _agent_records() -> list[dict[str, object]]:
    result = run(["opencode", "debug", "agents", "--standalone"])
    if result.returncode == 0:
        raw = payload_of(result.stdout)
        if isinstance(raw, list) and raw:
            return [item for item in raw if isinstance(item, dict)]
    raw = api_get("/api/agent")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def check_agents() -> bool:
    expected = {agent.id: agent.max_turns + 1 for agent in discover_agents(ROOT)}
    records = _agent_records()
    if not records:
        fail(
            "agent registry is empty; location not loaded, restart OpenCode at the repository root"
        )
        return False
    by_id = {record_id(record): record for record in records}
    problems: list[str] = []
    for agent_id, steps in sorted(expected.items()):
        record = by_id.get(agent_id)
        if record is None:
            problems.append(f"{agent_id} missing")
            continue
        if record.get("mode") != "subagent":
            problems.append(f"{agent_id} mode={record.get('mode')!r}")
            continue
        if record.get("steps") != steps:
            problems.append(f"{agent_id} steps={record.get('steps')!r}, expected {steps}")
    if problems:
        fail("agent problems: " + "; ".join(problems))
        return False
    ok(f"{len(expected)} subagents with mode=subagent and expected steps")
    return True


def check_commands() -> bool:
    raw = api_get("/api/command")
    records = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    if not records:
        fail(
            "command registry is empty; location not loaded, restart OpenCode at the repository root"
        )
        return False
    present = {record_id(record) for record in records}
    if "seo" not in present:
        fail("seo command missing")
        return False
    ok("seo command present")
    return True


def main() -> int:
    if shutil.which("opencode") is None:
        print("fail: opencode is not on PATH")
        return 2
    if check_version() is None:
        return 2
    checks = [check_skills, check_agents, check_commands]
    passed = True
    for check in checks:
        try:
            if not check():
                passed = False
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            fail(f"{check.__name__}: {exc}")
            passed = False
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
