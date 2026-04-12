#!/usr/bin/env python3
"""
NotebookLM client wrapper for Claude SEO.

Thin sync CLI over the unofficial ``notebooklm-py`` async API. Provides
research-automation primitives used by the ``seo-notebooklm`` skill:
auth check, notebook create, bulk URL import, ask, and artifact generation
(study guide, mind map, podcast, quiz, flashcards).

Outputs JSON with a consistent envelope:
    {"status": "ok|error|rate_limited|timeout", "command": "...", ...}

Usage:
    python notebooklm_client.py check --json
    python notebooklm_client.py create --name "Research" --json
    python notebooklm_client.py import --nb <id> --urls urls.txt --json
    python notebooklm_client.py import-pdf --nb <id> --path paper.pdf --json
    python notebooklm_client.py ask --nb <id> --question "..." --json
    python notebooklm_client.py study-guide --nb <id> --output study.md --json
    python notebooklm_client.py mind-map --nb <id> --output map.json --json
    python notebooklm_client.py podcast --nb <id> --output pod.mp3 \\
        --instructions "..." --json
    python notebooklm_client.py quiz --nb <id> --difficulty hard \\
        --output quiz.json --json
    python notebooklm_client.py flashcards --nb <id> --output cards.json --json
    python notebooklm_client.py brief --topic "..." --urls urls.txt \\
        --artifacts study-guide,mind-map --output ./out/ --json

This script is a *research accelerator*, not a production data source.
Upstream uses undocumented Google endpoints -- any operation can fail; the
caller (SKILL.md) handles surfaced errors gracefully.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

# Shared SSRF-protection helper from the seo-google skill.
try:
    from google_auth import validate_url
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from google_auth import validate_url


INSTALL_HINT = (
    'notebooklm-py is not installed. Run: '
    'pip install "notebooklm-py[browser]" && playwright install chromium'
)

# Absolute cap on artifact generation wait, to avoid blocking the caller.
ARTIFACT_TIMEOUT_SECONDS = 300

# Soft cap on per-notebook sources (NotebookLM historical free tier).
SOURCE_SOFT_CAP = 50


def _emit(payload: dict, as_json: bool) -> None:
    """Print an envelope to stdout in JSON or human-readable form."""
    if as_json:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
        return

    status = payload.get("status", "ok")
    command = payload.get("command", "?")
    print(f"[{status}] {command}")
    for key, value in payload.items():
        if key in ("status", "command"):
            continue
        if isinstance(value, (dict, list)):
            print(f"  {key}: {json.dumps(value, ensure_ascii=False, default=str)}")
        else:
            print(f"  {key}: {value}")


def _err(command: str, message: str, **extra: Any) -> dict:
    return {"status": "error", "command": command, "error": message, **extra}


def _import_client():
    """Lazy import so `check` can report a friendly install hint."""
    try:
        from notebooklm import NotebookLMClient  # type: ignore
    except ImportError as exc:
        raise RuntimeError(INSTALL_HINT) from exc
    return NotebookLMClient


def _read_urls(path: str) -> list[str]:
    """Read newline-delimited URLs, stripping blanks and comments."""
    urls: list[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


@dataclass
class ImportReport:
    imported: int = 0
    failed: list[dict] = field(default_factory=list)

    def record_ok(self) -> None:
        self.imported += 1

    def record_fail(self, url: str, reason: str) -> None:
        self.failed.append({"url": url, "reason": reason})


async def _bulk_import(client, notebook_id: str, urls: list[str]) -> ImportReport:
    """Import URLs one-by-one, recording per-source failures without aborting."""
    report = ImportReport()
    for url in urls:
        if not validate_url(url):
            report.record_fail(url, "blocked_by_ssrf_filter")
            continue
        try:
            await client.sources.add_url(notebook_id, url, wait=True)
            report.record_ok()
        except Exception as exc:  # upstream surface is unstable; keep broad
            report.record_fail(url, type(exc).__name__ + ": " + str(exc))
    return report


async def _wait_artifact(client, notebook_id: str, task_id: str) -> str:
    """Wait for an artifact task with a hard timeout. Returns 'ok' or 'timeout'."""
    try:
        await asyncio.wait_for(
            client.artifacts.wait_for_completion(notebook_id, task_id),
            timeout=ARTIFACT_TIMEOUT_SECONDS,
        )
        return "ok"
    except asyncio.TimeoutError:
        return "timeout"


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


async def cmd_check() -> dict:
    try:
        NotebookLMClient = _import_client()
    except RuntimeError as exc:
        return _err("check", str(exc))

    try:
        async with await NotebookLMClient.from_storage() as client:
            notebooks = await client.notebooks.list()
            return {
                "status": "ok",
                "command": "check",
                "authenticated": True,
                "notebook_count": len(notebooks),
                "notebooks": [
                    {"id": nb.id, "name": getattr(nb, "name", None)}
                    for nb in notebooks[:20]
                ],
            }
    except Exception as exc:
        return _err(
            "check",
            f"{type(exc).__name__}: {exc}",
            hint="Run: notebooklm login",
        )


async def cmd_create(name: str) -> dict:
    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        nb = await client.notebooks.create(name)
        return {
            "status": "ok",
            "command": "create",
            "notebook_id": nb.id,
            "name": name,
        }


async def cmd_import(notebook_id: str, urls_path: str) -> dict:
    urls = _read_urls(urls_path)
    if len(urls) > SOURCE_SOFT_CAP:
        warnings = [
            f"{len(urls)} urls exceeds soft cap of {SOURCE_SOFT_CAP}; "
            "consider splitting into multiple notebooks"
        ]
    else:
        warnings = []

    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        report = await _bulk_import(client, notebook_id, urls)

    return {
        "status": "ok",
        "command": "import",
        "notebook_id": notebook_id,
        "imported": report.imported,
        "failed": report.failed,
        "warnings": warnings,
    }


async def cmd_import_pdf(notebook_id: str, path: str) -> dict:
    if not os.path.isfile(path):
        return _err("import-pdf", f"file not found: {path}")

    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        await client.sources.add_file(notebook_id, path, wait=True)

    return {
        "status": "ok",
        "command": "import-pdf",
        "notebook_id": notebook_id,
        "path": path,
    }


async def cmd_ask(notebook_id: str, question: str) -> dict:
    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        answer = await client.chat.ask(notebook_id, question)

    return {
        "status": "ok",
        "command": "ask",
        "notebook_id": notebook_id,
        "question": question,
        "answer": getattr(answer, "text", str(answer)),
    }


async def cmd_study_guide(notebook_id: str, output: Optional[str]) -> dict:
    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        status = await client.artifacts.generate_report(
            notebook_id, format="study guide"
        )
        wait_status = await _wait_artifact(client, notebook_id, status.task_id)
        if wait_status == "timeout":
            return {"status": "timeout", "command": "study-guide"}

        path = output or f"./study-guide-{notebook_id}.md"
        await client.artifacts.download_report(notebook_id, path)

    return {
        "status": "ok",
        "command": "study-guide",
        "notebook_id": notebook_id,
        "artifact": {"study_guide": path},
    }


async def cmd_mind_map(notebook_id: str, output: Optional[str]) -> dict:
    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        status = await client.artifacts.generate_mind_map(notebook_id)
        wait_status = await _wait_artifact(client, notebook_id, status.task_id)
        if wait_status == "timeout":
            return {"status": "timeout", "command": "mind-map"}

        path = output or f"./mind-map-{notebook_id}.json"
        await client.artifacts.download_mind_map(notebook_id, path)

    return {
        "status": "ok",
        "command": "mind-map",
        "notebook_id": notebook_id,
        "artifact": {"mind_map": path},
    }


async def cmd_podcast(
    notebook_id: str,
    output: Optional[str],
    instructions: Optional[str],
) -> dict:
    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        status = await client.artifacts.generate_audio(
            notebook_id, instructions=instructions or ""
        )
        wait_status = await _wait_artifact(client, notebook_id, status.task_id)
        if wait_status == "timeout":
            return {"status": "timeout", "command": "podcast"}

        path = output or f"./podcast-{notebook_id}.mp3"
        await client.artifacts.download_audio(notebook_id, path)

    return {
        "status": "ok",
        "command": "podcast",
        "notebook_id": notebook_id,
        "artifact": {"podcast": path},
    }


async def cmd_quiz(
    notebook_id: str, difficulty: str, output: Optional[str]
) -> dict:
    if difficulty not in ("easy", "medium", "hard"):
        return _err(
            "quiz", f"invalid difficulty: {difficulty} (expected easy|medium|hard)"
        )

    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        status = await client.artifacts.generate_quiz(
            notebook_id, difficulty=difficulty
        )
        wait_status = await _wait_artifact(client, notebook_id, status.task_id)
        if wait_status == "timeout":
            return {"status": "timeout", "command": "quiz"}

        path = output or f"./quiz-{notebook_id}.json"
        await client.artifacts.download_quiz(
            notebook_id, path, output_format="json"
        )

    return {
        "status": "ok",
        "command": "quiz",
        "notebook_id": notebook_id,
        "difficulty": difficulty,
        "artifact": {"quiz": path},
    }


async def cmd_flashcards(notebook_id: str, output: Optional[str]) -> dict:
    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        status = await client.artifacts.generate_flashcards(notebook_id)
        wait_status = await _wait_artifact(client, notebook_id, status.task_id)
        if wait_status == "timeout":
            return {"status": "timeout", "command": "flashcards"}

        path = output or f"./flashcards-{notebook_id}.json"
        await client.artifacts.download_flashcards(
            notebook_id, path, output_format="json"
        )

    return {
        "status": "ok",
        "command": "flashcards",
        "notebook_id": notebook_id,
        "artifact": {"flashcards": path},
    }


async def cmd_brief(
    topic: str,
    urls_path: str,
    artifacts: list[str],
    output_dir: str,
) -> dict:
    """End-to-end research pipeline: create nb, import urls, generate artifacts."""
    urls = _read_urls(urls_path)
    os.makedirs(output_dir, exist_ok=True)
    warnings: list[str] = []
    if len(urls) > SOURCE_SOFT_CAP:
        warnings.append(
            f"{len(urls)} urls exceeds soft cap of {SOURCE_SOFT_CAP}"
        )

    NotebookLMClient = _import_client()
    async with await NotebookLMClient.from_storage() as client:
        nb = await client.notebooks.create(topic)
        report = await _bulk_import(client, nb.id, urls)

        produced: dict[str, str] = {}
        for artifact in artifacts:
            artifact = artifact.strip()
            if artifact == "study-guide":
                status = await client.artifacts.generate_report(
                    nb.id, format="study guide"
                )
                if await _wait_artifact(client, nb.id, status.task_id) == "ok":
                    path = os.path.join(output_dir, "study-guide.md")
                    await client.artifacts.download_report(nb.id, path)
                    produced["study_guide"] = path
                else:
                    warnings.append("study-guide: timeout")
            elif artifact == "mind-map":
                status = await client.artifacts.generate_mind_map(nb.id)
                if await _wait_artifact(client, nb.id, status.task_id) == "ok":
                    path = os.path.join(output_dir, "mind-map.json")
                    await client.artifacts.download_mind_map(nb.id, path)
                    produced["mind_map"] = path
                else:
                    warnings.append("mind-map: timeout")
            elif artifact == "podcast":
                status = await client.artifacts.generate_audio(nb.id)
                if await _wait_artifact(client, nb.id, status.task_id) == "ok":
                    path = os.path.join(output_dir, "podcast.mp3")
                    await client.artifacts.download_audio(nb.id, path)
                    produced["podcast"] = path
                else:
                    warnings.append("podcast: timeout")
            else:
                warnings.append(f"unknown artifact: {artifact}")

    return {
        "status": "ok",
        "command": "brief",
        "notebook_id": nb.id,
        "topic": topic,
        "imported": report.imported,
        "failed": report.failed,
        "artifacts": produced,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notebooklm_client.py",
        description="Sync CLI wrapper over notebooklm-py for claude-seo.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON envelope")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Verify auth and list notebooks")

    p_create = sub.add_parser("create", help="Create a notebook")
    p_create.add_argument("--name", required=True)

    p_import = sub.add_parser("import", help="Bulk-import URLs from a file")
    p_import.add_argument("--nb", required=True)
    p_import.add_argument("--urls", required=True)

    p_import_pdf = sub.add_parser("import-pdf", help="Attach a local PDF")
    p_import_pdf.add_argument("--nb", required=True)
    p_import_pdf.add_argument("--path", required=True)

    p_ask = sub.add_parser("ask", help="Ask a question against notebook sources")
    p_ask.add_argument("--nb", required=True)
    p_ask.add_argument("--question", required=True)

    p_sg = sub.add_parser("study-guide", help="Generate a study guide report")
    p_sg.add_argument("--nb", required=True)
    p_sg.add_argument("--output", default=None)

    p_mm = sub.add_parser("mind-map", help="Generate a mind map (JSON)")
    p_mm.add_argument("--nb", required=True)
    p_mm.add_argument("--output", default=None)

    p_pod = sub.add_parser("podcast", help="Generate an audio overview")
    p_pod.add_argument("--nb", required=True)
    p_pod.add_argument("--output", default=None)
    p_pod.add_argument("--instructions", default=None)

    p_quiz = sub.add_parser("quiz", help="Generate a quiz")
    p_quiz.add_argument("--nb", required=True)
    p_quiz.add_argument("--difficulty", default="medium")
    p_quiz.add_argument("--output", default=None)

    p_fc = sub.add_parser("flashcards", help="Generate flashcards")
    p_fc.add_argument("--nb", required=True)
    p_fc.add_argument("--output", default=None)

    p_brief = sub.add_parser("brief", help="End-to-end research brief pipeline")
    p_brief.add_argument("--topic", required=True)
    p_brief.add_argument("--urls", required=True)
    p_brief.add_argument(
        "--artifacts",
        default="study-guide,mind-map",
        help="Comma-separated: study-guide,mind-map,podcast",
    )
    p_brief.add_argument("--output", default="./out/")

    return parser


async def dispatch(args: argparse.Namespace) -> dict:
    cmd = args.command
    try:
        if cmd == "check":
            return await cmd_check()
        if cmd == "create":
            return await cmd_create(args.name)
        if cmd == "import":
            return await cmd_import(args.nb, args.urls)
        if cmd == "import-pdf":
            return await cmd_import_pdf(args.nb, args.path)
        if cmd == "ask":
            return await cmd_ask(args.nb, args.question)
        if cmd == "study-guide":
            return await cmd_study_guide(args.nb, args.output)
        if cmd == "mind-map":
            return await cmd_mind_map(args.nb, args.output)
        if cmd == "podcast":
            return await cmd_podcast(args.nb, args.output, args.instructions)
        if cmd == "quiz":
            return await cmd_quiz(args.nb, args.difficulty, args.output)
        if cmd == "flashcards":
            return await cmd_flashcards(args.nb, args.output)
        if cmd == "brief":
            artifacts = [a for a in args.artifacts.split(",") if a]
            return await cmd_brief(args.topic, args.urls, artifacts, args.output)
        return _err(cmd or "?", "unknown command")
    except RuntimeError as exc:
        # Install-hint surface from _import_client
        return _err(cmd or "?", str(exc))
    except FileNotFoundError as exc:
        return _err(cmd or "?", f"file not found: {exc}")
    except Exception as exc:
        return _err(cmd or "?", f"{type(exc).__name__}: {exc}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = asyncio.run(dispatch(args))
    _emit(result, as_json=args.json)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
