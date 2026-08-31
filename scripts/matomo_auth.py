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
import json
import os
import sys
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests",
          file=sys.stderr)
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

CONFIG_PATH = os.path.expanduser("~/.config/claude-seo/matomo.json")
DEFAULT_TIMEOUT = 15


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


def _sanity_check_instance_url(url: str) -> Optional[str]:
    """
    Light sanity check for a user-configured Matomo instance URL.

    Intentionally does NOT use scripts/url_safety.validate_url(): self-hosted
    Matomo instances frequently live on private networks, localhost, or
    behind reverse proxies on internal IPs. Forcing SSRF protection would
    block legitimate analytics setups. Instead we only enforce:

    - non-empty
    - http or https scheme
    - non-empty host
    - no userinfo in URL

    Returns:
        Normalized URL (trailing slash trimmed) or None if invalid.
    """
    if not url:
        return None
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    if "@" in url.split("//", 1)[-1].split("/", 1)[0]:
        return None
    host = url.split("//", 1)[-1].split("/", 1)[0]
    if not host:
        return None
    return url.rstrip("/")


def _probe_version(url: str, token: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Light probe: hit ``API.getMatomoVersion`` over HTTPS POST.

    Returns one of:
        {"ok": True, "version": "x.y.z"}
        {"ok": False, "status_code": int, "error": str}
    """
    try:
        resp = requests.post(
            f"{url}/index.php",
            data={
                "module": "API",
                "method": "API.getMatomoVersion",
                "format": "JSON",
                "token_auth": token,
            },
            timeout=timeout,
            headers={"User-Agent": "ClaudeSEO/2.2.5"},
        )
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

    url = _sanity_check_instance_url(raw_url)
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
    return _sanity_check_instance_url(config.get("matomo_url"))


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

  Note on self-hosted instances: MATOMO_URL may point to localhost, an
  internal IP, or behind a reverse proxy on a private network. The script
  applies a light URL sanity check (scheme + host only) rather than the
  strict SSRF protection used for arbitrary web fetches, because self-hosted
  Matomo instances frequently live outside the public internet.

VERIFY CONFIGURATION:
  python scripts/matomo_auth.py --check
  python scripts/matomo_auth.py --tier
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

    args = parser.parse_args()

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