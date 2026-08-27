"""Sync Flow operational references from GitHub into the seo-flow skill."""

import argparse
import base64
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.github.com/repos/AgriciDaniel/flow/contents"
_ALLOWED_HOST = "api.github.com"
_SIZE_LIMIT = 5 * 1024 * 1024  # 5 MB


def _validate_github_url(url):
    """Abort if url does not use HTTPS or does not target the expected GitHub API host."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != _ALLOWED_HOST:
        raise ValueError(f"Blocked request to unexpected host: {parsed.netloc!r} (scheme: {parsed.scheme!r})")


PROMPT_STAGES = ["find", "leverage", "optimize", "win", "local"]
STATIC_FILES = [
    ("docs/01-framework/flow-framework.md", "flow-framework.md"),
    ("docs/10-references/bibliography.md", "bibliography.md"),
]
LOCK_REL = pathlib.Path("skills") / "seo-flow" / "references" / "flow-prompts.lock"

# Map upstream FLOW doc paths (a numbered-folder layout) onto this plugin's
# flattened skills/seo-flow/references/ layout. A None value means the target is
# not shipped in this plugin, so the link is removed while its label text stays.
_FLOW_LINK_MAP = {
    "01-framework/flow-framework.md": "flow-framework.md",
    "10-references/bibliography.md": "bibliography.md",
    "00-START-HERE.md": "../SKILL.md",
    "06-win/dual-surface-scorecard.md": None,
    "06-win/bofu-and-conversion-content.md": None,
}
_FLOW_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")


def rewrite_flow_links(text, target_path, refs_dir):
    """Repoint upstream FLOW relative links onto this plugin's flattened layout.

    Synced bodies link to the upstream numbered-folder layout (01-framework/,
    10-references/, 06-win/) that does not exist here. Links whose target ships
    under references/ are repointed; links to non-shipped targets are unlinked
    (the human-readable label is kept) so no dead link survives the sync.
    """
    def _sub(match):
        label, href = match.group(1), match.group(2)
        for tail, local in _FLOW_LINK_MAP.items():
            if href.endswith(tail):
                if local is None:
                    return label
                rel = os.path.relpath(
                    (refs_dir / local).resolve(), target_path.parent.resolve()
                )
                return f"[{label}]({rel})"
        return match.group(0)

    return _FLOW_LINK_RE.sub(_sub, text)


def script_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return pathlib.Path(script_dir).parent


def parse_args():
    epilog = (
        "Modes: no flags sync all files to disk; --dry-run reports changes "
        "without writing; --ref <sha> syncs from a specific Flow commit."
    )
    parser = argparse.ArgumentParser(
        description="Sync Flow references into skills/seo-flow/references/.",
        epilog=epilog,
    )
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    parser.add_argument("--ref", metavar="SHA", help="Pin fetches to a Flow commit SHA.")
    return parser.parse_args()


def _base_headers():
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _authed_headers():
    """Returns authenticated headers, or base headers if gh CLI is absent or unauthed."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return _base_headers()
    if result.returncode != 0 or not result.stdout.strip():
        return _base_headers()
    token = result.stdout.strip()
    return {**_base_headers(), "Authorization": f"Bearer {token}"}


def content_url(path, ref):
    return f"{API_ROOT}/{path}" + (f"?ref={ref}" if ref else "")


def api_get(path, ref, headers):
    url = content_url(path, ref)
    _validate_github_url(url)
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read(_SIZE_LIMIT + 1)
            if len(data) > _SIZE_LIMIT:
                raise ValueError(f"Response for {path!r} exceeds {_SIZE_LIMIT} bytes")
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429) and "Authorization" not in headers:
            authed = _authed_headers()
            if "Authorization" in authed:
                return api_get(path, ref, authed)
        raise
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise SystemExit(f"Network error reaching GitHub: {reason}") from None


def fetch_file(path, ref, headers):
    data = api_get(path, ref, headers)
    content = data.get("content", "")
    return base64.b64decode(content).decode("utf-8")


def list_markdown_files(path, ref, headers):
    data = api_get(path, ref, headers)
    files = [
        (item["path"], item["name"])
        for item in data
        if item.get("type") == "file" and item.get("name", "").endswith(".md")
    ]
    return sorted(files, key=lambda item: item[1].lower())


def attribution_header(today):
    return (
        "<!-- Source: github.com/AgriciDaniel/flow | License: CC BY 4.0 | "
        f"Synced: {today} -->"
    )


def frontmatter_value(lines, key):
    if not lines or lines[0].strip() != "---":
        return ""
    needle = f"{key}:"
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.lower().startswith(needle):
            value = stripped[len(needle) :].strip()
            return value.strip("\"'")
    return ""


def body_lines_after_frontmatter(lines):
    if not lines or lines[0].strip() != "---":
        return lines
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return lines[index + 1 :]
    return lines


def first_h1(lines):
    for line in body_lines_after_frontmatter(lines):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def first_description(lines):
    for line in body_lines_after_frontmatter(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def prompt_meta(stage, filename, raw):
    lines = raw.splitlines()
    return {
        "stage": stage,
        "filename": filename,
        "title": frontmatter_value(lines, "title") or first_h1(lines),
        "description": frontmatter_value(lines, "description") or first_description(lines),
    }


def escape_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def prompt_readme(rows):
    lines = ["# Flow Prompt Index", "", "| Stage | Filename | Title | Description |", "|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| {stage} | {filename} | {title} | {description} |".format(
                stage=escape_cell(row["stage"]),
                filename=escape_cell(row["filename"]),
                title=escape_cell(row["title"]),
                description=escape_cell(row["description"]),
            )
        )
    return "\n".join(lines) + "\n"


def _sha256(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _atomic_write(path, content):
    """Write content atomically via a temp file in the same directory."""
    dir_ = path.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        shutil.move(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def record_write(root, path, content, dry_run, changes):
    resolved = path.resolve()
    root_resolved = root.resolve()
    if not str(resolved).startswith(str(root_resolved) + os.sep):
        raise ValueError(f"Path traversal blocked: {resolved} is outside {root_resolved}")

    rel = path.relative_to(root).as_posix()
    changes.setdefault("hashes", {})[rel] = _sha256(content)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        bucket = "unchanged" if current == content else "updated"
    else:
        bucket = "added"
    changes[bucket].append(rel)
    print(f"{bucket}: {rel}", file=sys.stderr)
    if not dry_run and bucket != "unchanged":
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, content)


def sync(args):
    root = script_root()
    refs = root / "skills" / "seo-flow" / "references"
    today = datetime.date.today().isoformat()
    headers = _base_headers()
    changes = {"added": [], "updated": [], "unchanged": [], "hashes": {}}
    prompt_rows = []

    for source, target in STATIC_FILES:
        print(f"fetch: {source}", file=sys.stderr)
        raw = fetch_file(source, args.ref, headers)
        content = f"{attribution_header(today)}\n{raw}"
        tpath = refs / target
        content = rewrite_flow_links(content, tpath, refs)
        record_write(root, tpath, content, args.dry_run, changes)

    for stage in PROMPT_STAGES:
        source_dir = f"docs/09-prompts/{stage}"
        print(f"list: {source_dir}", file=sys.stderr)
        for source, filename in list_markdown_files(source_dir, args.ref, headers):
            print(f"fetch: {source}", file=sys.stderr)
            raw = fetch_file(source, args.ref, headers)
            prompt_rows.append(prompt_meta(stage, filename, raw))
            target = refs / "prompts" / stage / filename
            content = f"{attribution_header(today)}\n{raw}"
            content = rewrite_flow_links(content, target, refs)
            record_write(root, target, content, args.dry_run, changes)

    record_write(root, refs / "prompts" / "README.md", prompt_readme(prompt_rows), args.dry_run, changes)

    # Generate SHA-256 lockfile
    lock_path = root / LOCK_REL
    lock_lines = [
        "# flow-prompts.lock — SHA-256 baseline for synced FLOW prompts",
        f"# Ref: {args.ref or 'HEAD'} | format: <sha256hex>  <rel_path> (sha256sum-compatible)",
        "",
    ]
    for rel in sorted(changes["hashes"]):
        lock_lines.append(f"{changes['hashes'][rel]}  {rel}")
    lock_content = "\n".join(lock_lines) + "\n"

    # Diff against existing lockfile and print drift report
    if lock_path.exists():
        old_lock = lock_path.read_text(encoding="utf-8")
        old_hashes = {}
        for line in old_lock.splitlines():
            if line and not line.startswith("#"):
                parts = line.split("  ", 1)
                if len(parts) == 2:
                    old_hashes[parts[1]] = parts[0]
        drift = []
        for rel, sha in sorted(changes["hashes"].items()):
            old_sha = old_hashes.get(rel)
            if old_sha is None:
                drift.append(f"  ADDED   {rel}")
            elif old_sha != sha:
                drift.append(f"  CHANGED {rel}")
        for rel in sorted(old_hashes):
            if rel not in changes["hashes"]:
                drift.append(f"  REMOVED {rel}")
        if drift:
            print("Lockfile drift detected:", file=sys.stderr)
            for line in drift:
                print(line, file=sys.stderr)
        else:
            print("Lockfile: no drift (all hashes match baseline)", file=sys.stderr)

    # Write lockfile (excluded from its own hashes tracking)
    record_write(root, lock_path, lock_content, args.dry_run, changes)
    lock_rel = LOCK_REL.as_posix()
    changes["hashes"].pop(lock_rel, None)
    for bucket in ("added", "updated", "unchanged"):
        try:
            changes[bucket].remove(lock_rel)
        except ValueError:
            pass

    return changes


if __name__ == "__main__":
    print(json.dumps(sync(parse_args()), sort_keys=True))
