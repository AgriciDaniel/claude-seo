#!/usr/bin/env python3
"""Repository consistency checker: dead references, orphans, routing, lock integrity.

Complements tests/test_manifest_consistency.py (counts and version triangulation) with
reference-graph checks that no other tool covers:

1. ``references/X`` mentions in SKILL.md and agent files resolve via the fallback chain
   own dir -> shared ``skills/seo/references/`` -> any skill's references dir (cross-skill
   resolutions are reported as info, dead ones as errors).
2. ``research/X.md`` path mentions exist.
3. ``scripts/X.py`` mentions resolve PATH-AWARE: repo-root ``scripts/`` first, then the
   enclosing extension's ``scripts/`` dir for files under ``extensions/<name>/``. A bare
   basename existing somewhere else in the tree does NOT count (this exact bug hid dead
   ``scripts/presets.py`` invocations before the 2026-07 full review).
4. Routing tables in ``skills/seo/SKILL.md`` and ``docs/COMMANDS.md`` agree with each
   other and with the skill directories on disk.
5. ``agents/<name>.md`` path mentions exist (``seo-newagent`` doc example whitelisted).
6. ``skills/seo-flow/references/flow-prompts.lock`` SHA-256 integrity.
7. Orphan-file candidates (tracked files whose basename is mentioned nowhere else);
   reported as warnings, never errors.

Usage:
    python3 scripts/consistency_check.py [--json] [--strict]

Exit codes: 0 = no errors (warnings allowed unless --strict), 1 = errors found.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ORPHAN_SCRIPT_WHITELIST = {
    "portability_check.py", "agent_ux_check.py", "gbp_deprecation_lint.py",
    "release_sign.py", "verify_release.py", "consistency_check.py",
}
GENERIC_BASENAMES = {"README.md", "SKILL.md", "__init__.py", "LICENSE", "LICENSE.txt",
                     "plugin.json", "marketplace.json", "hooks.json"}
DOC_EXAMPLE_AGENTS = {"seo-newagent"}
LOCK_PATH = "skills/seo-flow/references/flow-prompts.lock"


def tracked_files():
    out = subprocess.run(["git", "-C", REPO, "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l.strip()]


def read(rel, _cache={}):
    if rel not in _cache:
        try:
            with open(os.path.join(REPO, rel), encoding="utf-8", errors="replace") as fh:
                _cache[rel] = fh.read()
        except OSError:
            _cache[rel] = ""
    return _cache[rel]


def extension_root(rel):
    m = re.match(r"(extensions/[^/]+)/", rel)
    return m.group(1) if m else None


def check_references(files, md):
    ref_pat = re.compile(r'references/([A-Za-z0-9_\-./]+\.(?:md|html|json|txt|ya?ml))')
    errors, infos = [], []
    carriers = [f for f in md if (f.startswith(("skills/", "extensions/")) and f.endswith("SKILL.md"))
                or f.startswith("agents/")]
    for f in carriers:
        base = os.path.dirname(f)
        for m in sorted(set(ref_pat.findall(read(f)))):
            candidates = [os.path.join(base, "references", m),
                          os.path.join("skills/seo/references", m)]
            if any(os.path.exists(os.path.join(REPO, c)) for c in candidates):
                continue
            hits = (glob.glob(os.path.join(REPO, "skills", "*", "references", m))
                    + glob.glob(os.path.join(REPO, "extensions", "*", "skills", "*", "references", m)))
            if hits:
                infos.append(f"{f}: references/{m} resolves cross-skill to "
                             f"{os.path.relpath(hits[0], REPO)}")
            else:
                errors.append(f"{f}: dead reference references/{m}")
    return errors, infos


SELF_DOC = {"scripts/consistency_check.py", "tests/test_consistency_check.py"}


def check_research_refs(files, texts):
    pat = re.compile(r'research/([A-Za-z0-9_\-]+\.md)')
    errors = []
    for f in texts:
        if f in SELF_DOC:
            continue
        for m in sorted(set(pat.findall(read(f)))):
            if not os.path.exists(os.path.join(REPO, "research", m)):
                errors.append(f"{f}: dead research ref research/{m}")
    return errors


def check_script_refs(files, texts):
    """Path-aware: scripts/X.py must exist at repo scripts/ or the enclosing extension's.

    The lookbehind skips path-qualified mentions such as
    ``extensions/banana/scripts/edit.py`` (checked via their own full path elsewhere).
    ``research/`` notes, ``CHANGELOG.md``, and ``.github/`` templates are
    historical/example carriers.
    """
    pat = re.compile(r'(?<![\w/])scripts/([A-Za-z0-9_]+\.py)\b')
    errors = []
    mentioned = set()
    for f in texts:
        if f.startswith(("research/", ".github/")) or f == "CHANGELOG.md" or f in SELF_DOC:
            continue
        ext_root = extension_root(f)
        for m in sorted(set(pat.findall(read(f)))):
            mentioned.add(m)
            candidates = [f"scripts/{m}"]
            if ext_root:
                candidates.insert(0, f"{ext_root}/scripts/{m}")
            if not any(c in files for c in candidates):
                errors.append(f"{f}: dead script ref scripts/{m} "
                              f"(checked: {', '.join(candidates)})")
    orphans = []
    all_text = "\n".join(read(f) for f in texts)
    for s in sorted(os.path.basename(f) for f in files
                    if f.startswith("scripts/") and f.endswith(".py")):
        if s in ORPHAN_SCRIPT_WHITELIST:
            continue
        others = all_text.count(s) - read(f"scripts/{s}").count(s)
        if others <= 0:
            orphans.append(f"scripts/{s}: referenced nowhere outside itself")
    return errors, orphans


def check_routing(files):
    cmd_pat = re.compile(r'`/seo(?:\s+([a-z][a-z0-9-]*))?')
    tables = {src: {m for m in cmd_pat.findall(read(src)) if m}
              for src in ("skills/seo/SKILL.md", "docs/COMMANDS.md")}
    skill_tokens = {d.split("/")[1][4:] for d in files
                    if d.startswith("skills/seo-") and d.endswith("SKILL.md")}
    ext_tokens = {p.split("/")[3][4:] for p in files
                  if re.match(r'extensions/[^/]+/skills/seo-[^/]+/SKILL\.md$', p)}
    known = skill_tokens | ext_tokens
    a, b = tables["skills/seo/SKILL.md"], tables["docs/COMMANDS.md"]
    errors = []
    for c in sorted(a - b):
        errors.append(f"routing: `/seo {c}` in orchestrator but not docs/COMMANDS.md")
    for c in sorted(b - a):
        errors.append(f"routing: `/seo {c}` in docs/COMMANDS.md but not orchestrator")
    for c in sorted((a | b) - known):
        errors.append(f"routing: `/seo {c}` has no matching skill directory")
    return errors


def check_agent_refs(files, texts):
    agents = {os.path.basename(f)[:-3] for f in files
              if f.startswith("agents/") and f.endswith(".md")}
    pat = re.compile(r'agents/([a-z0-9-]+)\.md')
    errors = []
    for f in texts:
        if f.startswith("agents/"):
            continue
        for m in sorted(set(pat.findall(read(f)))):
            if m not in agents and m not in DOC_EXAMPLE_AGENTS:
                errors.append(f"{f}: dead agent ref agents/{m}.md")
    return errors


def check_flow_lock(files):
    errors = []
    locked = {}
    for line in read(LOCK_PATH).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 2:
            locked[parts[1]] = parts[0]
    for rel, want in locked.items():
        full = os.path.join(REPO, rel)
        if not os.path.exists(full):
            errors.append(f"flow lock: missing {rel}")
            continue
        with open(full, "rb") as fh:
            got = hashlib.sha256(fh.read()).hexdigest()
        if got != want:
            errors.append(f"flow lock: hash mismatch {rel}")
    extra = {f for f in files
             if f.startswith("skills/seo-flow/references/prompts/") and f.endswith(".md")} - set(locked)
    for rel in sorted(extra):
        errors.append(f"flow lock: unlocked prompt file {rel}")
    return errors


def check_orphan_files(files, texts):
    warnings = []
    prefixes = ("skills/", "docs/", "research/", "data/", "schema/")
    corpus = {f: read(f) for f in texts}
    for f in files:
        if not f.startswith(prefixes):
            continue
        base = os.path.basename(f)
        if base in GENERIC_BASENAMES or f.startswith("skills/seo-flow/references/prompts/"):
            continue
        if not any(base in c for other, c in corpus.items() if other != f):
            warnings.append(f"orphan candidate: {f}")
    return warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    args = ap.parse_args()

    files = tracked_files()
    fileset = set(files)
    md = [f for f in files if f.endswith(".md")]
    texts = [f for f in files if f.endswith((".md", ".json", ".yaml", ".yml", ".toml",
                                             ".py", ".sh", ".ps1", ".cff", ".txt", ".html"))]

    ref_errors, ref_infos = check_references(fileset, md)
    script_errors, script_orphans = check_script_refs(fileset, texts)
    errors = (ref_errors + check_research_refs(fileset, texts) + script_errors
              + check_routing(fileset) + check_agent_refs(fileset, texts)
              + check_flow_lock(fileset))
    warnings = script_orphans + check_orphan_files(fileset, texts)
    result = {"errors": errors, "warnings": warnings, "info": ref_infos,
              "files_checked": len(files),
              "status": "FAIL" if errors or (args.strict and warnings) else "PASS"}

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for e in errors:
            print(f"ERROR: {e}")
        for w in warnings:
            print(f"WARN:  {w}")
        print(f"{result['status']}: {len(errors)} errors, {len(warnings)} warnings, "
              f"{len(ref_infos)} cross-skill infos, {len(files)} files")
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
