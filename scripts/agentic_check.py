#!/usr/bin/env python3
"""
Agent-readiness HTTP auditor.

Checks the parts of agent readiness that live in HTTP responses and raw HTML,
so they can be verified without a browser:

1. robots.txt groups for AI crawlers and user-triggered agents, evaluated with
   RFC 9309 group selection (a named group replaces ``*``; nothing inherits),
   plus ``Content-Signal`` lines and the ``Agentmap:`` directive.
2. ``/llms.txt`` against the Lighthouse ``llms-txt`` rules and the llmstxt.org
   structure.
3. Markdown delivery: ``Accept: text/markdown`` negotiation (``Vary: Accept``),
   ``rel="alternate" type="text/markdown"`` links, and ``.md`` siblings.
4. Agentic Resource Discovery: ``ai-catalog.json`` discovery in the same order
   Lighthouse uses (robots ``Agentmap``, ``<link rel="ai-catalog">``, HTTP
   ``Link``, ``/.well-known/ai-catalog.json``) and the ARD conformance rules.
5. ``/.well-known`` discovery documents: RFC 9727 API Catalog, RFC 9728 and
   RFC 8414 OAuth metadata, and the A2A agent card. MCP Server Cards are found
   through ``ai-catalog.json`` (step 4), per the SEP-2127 proposal.
6. Server-rendered content: visible words in the raw HTML and JS-shell markers.
7. WebMCP hints in markup: declarative form attributes and imperative
   ``modelContext.registerTool`` calls in same-origin scripts.
8. Optional (``--ua-matrix``): how the site answers requests that carry each
   AI agent's user-agent token, compared with a browser user agent.

Audit posture
=============
Findings carry a priority (P0 to P3) and a status (pass, warn, fail, info, na).
Items built on drafts or proposals (Content-Signal, WebMCP, ARD) are labelled with their standards status. The script
does not compute a 0-100 score. For the Lighthouse "Agentic Browsing" fraction
use ``lighthouse_agentic.py``; for the accessibility tree use
``agent_ux_check.py``.

The user-agent matrix sends unverified requests. A WAF that challenges them is
often behaving correctly, because real agents are verified by IP range or Web
Bot Auth signature, not by the user-agent string. Read that section as
"observed behaviour for unverified traffic", never as proof that the real
agent is blocked.

SSRF
====
Every request goes through ``url_safety.safe_requests_get`` or
``url_safety.validate_url_strict``. Redirect targets are re-validated by the
DNS-pinning layer.

CLI
===
    python agentic_check.py https://example.com --json
    python agentic_check.py https://example.com/pricing --json --ua-matrix
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from typing import Optional
from urllib.parse import urljoin, urlparse

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import URLSafetyError, safe_requests_get  # noqa: E402

CHECKED_ON = "2026-09-23"
MAX_BODY = 2_000_000
MAX_SCRIPTS = 8
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/153.0.0.0 Safari/537.36")

# token, vendor, role, robots behaviour documented by the vendor.
# role: training | search | user (user-triggered fetch or agent) | control (robots token only)
AI_AGENTS = [
    ("GPTBot", "OpenAI", "training", "honours"),
    ("OAI-SearchBot", "OpenAI", "search", "honours"),
    ("ChatGPT-User", "OpenAI", "user", "may not apply"),
    ("OAI-AdsBot", "OpenAI", "ads", "see vendor documentation"),
    ("ClaudeBot", "Anthropic", "training", "honours"),
    ("Claude-SearchBot", "Anthropic", "search", "honours"),
    ("Claude-User", "Anthropic", "user", "honours"),
    ("PerplexityBot", "Perplexity", "search", "honours"),
    ("Perplexity-User", "Perplexity", "user", "generally ignores"),
    ("Google-Extended", "Google", "control", "honours"),
    ("Google-Agent", "Google", "user", "generally ignores"),
    ("Applebot-Extended", "Apple", "control", "honours"),
    ("CCBot", "Common Crawl", "training", "honours"),
]
ROLE_MEANING = {
    "training": "model training",
    "search": "AI search indexing and citation",
    "user": "fetches and actions a person asked for",
    "control": "a robots.txt control token (no separate crawler)",
    "ads": "ad landing-page checks",
}
# Representative user-agent strings containing each documented product token.
# Only the token matters for robots.txt matching and most WAF rules.
UA_STRINGS = {
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.3; +https://openai.com/gptbot)",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; OAI-SearchBot/1.3; +https://openai.com/searchbot)",
    "ChatGPT-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ChatGPT-User/1.0; +https://openai.com/bot)",
    "ClaudeBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "Claude-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0; +claudebot@anthropic.com)",
    "Claude-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +claudebot@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "Perplexity-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
}
CONTENT_SIGNAL_KEYS = {"search", "ai-input", "ai-train"}
# Cloudflare is testing a fourth key; accept it without treating it as standard.
CONTENT_SIGNAL_EXPERIMENTAL = {"use": {"immediate", "reference", "full"}}
# Vendor interstitial fingerprints. Generic words such as "captcha" or "access
# denied" appear on ordinary pages, so they only count with a 4xx/5xx status.
CHALLENGE_MARKERS = (
    "just a moment...", "cf-chl", "cf_chl", "px-captcha", "_incapsula_resource",
    "datadome", "verify you are human",
)
ARD_MEDIA_TYPES = {
    "application/ai-catalog+json", "application/agent-card+json",
    "application/a2a-agent-card+json", "application/mcp-server-card+json",
    "application/agent-skills+zip", "application/agent-skills+gzip",
    'text/markdown; profile="urn:air:agent-skills"', "application/ai-registry",
    "application/ai-registry+json",
}
ARD_URN = re.compile(r"^urn:air:([a-zA-Z0-9.-]+)(?::([a-zA-Z0-9._:-]+))?:([a-zA-Z0-9._-]+)$")
WELL_KNOWN = [
    # path, label, standards status, priority, expected content-type fragment
    ("/.well-known/api-catalog", "API Catalog", "RFC 9727", "P2", "linkset+json"),
    ("/.well-known/oauth-protected-resource", "OAuth Protected Resource Metadata",
     "RFC 9728", "P2", "json"),
    ("/.well-known/oauth-authorization-server", "OAuth Authorization Server Metadata",
     "RFC 8414", "P2", "json"),
    ("/.well-known/agent-card.json", "A2A agent card", "A2A protocol", "P3", "json"),
    ("/.well-known/ucp", "UCP commerce profile", "UCP (Google + Shopify open spec); "
     "depth in seo-ecommerce ucp_check.py", "P3", "json"),
]
# MCP Server Cards (SEP-2127, unmerged) are discovered through ai-catalog.json, which
# audit_ard() covers. The older /.well-known/mcp.json proposal (SEP-1649) is closed.


# --------------------------------------------------------------------------- fetch


def _site_root(url: str) -> str:
    parsed = urlparse(url if "://" in url else "https://" + url)
    return f"{parsed.scheme}://{parsed.netloc}"


def fetch(url: str, *, headers: Optional[dict] = None, timeout: int = 15) -> dict:
    """GET ``url`` through url_safety and return a small, JSON-safe record."""
    record = {"url": url, "status": None, "headers": {}, "text": "", "final_url": None,
              "error": None}
    try:
        resp = safe_requests_get(url, timeout=timeout, headers=headers or {},
                                 allow_redirects=True, stream=True)
        body = resp.raw.read(MAX_BODY + 1, decode_content=True) or b""
        resp.close()
    except URLSafetyError as exc:
        record["error"] = f"blocked by url_safety: {exc}"
        return record
    except Exception as exc:  # network errors are findings, not crashes
        record["error"] = f"{type(exc).__name__}: {exc}"[:300]
        return record
    record["status"] = resp.status_code
    record["final_url"] = resp.url
    record["headers"] = {k.lower(): v for k, v in resp.headers.items()}
    record["truncated"] = len(body) > MAX_BODY
    record["text"] = _decode(body[:MAX_BODY], record["headers"].get("content-type", ""))
    return record


def _decode(body: bytes, content_type: str) -> str:
    """Decode with the declared charset, else UTF-8; drop a leading BOM.

    ``requests`` would assume ISO-8859-1 for text/* without a charset, which
    garbles UTF-8 robots.txt and llms.txt files, so the header is read here.
    """
    match = re.search(r"charset=[\"']?([\w.:-]+)", content_type, re.I)
    meta = re.search(rb"<meta[^>]+charset\s*=\s*[\"']?([\w.:-]+)", body[:4096], re.I)
    if match:
        encoding = match.group(1)
    elif meta:
        encoding = meta.group(1).decode("ascii", "ignore")
    else:
        encoding = "utf-8"
    try:
        text = body.decode(encoding, errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    return text.lstrip("\ufeff")


def _ctype(rec: dict) -> str:
    return (rec.get("headers") or {}).get("content-type", "").lower()


def _check(cid, title, priority, status, standard, evidence=None, fix=None) -> dict:
    return {"id": cid, "title": title, "priority": priority, "status": status,
            "standard": standard, "evidence": evidence or {}, "fix": fix}


# --------------------------------------------------------------------------- robots.txt


def parse_robots(text: str) -> dict:
    """Parse robots.txt into RFC 9309 groups plus global lines.

    A group is one or more consecutive ``user-agent`` lines followed by rules.
    ``content-signal`` and other non-global lines attach to the current group.
    """
    groups: list = []
    global_lines = {"sitemap": [], "agentmap": [], "orphan_content_signal": []}
    current = None
    last_was_ua = False
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if current is None or not last_was_ua:
                current = {"agents": [], "rules": [], "content_signal": [], "other": []}
                groups.append(current)
            current["agents"].append(value)
            last_was_ua = True
            continue
        last_was_ua = False
        if field == "sitemap":
            global_lines["sitemap"].append(value)
        elif field == "agentmap":
            global_lines["agentmap"].append(value)
        elif current is None:
            if field == "content-signal":
                global_lines["orphan_content_signal"].append(value)
        elif field in ("allow", "disallow"):
            current["rules"].append((field, value))
        elif field == "content-signal":
            current["content_signal"].append(value)
        else:
            current["other"].append((field, value))
    return {"groups": groups, **global_lines}


def select_group(parsed: dict, token: str) -> dict:
    """RFC 9309: combine every group naming ``token``; else every ``*`` group."""
    token_l = token.lower()
    named = [g for g in parsed["groups"] if any(a.lower() == token_l for a in g["agents"])]
    chosen = named or [g for g in parsed["groups"] if "*" in g["agents"]]
    return {
        "matched": "named" if named else ("star" if chosen else "none"),
        "rules": [r for g in chosen for r in g["rules"]],
        "content_signal": [c for g in chosen for c in g["content_signal"]],
    }


def _pattern_matches(pattern: str, path: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "^" + ".*".join(re.escape(part) for part in body.split("*"))
    regex += "$" if anchored else ""
    return re.match(regex, path) is not None


def is_allowed(rules: list, path: str = "/") -> bool:
    """Longest-match evaluation; allow wins a tie; empty disallow allows all."""
    best_len, allowed = -1, True
    for field, value in rules:
        if field == "disallow" and value == "":
            continue
        if _pattern_matches(value, path):
            length = len(value)
            if length > best_len or (length == best_len and field == "allow"):
                best_len, allowed = length, field == "allow"
    return allowed


def parse_content_signal(value: str) -> dict:
    """Parse ``search=yes, ai-input=yes, ai-train=no`` into a dict plus issues."""
    signals, issues = {}, []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            issues.append(f"malformed entry '{part}'")
            continue
        key, val = (s.strip().lower() for s in part.split("=", 1))
        signals[key] = val
        if key in CONTENT_SIGNAL_EXPERIMENTAL:
            if val not in CONTENT_SIGNAL_EXPERIMENTAL[key]:
                issues.append(f"value for '{key}' must be one of "
                              f"{sorted(CONTENT_SIGNAL_EXPERIMENTAL[key])}")
            continue
        if key not in CONTENT_SIGNAL_KEYS:
            issues.append(f"unknown key '{key}'")
        elif val not in ("yes", "no"):
            issues.append(f"value for '{key}' must be yes or no")
    return {"signals": signals, "issues": issues}


def audit_robots(root: str) -> tuple[list, dict]:
    rec = fetch(root + "/robots.txt")
    checks, data = [], {"status": rec["status"], "error": rec["error"]}
    if rec["error"] or rec["status"] is None:
        checks.append(_check("robots-reachable", "robots.txt reachable", "P0", "warn",
                             "RFC 9309", {"error": rec["error"]},
                             "Serve /robots.txt so agents can read your policy."))
        return checks, data
    if rec["status"] >= 500:
        checks.append(_check("robots-reachable", "robots.txt reachable", "P0", "fail",
                             "RFC 9309", {"status": rec["status"]},
                             "A 5xx robots.txt tells compliant crawlers to treat the "
                             "whole site as disallowed. Fix the server error."))
        return checks, data
    if rec["status"] >= 400:
        checks.append(_check("robots-reachable", "robots.txt present", "P0", "warn",
                             "RFC 9309", {"status": rec["status"]},
                             "No robots.txt means everything is allowed and no "
                             "AI-usage preference is declared. Publish one deliberately."))
        data["parsed"] = parse_robots("")
        return checks, data

    parsed = parse_robots(rec["text"])
    data["parsed"] = {k: v for k, v in parsed.items() if k != "groups"}
    data["group_count"] = len(parsed["groups"])
    checks.append(_check("robots-reachable", "robots.txt reachable", "P0", "pass",
                         "RFC 9309", {"status": rec["status"], "groups": len(parsed["groups"])}))

    per_agent = []
    for token, vendor, role, behaviour in AI_AGENTS:
        sel = select_group(parsed, token)
        per_agent.append({
            "token": token, "vendor": vendor, "role": role,
            "governs": ROLE_MEANING[role], "robots_behaviour": behaviour,
            "group": sel["matched"], "root_allowed": is_allowed(sel["rules"], "/"),
            "content_signal": sel["content_signal"],
        })
    data["agents"] = per_agent

    explicit = [a["token"] for a in per_agent if a["group"] == "named"]
    blocked_search = [a["token"] for a in per_agent if a["role"] == "search" and not a["root_allowed"]]
    checks.append(_check(
        "robots-ai-groups", "Deliberate robots.txt groups for AI user agents", "P0",
        "warn" if blocked_search else ("pass" if explicit else "info"), "RFC 9309",
        {"named_groups": explicit, "search_crawlers_blocked_at_root": blocked_search},
        ("Blocking an AI search crawler removes the site from that engine's answers. "
         "Confirm this is intended." if blocked_search else
         None if explicit else
         "Every AI agent falls through to the * group. Add named groups if your "
         "policy differs by purpose (training vs search vs user fetches).")))

    user_agents = [a for a in per_agent if a["role"] == "user" and not a["root_allowed"]]
    checks.append(_check(
        "robots-user-agents", "User-triggered agents and robots.txt", "P1",
        "info" if user_agents else "pass", "vendor documentation",
        {"blocked_at_root": [a["token"] for a in user_agents],
         "documented_behaviour": {a["token"]: a["robots_behaviour"] for a in per_agent
                                  if a["role"] == "user"}},
        "Several user-triggered agents do not treat robots.txt as binding. Protect "
        "private paths with authentication, not robots.txt." if user_agents else None))

    all_signals = [s for g in parsed["groups"] for s in g["content_signal"]]
    signal_issues = []
    for value in all_signals + parsed["orphan_content_signal"]:
        signal_issues += parse_content_signal(value)["issues"]
    gap = [a["token"] for a in per_agent
           if a["group"] == "named" and not a["content_signal"]
           and any(g["content_signal"] for g in parsed["groups"] if "*" in g["agents"])]
    if not all_signals and not parsed["orphan_content_signal"]:
        status, fix = "info", ("No Content-Signal line. Optional: add one (for example "
                               "'Content-Signal: search=yes, ai-input=yes, ai-train=no') "
                               "to each group whose policy you want to state.")
    elif signal_issues or parsed["orphan_content_signal"] or gap:
        status = "warn"
        fix = ("A crawler that matches a named group reads only that group (RFC 9309), "
               "and no normative text says Content-Signal escapes that rule. Repeat the "
               "line inside every named group to be safe." if gap else
               "Place Content-Signal inside a user-agent group and use yes/no values "
               "for search, ai-input and ai-train.")
    else:
        status, fix = "pass", None
    checks.append(_check(
        "content-signal", "Content-Signal preference declared", "P1", status,
        "Cloudflare Content Signals Policy (CC0) + IETF draft; a preference, not "
        f"enforcement; Google says it does not act on it (checked {CHECKED_ON})",
        {"lines": all_signals, "outside_any_group": parsed["orphan_content_signal"],
         "issues": signal_issues, "named_groups_without_signal": gap}, fix))
    data["agentmap"] = parsed["agentmap"]
    return checks, data


# --------------------------------------------------------------------------- llms.txt


def evaluate_llms_txt(status: Optional[int], content: Optional[str]) -> dict:
    """Mirror Lighthouse 13.5.0 ``llms-txt`` and add llmstxt.org structure notes."""
    if status is None:
        return {"lighthouse": "fail", "errors": ["fetch failed"], "notes": []}
    if status >= 500:
        return {"lighthouse": "fail", "errors": [f"HTTP {status}"], "notes": []}
    if status >= 400:
        return {"lighthouse": "not-applicable", "errors": [], "notes": [f"HTTP {status}"]}
    content = (content or "").lstrip("\ufeff")  # JavaScript's \s matches a BOM
    errors = []
    if not re.search(r"^\s*#\s+.+", content, re.M):
        errors.append('missing an H1 header ("# Title")')
    if not re.search(r"\[.+\]\(.+\)", content):
        errors.append("contains no Markdown links")
    if len(content) < 50:
        errors.append("shorter than 50 characters")
    notes = []
    lines = [ln for ln in content.splitlines() if ln.strip()]
    if lines and not lines[0].lstrip().startswith("# "):
        notes.append("llmstxt.org expects the H1 to be the first line")
    if not re.search(r"^\s*>\s+\S", content, re.M):
        notes.append("no blockquote summary ('> ...') as llmstxt.org recommends")
    if not re.search(r"^\s*##\s+\S", content, re.M):
        notes.append("no H2 sections grouping the links")
    if re.search(r"^\s*<(!doctype|html)", content, re.I):
        notes.append("served HTML, not Markdown (likely a soft 404); not a Lighthouse rule")
    return {"lighthouse": "pass" if not errors else "fail", "errors": errors, "notes": notes}


def audit_llms(root: str) -> tuple[list, dict]:
    rec = fetch(root + "/llms.txt")
    result = evaluate_llms_txt(rec["status"], rec["text"] if rec["status"] else None)
    full = fetch(root + "/llms-full.txt")
    data = {"status": rec["status"], "content_type": _ctype(rec), "bytes": len(rec["text"]),
            "llms_full_status": full["status"], **result}
    status = {"pass": "pass", "fail": "fail", "not-applicable": "info"}[result["lighthouse"]]
    fix = None
    if result["lighthouse"] == "not-applicable":
        fix = ("No /llms.txt. Lighthouse drops the audit from the fraction; publishing a "
               "valid one adds a counted pass. Include an H1, a '>' summary and Markdown links.")
    elif result["lighthouse"] == "fail" and any("soft 404" in n for n in result["notes"]):
        fix = ("The host answers /llms.txt with an HTML page and status 200 (a catch-all). "
               "Lighthouse counts that as a failed audit. Return a real 404 (the audit "
               "becomes N/A) or publish a real llms.txt.")
    elif result["lighthouse"] == "fail":
        fix = "Fix: " + "; ".join(result["errors"])
    checks = [_check("llms-txt", "llms.txt follows the Lighthouse rules", "P1", status,
                     "community spec (llmstxt.org); Lighthouse checks it, Google Search "
                     "ignores it", data, fix)]
    return checks, data


# --------------------------------------------------------------------------- HTML page


def _soup(html: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml")


def visible_words(html: str) -> int:
    soup = _soup(html)
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    return len(soup.get_text(" ", strip=True).split())


JS_SHELL = re.compile(
    r'<div[^>]+id=["\'](root|app|__next|__nuxt)["\'][^>]*>\s*</div>|'
    r"enable javascript|you need to enable javascript", re.I)


def audit_page(url: str) -> tuple[list, dict]:
    rec = fetch(url)
    checks, data = [], {"status": rec["status"], "error": rec["error"]}
    if rec["error"] or not rec["status"] or rec["status"] >= 400:
        checks.append(_check("page-reachable", "Page reachable for a plain HTTP client",
                             "P0", "fail", "HTTP", {"status": rec["status"],
                                                   "error": rec["error"]},
                             "Agents and fetchers that do not run a browser cannot read it."))
        return checks, data
    html = rec["text"]
    words = visible_words(html)
    shell = bool(JS_SHELL.search(html))
    data.update({"words_without_js": words, "js_shell_marker": shell,
                 "final_url": rec["final_url"], "headers": {
                     k: rec["headers"].get(k) for k in ("link", "vary", "content-signal",
                                                        "x-robots-tag") if rec["headers"].get(k)}})
    status = "fail" if words < 50 and shell else "warn" if words < 150 else "pass"
    checks.append(_check(
        "server-rendered", "Primary content present without JavaScript", "P0", status,
        "practice (all fetchers)", {"words_without_js": words, "js_shell_marker": shell},
        None if status == "pass" else
        "Server-render or pre-render the main content. Several agent fetchers do not "
        "execute complex JavaScript. Compare with render_page.py --mode always."))

    soup = _soup(html)
    data["soup_links"] = _link_signals(soup, rec["headers"].get("link", ""), rec["final_url"])
    checks += _webmcp_markup(soup, rec["final_url"], data)
    return checks, data


def _link_signals(soup, link_header: str, base: str) -> dict:
    md_alt = [urljoin(base, tag.get("href", "")) for tag in soup.find_all("link")
              if "alternate" in [r.lower() for r in (tag.get("rel") or [])]
              and "text/markdown" in (tag.get("type") or "").lower() and tag.get("href")]
    ai_catalog = [urljoin(base, tag.get("href", "")) for tag in soup.find_all("link")
                  if "ai-catalog" in [r.lower() for r in (tag.get("rel") or [])]
                  and tag.get("href")]
    header_links = parse_link_header(link_header)
    for entry in header_links:
        rels = entry["rel"]
        if "alternate" in rels and "text/markdown" in entry.get("type", ""):
            md_alt.append(urljoin(base, entry["uri"]))
        if "ai-catalog" in rels:
            ai_catalog.append(urljoin(base, entry["uri"]))
    return {"markdown_alternates": sorted(set(md_alt)), "ai_catalog_links": ai_catalog,
            "ai_catalog_html": [u for u in ai_catalog if u not in
                                [urljoin(base, e["uri"]) for e in header_links]]}


def parse_link_header(value: str) -> list:
    """Minimal RFC 8288 parser: ``<uri>; rel="a b"; type="x"``."""
    out = []
    for match in re.finditer(r"<([^>]*)>([^,<]*)", value or ""):
        params = {}
        for p in re.finditer(r';\s*([a-zA-Z*-]+)\s*=\s*("([^"]*)"|[^;,\s]+)', match.group(2)):
            params[p.group(1).lower()] = p.group(3) if p.group(3) is not None else p.group(2)
        out.append({"uri": match.group(1),
                    "rel": [r.lower() for r in params.get("rel", "").split()],
                    "type": params.get("type", "").lower()})
    return out


def _webmcp_markup(soup, base: str, data: dict) -> list:
    forms = soup.find_all("form")
    annotated = [f for f in forms if f.get("toolname") or f.get("tooldescription")]
    unannotated = [(f.get("id") or f.get("name") or f.get("action") or "form") for f in forms
                   if not (f.get("toolname") or f.get("tooldescription"))]
    sources = [s.get_text() for s in soup.find_all("script") if not s.get("src")]
    origin = urlparse(base).netloc
    fetched = 0
    for tag in soup.find_all("script", src=True):
        if fetched >= MAX_SCRIPTS:
            break
        src = urljoin(base, tag["src"])
        if urlparse(src).netloc != origin:
            continue
        rec = fetch(src)
        fetched += 1
        if rec["status"] == 200:
            sources.append(rec["text"])
    blob = "\n".join(sources)
    registers = len(re.findall(r"\bregisterTool\s*\(", blob))
    uses_document = "document.modelContext" in blob
    uses_navigator = "navigator.modelContext" in blob
    data["webmcp"] = {"forms": len(forms), "forms_annotated": len(annotated),
                      "forms_unannotated": unannotated[:20], "registerTool_call_sites": registers,
                      "document_modelContext": uses_document,
                      "navigator_modelContext": uses_navigator,
                      "same_origin_scripts_scanned": fetched}
    checks = []
    has_tools = registers > 0 or annotated
    checks.append(_check(
        "webmcp-tools", "WebMCP tools for forms and transactions", "P2",
        "pass" if has_tools else "info",
        f"W3C Community Group draft, not a standard; WebKit opposes, Mozilla neutral "
        f"(checked {CHECKED_ON})",
        {"registerTool_call_sites": registers, "forms": len(forms),
         "forms_annotated": len(annotated),
         "note": "Static count of registerTool( call sites in inline and same-origin "
                 "scripts, not the number of tools (a loop registers many). Use "
                 "lighthouse_agentic.py webmcp-registered-tools for the real list."},
        None if has_tools else
        "Optional. If the site has search, booking, checkout or lead forms, register "
        "imperative tools bound to the same handlers the UI uses. Static scan only; "
        "confirm at runtime with lighthouse_agentic.py (webmcp-registered-tools)."))
    legacy_only = uses_navigator and not uses_document
    checks.append(_check(
        "webmcp-entry-point", "WebMCP registered on the current entry point", "P2",
        "warn" if legacy_only else ("pass" if uses_document else "na"),
        "W3C Community Group draft",
        {"navigator_modelContext": uses_navigator, "document_modelContext": uses_document},
        "Feature-detect both: 'const mc = document.modelContext ?? "
        "navigator.modelContext'. Check the current spec before shipping."
        if legacy_only else None))
    if not forms:
        form_status = "na"
    elif not unannotated:
        form_status = "pass"
    else:
        form_status = "info"
    checks.append(_check(
        "webmcp-form-annotations", "Forms annotated for declarative WebMCP (static scan)", "P3",
        form_status, "W3C Community Group draft (Chrome only)",
        {"forms": len(forms), "unannotated": unannotated[:20]},
        "Lighthouse's webmcp-form-coverage audit counts only when every form has toolname "
        "or tooldescription. Annotate only forms that are safe for an agent to submit."
        if form_status == "info" else None))
    return checks


# --------------------------------------------------------------------------- markdown


def audit_markdown(url: str, page: dict) -> tuple[list, dict]:
    neg = fetch(url, headers={"Accept": "text/markdown"})
    neg_ct = _ctype(neg)
    vary = (neg.get("headers") or {}).get("vary", "").lower()
    negotiated = neg["status"] == 200 and "text/markdown" in neg_ct
    data = {"negotiation": {"status": neg["status"], "content_type": neg_ct,
                            "vary_accept": "accept" in vary,
                            "x_markdown_tokens": (neg.get("headers") or {}).get("x-markdown-tokens"),
                            "content_signal_header": (neg.get("headers") or {}).get("content-signal")}}
    alternates = []
    for alt in (page.get("soup_links") or {}).get("markdown_alternates", [])[:3]:
        rec = fetch(alt)
        alternates.append({"url": alt, "status": rec["status"], "content_type": _ctype(rec),
                           "ok": rec["status"] == 200 and not _ctype(rec).startswith("text/html")})
    data["alternates"] = alternates
    parsed = urlparse(url)
    sibling = (f"{parsed.scheme}://{parsed.netloc}"
               + (parsed.path.rstrip("/") + ".md" if parsed.path.strip("/") else "/index.md"))
    sib = fetch(sibling)
    data["md_sibling"] = {"url": sibling, "status": sib["status"], "content_type": _ctype(sib),
                          "ok": sib["status"] == 200 and not _ctype(sib).startswith("text/html")}
    ok = negotiated or any(a["ok"] for a in alternates) or data["md_sibling"]["ok"]
    issues = []
    if negotiated and "accept" not in vary:
        issues.append("Markdown negotiation without 'Vary: Accept' lets caches serve "
                      "Markdown to browsers or HTML to agents.")
    status = "pass" if ok and not issues else ("warn" if ok else "info")
    checks = [_check(
        "markdown-delivery", "Markdown version of the page", "P1", status,
        "HTTP content negotiation (RFC 9110) + community practice; no consumer agent is "
        f"confirmed to request it (checked {CHECKED_ON})", data,
        "; ".join(issues) if issues else None if ok else
        "Optional. Offer a content-equivalent Markdown version via "
        "'Accept: text/markdown' (with 'Vary: Accept'), a rel=\"alternate\" "
        "type=\"text/markdown\" link, or a .md URL.")]
    return checks, data


# --------------------------------------------------------------------------- ARD


def validate_ai_catalog(raw: str) -> dict:
    """Port of the ARD semantic checks Lighthouse 13.5.0 runs (third-party/ard).

    The JSON Schema pass is not reproduced; ``lighthouse_agentic.py`` reports it.
    """
    errors, warnings = [], []
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return {"errors": [f"malformed JSON: {exc}"], "warnings": [], "entries": 0}
    if not isinstance(data, dict):
        return {"errors": ["root must be a JSON object"], "warnings": [], "entries": 0}
    spec = data.get("specVersion")
    if not spec:
        errors.append("missing required 'specVersion'")
    elif spec != "1.0":
        warnings.append(f"unrecognised specVersion {spec!r}, expected '1.0'")
    entries = data.get("entries")
    if entries is None:
        errors.append("missing required 'entries' array")
        return {"errors": errors, "warnings": warnings, "entries": 0}
    if not isinstance(entries, list):
        errors.append("'entries' must be an array")
        return {"errors": errors, "warnings": warnings, "entries": 0}
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry #{idx} is not an object")
            continue
        label = entry.get("displayName") or entry.get("identifier") or f"entry #{idx}"
        ident = entry.get("identifier")
        if not ident:
            errors.append(f"{label}: missing 'identifier'")
        elif not ARD_URN.match(str(ident)):
            errors.append(f"{label}: identifier must match "
                          "'urn:air:<publisher>[:<namespace>]:<name>'")
        if not entry.get("displayName"):
            errors.append(f"{label}: missing 'displayName'")
        media = entry.get("type")
        if not media:
            errors.append(f"{label}: missing 'type'")
        elif media not in ARD_MEDIA_TYPES:
            warnings.append(f"{label}: non-standard type {media!r}")
        has_url, has_data = "url" in entry, "data" in entry
        if has_url == has_data:
            errors.append(f"{label}: provide exactly one of 'url' or 'data'")
        queries = entry.get("representativeQueries")
        if queries is None:
            warnings.append(f"{label}: add 2 to 5 'representativeQueries'")
        elif not isinstance(queries, list):
            errors.append(f"{label}: 'representativeQueries' must be an array")
        else:
            if not 2 <= len(queries) <= 5:
                warnings.append(f"{label}: {len(queries)} representativeQueries, 2 to 5 recommended")
            if any(not isinstance(q, str) for q in queries):
                errors.append(f"{label}: every representative query must be a string")
        trust = entry.get("trustManifest")
        if trust is not None:
            if not isinstance(trust, dict):
                errors.append(f"{label}: 'trustManifest' must be an object")
            elif not trust.get("identity"):
                errors.append(f"{label}: 'trustManifest' needs 'identity'")
    if "collections" in data:
        errors.append("top-level 'collections' was removed (ADR-0003); nest catalogs in entries")
    return {"errors": errors, "warnings": warnings, "entries": len(entries)}


def audit_ard(root: str, agentmap: list, page: dict) -> tuple[list, dict]:
    links = page.get("soup_links") or {}
    candidates = ([urljoin(root + "/", a) for a in agentmap]
                  + links.get("ai_catalog_links", [])
                  + [root + "/.well-known/ai-catalog.json"])
    signalled = bool(agentmap or links.get("ai_catalog_links"))
    url = candidates[0]
    rec = fetch(url)
    data = {"catalog_url": url, "signalled": signalled, "status": rec["status"],
            "content_type": _ctype(rec)}
    standard = (f"Agentic Resource Discovery (ARD) spec 1.0; checked by Lighthouse 13.5 "
                f"ard-schema (checked {CHECKED_ON})")
    if not signalled and rec["status"] == 200 and _ctype(rec).startswith("text/html"):
        data["soft_404"] = True
        return [_check("ard-catalog", "ai-catalog.json (Agentic Resource Discovery)", "P1",
                       "fail", standard, data,
                       "/.well-known/ai-catalog.json returns an HTML page with status 200 (a "
                       "catch-all). Lighthouse treats any 200 as a catalog and counts a "
                       "failed ard-schema audit. Return a real 404 for unknown paths.")], data
    if not signalled and rec["status"] != 200:
        return [_check("ard-catalog", "ai-catalog.json (Agentic Resource Discovery)", "P3", "na",
                       standard, data,
                       "Only publish one if you have agent resources to list (MCP server, "
                       "A2A agent, skills). Lighthouse treats its absence as not applicable.")], data
    if rec["status"] != 200:
        return [_check("ard-catalog", "ai-catalog.json (Agentic Resource Discovery)", "P1",
                       "fail", standard, data,
                       "A catalog is signalled but does not load. Lighthouse counts this "
                       "as a failure. Fix the URL or remove the signal.")], data
    result = validate_ai_catalog(rec["text"])
    data.update(result)
    status = "fail" if result["errors"] else "warn" if result["warnings"] else "pass"
    return [_check("ard-catalog", "ai-catalog.json (Agentic Resource Discovery)",
                   "P1" if status == "fail" else "P3", status, standard, data,
                   None if status == "pass" else "Fix: " + "; ".join(
                       (result["errors"] + result["warnings"])[:6]))], data


# --------------------------------------------------------------------------- well-known


def audit_well_known(root: str) -> tuple[list, dict]:
    checks, data = [], {}
    for path, label, standard, priority, want in WELL_KNOWN:
        rec = fetch(root + path)
        ctype = _ctype(rec)
        row = {"status": rec["status"], "content_type": ctype}
        if rec["status"] == 200 and ctype.startswith("text/html"):
            row["soft_404"] = True
            status, fix = "warn", ("Returns HTML with 200. Serve a real 404 or the JSON "
                                   "document; soft 404s mislead discovery clients.")
        elif rec["status"] == 200:
            try:
                json.loads(rec["text"])
                row["valid_json"] = True
                status = "pass" if want in ctype else "warn"
                fix = None if status == "pass" else f"Serve with a content type containing '{want}'."
            except ValueError:
                row["valid_json"] = False
                status, fix = "fail", "Document is not valid JSON."
        else:
            status, fix = "na", f"Only needed if you operate the matching service ({label})."
        data[path] = row
        checks.append(_check(f"well-known:{path.split('/.well-known/')[1]}", label, priority,
                             status, standard, row, fix))
    return checks, data


# --------------------------------------------------------------------------- UA matrix


def _challenged(rec: dict) -> bool:
    headers = rec.get("headers") or {}
    if headers.get("cf-mitigated") == "challenge":
        return True
    if rec.get("status") in (401, 403, 429, 503):
        return True
    # Challenge interstitials are small pages; a marker inside a full content
    # page is not a challenge.
    text = rec.get("text") or ""
    return len(text) < 30000 and any(marker in text.lower() for marker in CHALLENGE_MARKERS)


def audit_ua_matrix(url: str) -> tuple[list, dict]:
    baseline = fetch(url, headers={"User-Agent": BROWSER_UA})
    rows = {"browser": {"status": baseline["status"], "challenged": _challenged(baseline),
                        "bytes": len(baseline["text"])}}
    for token, ua in UA_STRINGS.items():
        rec = fetch(url, headers={"User-Agent": ua})
        rows[token] = {"status": rec["status"], "challenged": _challenged(rec),
                       "bytes": len(rec["text"]), "error": rec["error"]}
    if rows["browser"]["challenged"] or not rows["browser"]["status"]:
        return [_check(
            "waf-ua-matrix", "Responses to AI agent user agents (unverified requests)", "P0",
            "info", "observation only; real agents are verified by IP or Web Bot Auth",
            {"rows": rows}, "Inconclusive: the browser baseline itself was challenged or "
            "failed, so agent rows cannot be compared. Check WAF logs instead.")], rows
    differing = [t for t, r in rows.items() if t != "browser"
                 and (r["status"] != rows["browser"]["status"] or r["challenged"])]
    status = "info" if differing else "pass"
    return [_check(
        "waf-ua-matrix", "Responses to AI agent user agents (unverified requests)", "P0",
        status, "observation only; real agents are verified by IP or Web Bot Auth",
        {"rows": rows, "differs_from_browser": differing},
        None if not differing else
        "Unverified requests using these tokens were treated differently. That is correct "
        "if your WAF verifies bots. Confirm in your WAF logs that verified bots and signed "
        "agents (Web Bot Auth) are allowed, and keep CAPTCHAs off content pages.")], rows


# --------------------------------------------------------------------------- driver


def audit_not_found(root: str) -> tuple[list, dict]:
    """Does an unknown URL return a real 404? Catch-all 200s break discovery files."""
    probe = f"{root}/claude-seo-404-probe-{os.urandom(4).hex()}"
    rec = fetch(probe)
    data = {"probe_url": probe, "status": rec["status"], "content_type": _ctype(rec)}
    catch_all = rec["status"] == 200
    data["catch_all_200"] = catch_all
    return [_check(
        "http-404", "Unknown URLs return a real 404", "P1",
        "warn" if catch_all else ("pass" if rec["status"] and rec["status"] >= 400 else "info"),
        "HTTP semantics (RFC 9110); Google soft-404 guidance", data,
        "Unknown paths return 200. Crawlers see soft 404s, and Lighthouse fails llms-txt and "
        "ard-schema on the catch-all page. Serve a real 404 for paths that do not exist."
        if catch_all else None)], data


def summarize(checks: list) -> dict:
    summary: dict = {}
    for c in checks:
        bucket = summary.setdefault(c["priority"], {})
        bucket[c["status"]] = bucket.get(c["status"], 0) + 1
    return dict(sorted(summary.items()))


def audit(url: str, *, ua_matrix: bool = False) -> dict:
    if "://" not in url:
        url = "https://" + url
    root = _site_root(url)
    report = {"url": url, "site_root": root,
              "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
              "facts_checked_on": CHECKED_ON, "checks": [], "data": {}}
    page_checks, page = audit_page(url)
    robots_checks, robots = audit_robots(root)
    llms_checks, llms = audit_llms(root)
    md_checks, md = audit_markdown(url, page)
    ard_checks, ard = audit_ard(root, robots.get("agentmap", []), page)
    wk_checks, wk = audit_well_known(root)
    nf_checks, nf = audit_not_found(root)
    report["checks"] = (page_checks + robots_checks + llms_checks + md_checks + ard_checks
                        + wk_checks + nf_checks)
    page.pop("soup_links", None)
    report["data"] = {"page": page, "robots": robots, "llms": llms, "markdown": md,
                      "ard": ard, "well_known": wk, "not_found": nf}
    if ua_matrix:
        ua_checks, rows = audit_ua_matrix(url)
        report["checks"] += ua_checks
        report["data"]["ua_matrix"] = rows
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    rank = {"fail": 0, "warn": 1, "info": 2, "pass": 3, "na": 4}
    report["checks"].sort(key=lambda c: (order[c["priority"]], rank[c["status"]]))
    report["summary"] = summarize(report["checks"])
    return report


def _print_text(report: dict) -> None:
    print(f"Agent readiness: {report['url']}")
    for c in report["checks"]:
        print(f"  {c['priority']} [{c['status']:>4}] {c['title']}")
        if c.get("fix") and c["status"] in ("fail", "warn"):
            print(f"      -> {c['fix']}")
    print(f"Summary: {json.dumps(report['summary'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent-readiness HTTP auditor")
    parser.add_argument("url", help="Page URL (the site root is derived from it)")
    parser.add_argument("--ua-matrix", action="store_true",
                        help="Also request the page with AI agent user agents "
                             "(use only on sites you control or are authorized to test)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()
    report = audit(args.url, ua_matrix=args.ua_matrix)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_text(report)
    failed_page = any(c["id"] == "page-reachable" for c in report["checks"])
    sys.exit(1 if failed_page else 0)


if __name__ == "__main__":
    main()
