#!/usr/bin/env python3
"""
Matomo credential management for Claude SEO.

Loads and validates credentials for the Matomo Reporting API.
Supports config file and environment variable fallbacks.

Usage:
    python matomo_auth.py --check                  # Check credentials (live probe)
    python matomo_auth.py --check --json            # JSON output
    python matomo_auth.py --setup                   # Show setup instructions
    python matomo_auth.py --tier                    # Show detected credential tier
"""

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests",
          file=sys.stderr)
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from url_safety import (  # noqa: E402  (path bootstrap must run first)
    URLSafetyError,
    is_safe_ip,
    safe_requests_session,
)

CONFIG_PATH = os.path.expanduser("~/.config/claude-seo/matomo.json")
DEFAULT_TIMEOUT = 15
USER_AGENT = "ClaudeSEO/2.3.0"
LOCAL_TARGETS_ENV = "CLAUDE_SEO_LOCAL_TARGETS"

_SECRET_RE = re.compile(r"(token_auth|token|password)=[^\s&\"']+", re.IGNORECASE)


def redact(text: str) -> str:
    """Strip any ``token_auth=``/``token=``/``password=`` value from a string.

    Applied to every message this module emits. The token travels in the POST
    body, so it should never reach an exception string in the first place;
    this is the belt to that braces.
    """
    return _SECRET_RE.sub(r"\1=<redacted>", str(text))


def load_config() -> dict:
    """
    Load configuration from config file with environment variable fallbacks.

    Reads ~/.config/claude-seo/matomo.json first. Any missing fields
    are filled from environment variables.

    Returns:
        Dictionary with keys: matomo_url, matomo_token, matomo_site_id.
    """
    config = {
        "matomo_url": None,
        "matomo_token": None,
        "matomo_site_id": None,
    }

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                file_config = json.load(f)
            for k, v in file_config.items():
                if v is not None and v != "":
                    config[k] = v
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read config file: {e}", file=sys.stderr)

    if not config["matomo_url"]:
        config["matomo_url"] = os.environ.get("MATOMO_URL")
    if not config["matomo_token"]:
        config["matomo_token"] = (
            os.environ.get("MATOMO_API_TOKEN")
            or os.environ.get("MATOMO_TOKEN")
        )
    if not config["matomo_site_id"]:
        config["matomo_site_id"] = (
            os.environ.get("MATOMO_SITE_ID")
            or os.environ.get("MATOMO_IDSITE")
        )

    return config


def _normalize_instance_url(url: str) -> Optional[str]:
    """Shape-check and normalize a configured Matomo instance URL.

    Shape only: scheme, host, no userinfo, no trailing slash. Whether the
    instance may actually be contacted is decided by ``url_safety`` at request
    time (see :func:`instance_endpoint` and :func:`post_to_instance`), which is
    the single place in claude-seo that reads
    ``CLAUDE_SEO_LOCAL_TARGETS``. Deciding it here as well would put a second,
    divergent SSRF policy in the tree.

    Returns:
        Normalized URL (trailing slash trimmed) or None if malformed.
    """
    if not url:
        return None
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    authority = url.split("//", 1)[-1].split("/", 1)[0]
    if not authority or "@" in authority:
        return None
    return url.rstrip("/")


def instance_endpoint(url: str) -> str:
    """The Reporting API endpoint for a normalized instance URL."""
    return f"{url.rstrip('/')}/index.php"


def _local_targets_hint(endpoint: str) -> str:
    """The one-line remedy for a self-hosted instance on a private address."""
    parsed = urlparse(endpoint)
    host = parsed.hostname or ""
    port = parsed.port
    target = f"{host}:{port}" if port else host
    return (
        f"A self-hosted Matomo on a private address is supported: add it to the "
        f"{LOCAL_TARGETS_ENV} allowlist, for example "
        f"{LOCAL_TARGETS_ENV}={target}. The allowlist is consulted only for this "
        f"first, top-level URL; redirects and subresources stay fail-closed, and "
        f"cloud metadata addresses are refused even when listed. See SECURITY.md."
    )


def resolves_to_private_address(url: str) -> bool:
    """True when the instance URL's host resolves to a non-public address.

    Used by the installers to decide whether to print the
    ``CLAUDE_SEO_LOCAL_TARGETS`` hint. Best-effort: a host that does not
    resolve at all is not reported as private.
    """
    normalized = _normalize_instance_url(url)
    if not normalized:
        return False
    host = urlparse(normalized).hostname or ""
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return not is_safe_ip(host)
    try:
        addrinfo = socket.getaddrinfo(host, None, family=socket.AF_INET,
                                      type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return False
    return any(not is_safe_ip(info[4][0]) for info in addrinfo)


class MatomoRequestRefused(Exception):
    """A request to the configured Matomo instance was refused before it left.

    Raised for a URL ``url_safety`` will not allow (private address without the
    allowlist, blocked hostname, failed DNS) and for a redirect away from the
    instance. The message is always redacted.
    """


def post_to_instance(endpoint: str, data: dict,
                     timeout: int = DEFAULT_TIMEOUT) -> "requests.Response":
    """POST to a Matomo instance through url_safety's DNS-pinned session.

    Every outbound request to the user's Matomo instance goes through here.
    ``safe_requests_session`` validates the endpoint with
    ``validate_url_strict`` (which consults ``CLAUDE_SEO_LOCAL_TARGETS`` for
    this top-level URL) and pins the hostname to the validated address for the
    life of the session, so the address cannot be re-bound between validation
    and connect.

    Redirects are refused rather than followed. The Reporting API answers a
    POST with a JSON body; a 30x is either a misconfigured ``MATOMO_URL`` or an
    attempt to pivot the pinned session onto another host, and the pin does not
    extend to a redirect target. The error names the redirect target's host so
    the user can point ``MATOMO_URL`` at the final URL themselves.

    Raises:
        MatomoRequestRefused: refused before or instead of a response.
        requests.exceptions.RequestException: transport failures, which the
            callers already map to their own error envelopes.
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        with safe_requests_session(endpoint) as session:
            resp = session.post(
                endpoint,
                data=data,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
            )
    except URLSafetyError as exc:
        message = redact(exc)
        if resolves_to_private_address(endpoint):
            message = f"{message}. {_local_targets_hint(endpoint)}"
        raise MatomoRequestRefused(message) from None

    if 300 <= resp.status_code < 400:
        location = resp.headers.get("Location", "")
        target_host = urlparse(location).hostname or "an unnamed target"
        raise MatomoRequestRefused(
            f"Matomo answered HTTP {resp.status_code} with a redirect to "
            f"{target_host}. Redirects are not followed: the DNS pin covers "
            f"only the configured instance. Set MATOMO_URL to the URL your "
            f"instance actually serves the Reporting API from."
        )
    return resp


def _probe_version(url: str, token: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Light probe: POST ``API.getMatomoVersion`` through the pinned helpers.

    Returns one of:
        {"ok": True, "version": "x.y.z"}
        {"ok": False, "status_code": int, "error": str}
    """
    try:
        resp = post_to_instance(
            instance_endpoint(url),
            {
                "module": "API",
                "method": "API.getMatomoVersion",
                "format": "JSON",
                "token_auth": token,
            },
            timeout=timeout,
        )
    except MatomoRequestRefused as e:
        return {"ok": False, "error": redact(e)}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": f"timeout after {timeout}s"}
    except requests.exceptions.SSLError as e:
        return {"ok": False, "error": f"SSL error: {type(e).__name__}"}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "error": f"connection error: {type(e).__name__}"}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"request error ({type(e).__name__})"}

    if resp.status_code == 401 or resp.status_code == 403:
        return {"ok": False, "status_code": resp.status_code,
                "error": "authentication failed (invalid token_auth or insufficient permission)"}
    if resp.status_code >= 400:
        return {"ok": False, "status_code": resp.status_code,
                "error": f"HTTP {resp.status_code}"}

    try:
        payload = resp.json()
    except ValueError:
        return {"ok": False, "error": "non-JSON response"}

    if isinstance(payload, dict) and "result" in payload and payload.get("result") == "error":
        return {"ok": False, "error": str(payload.get("message", "Matomo API error"))[:200]}

    if isinstance(payload, str):
        return {"ok": True, "version": payload}
    if isinstance(payload, dict):
        # Matomo 5+ wraps the version: {"value": "5.13.0"}
        value = payload.get("value")
        if isinstance(value, str):
            return {"ok": True, "version": value}
    return {"ok": True, "version": json.dumps(payload)[:80]}


def check_credentials() -> dict:
    """
    Validate Matomo credentials by probing the configured instance.

    Returns:
        Dictionary with: available, method, instance, site_id, version,
        error (when unavailable).
    """
    config = load_config()
    raw_url = config.get("matomo_url") or ""
    token = config.get("matomo_token")
    site_id = config.get("matomo_site_id")

    url = _normalize_instance_url(raw_url)
    if not url:
        return {
            "available": False,
            "method": "matomo_token",
            "instance": raw_url,
            "site_id": site_id,
            "error": (
                "No Matomo URL configured or URL is invalid. Set MATOMO_URL environment variable "
                f"or add 'matomo_url' to {CONFIG_PATH}. URL must start with http:// or https://."
            ),
        }
    if not token:
        return {
            "available": False,
            "method": "matomo_token",
            "instance": url,
            "site_id": site_id,
            "error": (
                "No Matomo token_auth configured. Set MATOMO_API_TOKEN environment variable "
                f"or add 'matomo_token' to {CONFIG_PATH}."
            ),
        }

    probe = _probe_version(url, token)
    if not probe["ok"]:
        return {
            "available": False,
            "method": "matomo_token",
            "instance": url,
            "site_id": site_id,
            "verified": False,
            "error": probe.get("error"),
        }

    result = {
        "available": True,
        "method": "matomo_token",
        "instance": url,
        "site_id": site_id,
        "verified": True,
        "version": probe.get("version"),
    }
    return result


def detect_tier() -> dict:
    """Detect the Matomo credential tier available.

    Returns:
        Dictionary with tier (0 or 1), description, capabilities, missing.
    """
    status = check_credentials()
    if status["available"]:
        return {
            "tier": 1,
            "description": "Matomo configured (organic traffic + landing pages + referrers)",
            "capabilities": [
                "VisitsSummary.get (total and per-day organic sessions)",
                "Actions.getEntryPageUrls (organic landing pages)",
                "Actions.getPageUrls (all pages)",
                "DevicesDetection.getType (device breakdown)",
                "UserCountry.getCountry (country breakdown)",
                "Referrers.getReferrersType (direct / search / social / website)",
                "Referrers.getSearchEngines (search-engine split)",
                "Referrers.getKeywords (organic keywords; often '(not provided)')",
            ],
            "missing": None,
        }
    return {
        "tier": 0,
        "description": "No Matomo credentials",
        "capabilities": [],
        "missing": (
            "Configure Matomo via extensions/matomo/install.sh to unlock "
            "organic traffic, top landing pages, device and country breakdowns, "
            "and referrer analysis. Works alongside GA4 or as a replacement."
        ),
    }


def get_matomo_url() -> Optional[str]:
    """Get the configured Matomo URL."""
    config = load_config()
    return _normalize_instance_url(config.get("matomo_url"))


def get_matomo_token() -> Optional[str]:
    """Get the configured Matomo token_auth."""
    config = load_config()
    return config.get("matomo_token")


def get_matomo_site_id() -> Optional[str]:
    """Get the configured default Matomo site ID (as string)."""
    config = load_config()
    sid = config.get("matomo_site_id")
    if sid is None:
        return None
    return str(sid)


def print_setup_instructions() -> None:
    """Print step-by-step setup instructions for Matomo."""
    print(f"""
Matomo Setup Instructions
=========================

Matomo is a self-hosted web analytics platform. Use it as a GA4 replacement
when you want full data ownership, no Google dependency, or privacy-first
analytics. The Reporting API exposes visits, landing pages, devices,
countries, and referrers.

TIER 1: MATOMO REPORTING API (one token, your own instance)
-----------------------------------------------------------

  1. Log in to your Matomo instance as a Super User or Admin
  2. Go to Administration -> Personal -> Security -> API Tokens
  3. Click "Create a new token". Give it a meaningful name (e.g. "claude-seo")
     and at least "view" access on the sites you want to analyze
  4. Copy the generated token_auth (a 32-character hex string)

  Configure via env (recommended for shared machines):

    export MATOMO_URL="https://analytics.example.com"
    export MATOMO_API_TOKEN="abc123...32hex"
    export MATOMO_SITE_ID="1"

  Or save to {CONFIG_PATH}:

    {{
      "matomo_url": "https://analytics.example.com",
      "matomo_token": "abc123...32hex",
      "matomo_site_id": "1"
    }}

  Provides: visits, bounce rate, avg time on site, organic landing pages,
            device and country breakdowns, search-engine referral split,
            organic search keywords (often "(not provided)" due to browser
            privacy headers and Matomo's keyword anonymization rules).

  Note on self-hosted instances: every request to your Matomo instance goes
  through claude-seo's SSRF guard, which refuses private and loopback
  addresses by default. If your instance lives on such an address, name it in
  the CLAUDE_SEO_LOCAL_TARGETS allowlist:

    export CLAUDE_SEO_LOCAL_TARGETS="matomo.internal:8080"

  Entries are host or host:port, comma-separated, matched exactly. The
  allowlist is consulted only for the top-level instance URL; redirects and
  subresources stay fail-closed, and cloud metadata addresses are refused even
  when listed. See SECURITY.md.

VERIFY CONFIGURATION:
  "${{CLAUDE_PLUGIN_ROOT}}/scripts/claude-seo" run matomo_auth.py --check
  "${{CLAUDE_PLUGIN_ROOT}}/scripts/claude-seo" run matomo_auth.py --tier
""")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Matomo credential management for Claude SEO"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Probe configured Matomo credentials (live API.getMatomoVersion call)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Show setup instructions",
    )
    parser.add_argument(
        "--tier",
        action="store_true",
        help="Show detected credential tier",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--local-target-hint",
        metavar="URL",
        help=(
            "Print the CLAUDE_SEO_LOCAL_TARGETS line needed to reach URL when it "
            "resolves to a private address, and nothing otherwise. Used by the "
            "extension installers."
        ),
    )

    args = parser.parse_args()

    if args.local_target_hint:
        url = _normalize_instance_url(args.local_target_hint)
        if url and resolves_to_private_address(url):
            print(_local_targets_hint(instance_endpoint(url)))
        return 0

    if args.setup:
        print_setup_instructions()
        return 0

    if args.check:
        status = check_credentials()
        if args.json:
            tier_info = detect_tier()
            output = {"status": "success" if status["available"] else "error",
                      "tier": tier_info,
                      "credentials": status}
            print(json.dumps(output, indent=2))
        else:
            tier_info = detect_tier()
            print(f"Matomo Tier: {tier_info['tier']} -- {tier_info['description']}")
            print()
            tag = "OK" if status["available"] else "MISSING"
            print(f"  [{tag}] Matomo Reporting API")
            print(f"         Instance: {status.get('instance') or '-'}")
            print(f"         Site ID: {status.get('site_id') or '-'}")
            if status.get("version"):
                print(f"         Version: {status['version']}")
            if status.get("error"):
                print(f"         Error: {status['error']}")
            print()
            if tier_info["missing"]:
                print(f"Tip: {tier_info['missing']}")
        return 0 if status["available"] else 1

    if args.tier:
        tier_info = detect_tier()
        if args.json:
            print(json.dumps(tier_info, indent=2))
        else:
            print(f"Matomo Tier: {tier_info['tier']} -- {tier_info['description']}")
            if tier_info["capabilities"]:
                print(f"Capabilities: {', '.join(tier_info['capabilities'])}")
            if tier_info["missing"]:
                print(f"Next: {tier_info['missing']}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
