#!/usr/bin/env python3
"""
Agent-readiness fix drafter.

Produces reviewable drafts for the fixes ``agentic_check.py`` reports. It never
writes to the site or overwrites a file: every draft goes to stdout (or the
``--output`` path the user names), and each one says what a person must decide
before shipping it.

Subcommands
===========
robots      Add a ``Content-Signal`` line to every user-agent group of an
            existing robots.txt that lacks one. Allow/Disallow rules are never
            changed: access policy is the site owner's decision.
llms        Draft an ``/llms.txt`` from a page's title, meta description and
            same-site navigation links (llmstxt.org structure; passes the
            Lighthouse ``llms-txt`` rules when the page has links).
ai-catalog  Draft an ``ai-catalog.json`` (Agentic Resource Discovery 1.0) from
            ``--entry`` values and validate it with the same rules as
            ``agentic_check.py``.
webmcp      Draft WebMCP scaffolds for each ``<form>`` on a page: declarative
            attributes (Chrome only) and an imperative ``registerTool`` block
            (Chrome origin trial and ChatGPT desktop) that submits through the
            form itself, so the tool runs the same handler as the UI.

CLI
===
    python agentic_fix.py robots https://example.com --signal "search=yes, ai-input=yes, ai-train=no"
    python agentic_fix.py robots --file robots.txt --signal "search=yes, ai-train=no"
    python agentic_fix.py llms https://example.com
    python agentic_fix.py ai-catalog --publisher example.com \\
        --entry "Docs MCP|application/mcp-server-card+json|https://example.com/mcp/server-card"
    python agentic_fix.py webmcp https://example.com/contact --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import urljoin, urlparse

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from agentic_check import fetch, parse_content_signal, validate_ai_catalog  # noqa: E402

DEFAULT_SIGNAL = "search=yes, ai-input=yes, ai-train=no"
SLUG = re.compile(r"[^a-z0-9]+")


# --------------------------------------------------------------------------- robots


def add_content_signal(robots_text: str, signal: str) -> dict:
    """Insert ``Content-Signal: <signal>`` into each user-agent group that has none.

    Groups follow RFC 9309 as ``agentic_check.parse_robots`` reads them: a group
    is a run of ``user-agent`` lines (blank lines and comments between them do
    not end it) followed by rule lines, until the next ``user-agent`` line after
    a rule. The signal goes directly after the group's last ``user-agent`` line,
    so no group is split and every Allow/Disallow outcome stays identical.
    """
    parsed = parse_content_signal(signal)
    if parsed["issues"]:
        raise ValueError("invalid signal: " + "; ".join(parsed["issues"]))
    robots_text = robots_text.lstrip("\ufeff")
    newline = "\r\n" if "\r\n" in robots_text else "\n"
    lines = robots_text.splitlines()

    # Pass 1: find groups as (index of last user-agent line, agents, has_signal).
    groups, current, in_ua_block = [], None, False
    for idx, line in enumerate(lines):
        field = _field(line)
        if not field:
            continue  # blank line or comment: neither starts nor ends a block
        if field == "user-agent":
            if current is None or not in_ua_block:
                current = {"last_ua": idx, "agents": [], "has_signal": False}
                groups.append(current)
            current["agents"].append(line.split(":", 1)[1].split("#", 1)[0].strip())
            current["last_ua"] = idx
            in_ua_block = True
            continue
        in_ua_block = False
        if current is not None and field == "content-signal":
            current["has_signal"] = True

    # Pass 2: insert after the last user-agent line of each group lacking a signal.
    insert_after = {g["last_ua"] for g in groups if not g["has_signal"]}
    changed = [g["agents"] for g in groups if not g["has_signal"]]
    out = []
    for idx, line in enumerate(lines):
        out.append(line)
        if idx in insert_after:
            out.append(f"Content-Signal: {signal}")

    if not groups:
        # Append (never prepend): rules outside any group stay inert instead of
        # joining the new group, and no Allow/Disallow line is invented.
        tail = ["User-agent: *", f"Content-Signal: {signal}"]
        out = (out + [""] + tail) if any(ln.strip() for ln in out) else tail
        changed.append(["*"])
    text = newline.join(out)
    if robots_text.endswith(("\n", "\r")) or not robots_text:
        text += newline
    return {"robots_txt": text, "groups_changed": changed}


def _field(line: str) -> str:
    body = line.lstrip("\ufeff").split("#", 1)[0]
    return body.split(":", 1)[0].strip().lower() if ":" in body else ""


# --------------------------------------------------------------------------- llms.txt


def draft_llms_txt(url: str, html: str, max_links: int = 30) -> str:
    """Build an llms.txt draft; ``url`` should be the final URL after redirects."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "") or urlparse(url).netloc
    desc_tag = soup.find("meta", attrs={"name": "description"})
    summary = (desc_tag.get("content") or "").strip() if desc_tag else ""
    host = urlparse(url).netloc
    seen, links = set(), []
    containers = soup.find_all(["nav", "header", "footer"]) or [soup]
    for container in containers:
        for a in container.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#", 1)[0]
            text = " ".join(a.get_text(" ", strip=True).split())
            if urlparse(href).netloc != host or not text or href in seen:
                continue
            seen.add(href)
            links.append((text, href))
            if len(links) >= max_links:
                break
        if len(links) >= max_links:
            break
    lines = [f"# {title}", ""]
    lines += [f"> {summary}", ""] if summary else ["> TODO: one or two sentences on what this site offers.", ""]
    lines += ["## Pages", ""]
    lines += [f"- [{text}]({href})" for text, href in links] or ["- [Home](" + url + ")"]
    lines += ["", "## Optional", "", "- TODO: secondary links agents may skip", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- ai-catalog


def draft_ai_catalog(publisher: str, entries: list) -> dict:
    items = []
    pub = SLUG.sub("-", publisher.lower()).strip("-") or "example"
    for raw in entries:
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) != 3:
            raise ValueError(f"--entry must be 'Display name|media type|url': {raw!r}")
        name, media, url = parts
        items.append({
            "identifier": f"urn:air:{pub}:{SLUG.sub('-', name.lower()).strip('-')}",
            "displayName": name,
            "type": media,
            "url": url,
            "representativeQueries": [f"TODO: a question {name} answers",
                                      f"TODO: a second question {name} answers"],
        })
    catalog = {"specVersion": "1.0", "entries": items}
    return {"catalog": catalog, "validation": validate_ai_catalog(json.dumps(catalog))}


# --------------------------------------------------------------------------- WebMCP


def _tool_name(form, index: int) -> str:
    base = form.get("id") or form.get("name") or urlparse(form.get("action") or "").path
    base = SLUG.sub("_", (base or f"form_{index}").lower()).strip("_") or f"form_{index}"
    return base[:48]


def _form_fields(form) -> list:
    fields = []
    for el in form.find_all(["input", "select", "textarea"]):
        name = el.get("name")
        kind = (el.get("type") or el.name).lower()
        if not name or kind in ("hidden", "submit", "button", "reset", "image", "file", "password"):
            continue
        label = ""
        if el.get("id"):
            tag = form.find("label", attrs={"for": el["id"]})
            label = tag.get_text(" ", strip=True) if tag else ""
        label = label or el.get("aria-label") or el.get("placeholder") or name
        schema = {"type": "number" if kind in ("number", "range") else
                  "boolean" if kind == "checkbox" else "string",
                  "description": label}
        if el.name == "select":
            options = [o.get("value", o.get_text(strip=True)) for o in el.find_all("option")]
            schema["enum"] = [o for o in options if o]
        if kind == "email":
            schema["format"] = "email"
        if kind == "radio":
            schema = {"type": "string", "description": name, "enum": []}
        existing = next((f for f in fields if f["name"] == name), None)
        if existing:  # radio and checkbox groups share one name
            if kind == "radio" and el.get("value"):
                existing["schema"].setdefault("enum", []).append(el["value"])
            existing["required"] = existing["required"] or el.has_attr("required")
            continue
        if kind == "radio" and el.get("value"):
            schema["enum"].append(el["value"])
        fields.append({"name": name, "schema": schema, "required": el.has_attr("required")})
    return fields


def draft_webmcp(url: str, html: str) -> list:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    drafts = []
    for index, form in enumerate(soup.find_all("form")):
        fields = _form_fields(form)
        if not fields:
            continue
        name = _tool_name(form, index)
        method = (form.get("method") or "get").lower()
        consequential = method == "post"
        properties = {f["name"]: f["schema"] for f in fields}
        required = [f["name"] for f in fields if f["required"]]
        # document.forms follows document order; CSS :nth-of-type counts siblings only.
        locator = (f"document.getElementById({json.dumps(form['id'])})" if form.get("id")
                   else f"document.forms[{index}]")
        selector = f"form#{form['id']}" if form.get("id") else f"document.forms[{index}]"
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        annotations = {"readOnlyHint": not consequential}
        if consequential:
            annotations["consequentialHint"] = True
        imperative = IMPERATIVE_TEMPLATE.format(
            name=name, locator=_js_safe(locator),
            schema=_js_safe(json.dumps(schema, indent=2).replace("\n", "\n    ")),
            annotations=json.dumps(annotations))
        drafts.append({
            "form": selector,
            "action": form.get("action"),
            "method": method,
            "tool_name": name,
            "consequential": consequential,
            "declarative_attributes": {
                "form": {"toolname": name, "tooldescription": "TODO: what submitting does"},
                "fields": {f["name"]: {"toolparamdescription": f["schema"]["description"]}
                           for f in fields},
            },
            "imperative_js": imperative,
            "review": [
                "Replace every TODO description with plain language an agent can act on.",
                "Keep the tool bound to the form submit so it runs the UI's own handler.",
                "Consequential tools (purchases, sends, deletes) must keep a human "
                "confirmation step; consequentialHint does not replace it.",
                "Log SubmitEvent.agentInvoked server-side and rate-limit agent submissions.",
            ],
        })
    return drafts


def _js_safe(text: str) -> str:
    """Keep page-derived strings from closing the surrounding <script> element."""
    return text.replace("<", "\\u003c")


IMPERATIVE_TEMPLATE = """<script type="module">
// Draft generated by claude-seo. WebMCP is a W3C Community Group draft.
const mc = document.modelContext ?? navigator.modelContext; // navigator: legacy engines
const form = {locator};
if (mc?.registerTool && form) {{
  mc.registerTool({{
    name: "{name}",
    description: "TODO: one sentence on what this does and what it returns.",
    inputSchema: {schema},
    annotations: {annotations},
    async execute(input) {{
      for (const [key, value] of Object.entries(input)) {{
        const field = form.elements.namedItem(key);
        if (!field) continue;
        if (field.type === "checkbox") field.checked = Boolean(value);
        else if ("value" in field) field.value = String(value);
      }}
      form.requestSubmit(); // same submit handler and validation as the UI
      return {{ content: [{{ type: "text", text: "Submitted. TODO: describe the visible result." }}] }};
    }}
  }});
}}
</script>"""


# --------------------------------------------------------------------------- CLI


def _with_scheme(url: str) -> str:
    return url if "://" in url else "https://" + url


def _page(url: str) -> tuple[str, str]:
    """Return (final_url, html); the final URL keeps same-site checks right after redirects."""
    rec = fetch(url)
    if rec["error"] or not rec["status"] or rec["status"] >= 400:
        raise SystemExit(f"Could not fetch {url}: {rec['error'] or rec['status']}")
    return rec["final_url"] or url, rec["text"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent-readiness fix drafter")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_robots = sub.add_parser("robots", help="Add Content-Signal to each robots.txt group")
    p_robots.add_argument("url", nargs="?", help="Site URL (reads /robots.txt)")
    p_robots.add_argument("--file", help="Local robots.txt instead of a URL")
    p_robots.add_argument("--signal", default=DEFAULT_SIGNAL)
    p_llms = sub.add_parser("llms", help="Draft /llms.txt from a page")
    p_llms.add_argument("url")
    p_cat = sub.add_parser("ai-catalog", help="Draft ai-catalog.json")
    p_cat.add_argument("--publisher", required=True, help="Publisher id, e.g. example.com")
    p_cat.add_argument("--entry", action="append", default=[],
                       help="'Display name|media type|url' (repeatable)")
    p_web = sub.add_parser("webmcp", help="Draft WebMCP scaffolds for a page's forms")
    p_web.add_argument("url")
    for p in (p_robots, p_llms, p_cat, p_web):
        p.add_argument("--json", action="store_true", help="JSON output")
        p.add_argument("--output", help="Write the draft to this path instead of stdout")
    args = parser.parse_args()

    if args.cmd == "robots":
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read()
        elif args.url:
            root = urlparse(_with_scheme(args.url))
            rec = fetch(f"{root.scheme}://{root.netloc}/robots.txt")
            if rec["status"] == 200:
                text = rec["text"]
            elif rec["status"] and 400 <= rec["status"] < 500:
                text = ""  # 4xx: no robots.txt, so start a new one
            else:
                # A 5xx, WAF block or network error is not "no file"; drafting from
                # nothing here would propose replacing the real policy.
                raise SystemExit(f"Could not read robots.txt ({rec['error'] or rec['status']}). "
                                 "Retry, or pass the current file with --file.")
        else:
            parser.error("robots needs a URL or --file")
        result = add_content_signal(text, args.signal)
        draft = result["robots_txt"]
    elif args.cmd == "llms":
        draft = draft_llms_txt(*_page(_with_scheme(args.url)))
        result = {"llms_txt": draft}
    elif args.cmd == "ai-catalog":
        if not args.entry:
            parser.error("ai-catalog needs at least one --entry")
        result = draft_ai_catalog(args.publisher, args.entry)
        draft = json.dumps(result["catalog"], indent=2) + "\n"
    else:
        final_url, html = _page(_with_scheme(args.url))
        result = {"url": final_url, "tools": draft_webmcp(final_url, html)}
        draft = "\n\n".join(t["imperative_js"] for t in result["tools"]) or "No forms with named fields.\n"

    body = json.dumps(result, indent=2) + "\n" if args.json else draft
    if args.output:
        try:
            with open(args.output, "x", encoding="utf-8") as fh:  # atomic: never overwrites
                fh.write(body)
        except FileExistsError:
            raise SystemExit(f"Refusing to overwrite {args.output}; choose a new path.") from None
        print(f"Draft written to {args.output}")
    else:
        sys.stdout.write(body)


if __name__ == "__main__":
    main()
