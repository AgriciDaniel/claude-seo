#!/usr/bin/env python3
"""
Backlink API credential management for Claude SEO.

Loads and validates credentials for Moz Link Explorer API,
Bing Webmaster Tools API, and Common Crawl web graphs.
Supports config file and environment variable fallbacks.

Usage:
    python backlinks_auth.py --check                  # Check all credentials
    python backlinks_auth.py --check moz              # Check specific service
    python backlinks_auth.py --check --json            # JSON output
    python backlinks_auth.py --setup                   # Show setup instructions
    python backlinks_auth.py --tier                    # Show detected credential tier
"""

import argparse
import json
import os
import sys
from typing import Optional

# Import SSRF protection from google_auth (reuse, don't duplicate)
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
try:
    from google_auth import validate_url
except ImportError:
    # Fallback: basic URL validation if google_auth not available
    def validate_url(url: str) -> bool:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.hostname:
            return False
        blocked = ["localhost", "127.0.0.1", "0.0.0.0", "::1",
                    "metadata.google.internal"]
        if parsed.hostname in blocked:
            return False
        return True

CONFIG_PATH = os.path.expanduser("~/.config/claude-seo/backlinks-api.json")
CACHE_DIR = os.path.expanduser("~/.cache/claude-seo/commoncrawl")

# Which services need which auth type
SERVICE_AUTH = {
    "moz": "api_key",
    "bing": "api_key",
    "commoncrawl": "none",
    "verify": "none",
}

# Human-readable service names
SERVICE_NAMES = {
    "moz": "Moz Link Explorer API",
    "bing": "Bing Webmaster Tools API",
    "commoncrawl": "Common Crawl Web Graph",
    "verify": "Backlink Verification Crawler",
}


def load_config() -> dict:
    """
    Load configuration from config file with environment variable fallbacks.

    Reads ~/.config/claude-seo/backlinks-api.json first. Any missing fields
    are filled from environment variables.

    Returns:
        Dictionary with keys: moz_api_key, bing_api_key,
        bing_verified_sites, commoncrawl_cache_dir.
    """
    config = {
        "moz_api_key": None,
        "bing_api_key": None,
        "bing_verified_sites": [],
        "commoncrawl_cache_dir": CACHE_DIR,
    }

    # Load from config file
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                file_config = json.load(f)
            for k, v in file_config.items():
                if v is not None and v != "":
                    config[k] = v
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read config file: {e}", file=sys.stderr)

    # Environment variable fallbacks
    if not config["moz_api_key"]:
        config["moz_api_key"] = os.environ.get("MOZ_API_KEY")

    if not config["bing_api_key"]:
        config["bing_api_key"] = os.environ.get("BING_WEBMASTER_API_KEY")

    # Expand cache dir path
    config["commoncrawl_cache_dir"] = os.path.expanduser(
        config.get("commoncrawl_cache_dir", CACHE_DIR)
    )

    return config


def check_credentials(service: str) -> dict:
    """
    Validate credentials for a specific backlink data service.

    Args:
        service: One of 'moz', 'bing', 'commoncrawl', 'verify'.

    Returns:
        Dictionary with:
            - available: bool
            - method: auth method description
            - service: human-readable service name
            - error: error message or None
    """
    result = {
        "available": False,
        "method": SERVICE_AUTH.get(service, "unknown"),
        "service": SERVICE_NAMES.get(service, service),
        "error": None,
    }

    config = load_config()

    if service == "moz":
        api_key = config.get("moz_api_key")
        if api_key:
            result["available"] = True
            result["method"] = "api_key"
        else:
            result["error"] = (
                "No Moz API key found. Set MOZ_API_KEY environment variable "
                f"or add 'moz_api_key' to {CONFIG_PATH}\n"
                "         Sign up free at https://moz.com/products/api"
            )

    elif service == "bing":
        api_key = config.get("bing_api_key")
        if api_key:
            result["available"] = True
            result["method"] = "api_key"
            sites = config.get("bing_verified_sites", [])
            if sites:
                result["verified_sites"] = sites
            else:
                result["note"] = (
                    "No verified sites listed. Add 'bing_verified_sites' to config "
                    "for site-specific backlink queries."
                )
        else:
            result["error"] = (
                "No Bing Webmaster API key found. Set BING_WEBMASTER_API_KEY "
                f"environment variable or add 'bing_api_key' to {CONFIG_PATH}\n"
                "         Get free key at https://www.bing.com/webmasters"
            )

    elif service == "commoncrawl":
        # Common Crawl is always available (public data, no auth needed)
        result["available"] = True
        result["method"] = "none (public data)"
        cache_dir = config.get("commoncrawl_cache_dir", CACHE_DIR)
        result["cache_dir"] = cache_dir
        if os.path.exists(cache_dir):
            cached_files = [f for f in os.listdir(cache_dir) if f.endswith(".json")]
            result["cached_domains"] = len(cached_files)
        else:
            result["cached_domains"] = 0

    elif service == "verify":
        # Verification crawler is always available (uses fetch_page.py + parse_html.py)
        result["available"] = True
        result["method"] = "none (local crawler)"
        # Check that required scripts exist
        fetch_script = os.path.join(_SCRIPTS_DIR, "fetch_page.py")
        parse_script = os.path.join(_SCRIPTS_DIR, "parse_html.py")
        if not os.path.exists(fetch_script):
            result["available"] = False
            result["error"] = f"Required script not found: {fetch_script}"
        elif not os.path.exists(parse_script):
            result["available"] = False
            result["error"] = f"Required script not found: {parse_script}"

    else:
        result["error"] = f"Unknown service: {service}"

    return result


def detect_tier() -> dict:
    """
    Detect the backlink credential tier available.

    Tier 0: No API keys (Common Crawl + Verification Crawler always available)
    Tier 1: Moz API key configured
    Tier 2: Moz + Bing configured
    Tier 3: All + DataForSEO MCP available (checked externally)

    Returns:
        Dictionary with tier, description, capabilities, missing.
    """
    config = load_config()

    has_moz = bool(config.get("moz_api_key"))
    has_bing = bool(config.get("bing_api_key"))

    if has_moz and has_bing:
        return {
            "tier": 2,
            "description": "Full Free (Moz + Bing + Common Crawl + Verify)",
            "capabilities": [
                "Moz DA/PA/Spam Score (any domain)",
                "Moz referring domains and anchors",
                "Bing inbound links (verified sites)",
                "Bing competitor comparison",
                "Common Crawl domain-level graph",
                "Backlink verification crawler",
            ],
            "missing": "Add DataForSEO extension for premium backlink data (paid)",
        }
    elif has_moz:
        return {
            "tier": 1,
            "description": "Moz Only (Moz + Common Crawl + Verify)",
            "capabilities": [
                "Moz DA/PA/Spam Score (any domain)",
                "Moz referring domains and anchors",
                "Common Crawl domain-level graph",
                "Backlink verification crawler",
            ],
            "missing": (
                "Add Bing Webmaster API key for competitor comparison. "
                "Free at https://www.bing.com/webmasters"
            ),
        }
    else:
        return {
            "tier": 0,
            "description": "Basic (Common Crawl + Verify only)",
            "capabilities": [
                "Common Crawl domain-level graph (PageRank, in-degree)",
                "Backlink verification crawler",
            ],
            "missing": (
                "Add Moz API key for DA/PA and spam scoring. "
                "Free at https://moz.com/products/api (2,500 rows/month)"
            ),
        }


def get_moz_api_key() -> Optional[str]:
    """Get the Moz API key from config or environment."""
    config = load_config()
    return config.get("moz_api_key")


def get_bing_api_key() -> Optional[str]:
    """Get the Bing Webmaster API key from config or environment."""
    config = load_config()
    return config.get("bing_api_key")


def get_bing_verified_sites() -> list:
    """Get the list of Bing-verified sites from config."""
    config = load_config()
    return config.get("bing_verified_sites", [])


def get_cache_dir() -> str:
    """Get the Common Crawl cache directory, creating it if needed."""
    config = load_config()
    cache_dir = config.get("commoncrawl_cache_dir", CACHE_DIR)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def print_setup_instructions():
    """Print step-by-step setup instructions for all backlink APIs."""
    print("""
Backlink API Setup Instructions
================================

Free backlink data sources for Claude SEO. No payment required for any of these.

TIER 0: ALWAYS AVAILABLE (no setup needed)
------------------------------------------
  Common Crawl Web Graph: Public domain-level link data with PageRank.
  Backlink Verification:  Crawls pages to verify if backlinks still exist.

  These work immediately with no configuration.

TIER 1: MOZ API (free signup, 2,500 rows/month)
-------------------------------------------------
  1. Go to https://moz.com/products/api
  2. Click "Start your free 30-day trial" or "Get Free Access"
     (Free tier continues after trial with 2,500 rows/month)
  3. A valid credit card is required at signup but will NOT be charged
  4. After signup, go to https://moz.com/products/api/keys
  5. Copy your API key (looks like: mozscape-xxxxxxxx)

  Configure:
    export MOZ_API_KEY="mozscape-xxxxxxxx"

  Or save to """ + CONFIG_PATH + """:
    {
      "moz_api_key": "mozscape-xxxxxxxx"
    }

  Provides: Domain Authority, Page Authority, Spam Score, link counts,
            referring domains, anchor text distribution (any domain).
  Rate limit: 1 request per 10 seconds.

TIER 2: + BING WEBMASTER TOOLS API (free, verified sites)
-----------------------------------------------------------
  1. Go to https://www.bing.com/webmasters
  2. Sign in with Microsoft account
  3. Add and verify your site(s) (DNS, meta tag, or CNAME)
  4. Go to Settings > API access > API key
  5. Copy your API key

  Add to """ + CONFIG_PATH + """:
    {
      "moz_api_key": "mozscape-xxxxxxxx",
      "bing_api_key": "your-bing-api-key",
      "bing_verified_sites": ["example.com", "other-site.com"]
    }

  Or set environment variable:
    export BING_WEBMASTER_API_KEY="your-bing-api-key"

  Provides: Inbound links with anchor text, referring domains,
            competitor backlink comparison (unique feature!).
  Limitation: Only works for verified sites + their competitors.

PREMIUM: DATAFORSEO EXTENSION (paid, most comprehensive)
----------------------------------------------------------
  For full commercial-grade backlink data, install the DataForSEO extension:
    ./extensions/dataforseo/install.sh

  Provides: 35+ trillion links, real-time updates, toxic scoring,
            anchor text, competitor gap analysis, link velocity.

VERIFY CONFIGURATION:
  python scripts/backlinks_auth.py --check
  python scripts/backlinks_auth.py --tier
""")


def main():
    parser = argparse.ArgumentParser(
        description="Backlink API credential management for Claude SEO"
    )
    parser.add_argument(
        "--check",
        nargs="?",
        const="all",
        metavar="SERVICE",
        help="Check credentials. Optionally specify: moz, bing, commoncrawl, verify",
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
        return

    if args.tier:
        tier_info = detect_tier()
        if args.json:
            print(json.dumps(tier_info, indent=2))
        else:
            print(f"Backlink Tier: {tier_info['tier']} -- {tier_info['description']}")
            if tier_info["capabilities"]:
                print(f"Capabilities: {', '.join(tier_info['capabilities'])}")
            if tier_info["missing"]:
                print(f"Next tier: {tier_info['missing']}")
        return

    if args.check:
        services = (
            list(SERVICE_AUTH.keys())
            if args.check == "all"
            else [args.check]
        )

        results = {}
        for svc in services:
            if svc not in SERVICE_AUTH:
                results[svc] = {"available": False, "error": f"Unknown service: {svc}"}
                continue
            results[svc] = check_credentials(svc)

        if args.json:
            tier_info = detect_tier()
            output = {"status": "success", "tier": tier_info, "services": results}
            print(json.dumps(output, indent=2))
        else:
            tier_info = detect_tier()
            print(f"Backlink Tier: {tier_info['tier']} -- {tier_info['description']}")
            print()
            for svc, result in results.items():
                status = "OK" if result["available"] else "MISSING"
                print(f"  [{status}] {result.get('service', svc)}")
                if result.get("error"):
                    print(f"         {result['error']}")
                if result.get("verified_sites"):
                    print(f"         Verified sites: {', '.join(result['verified_sites'])}")
                if result.get("note"):
                    print(f"         Note: {result['note']}")
                if result.get("cached_domains") is not None:
                    print(f"         Cached domains: {result['cached_domains']}")
            print()
            if tier_info["missing"]:
                print(f"Tip: {tier_info['missing']}")
        return

    # Default: show tier
    tier_info = detect_tier()
    if args.json:
        print(json.dumps({"status": "success", "tier": tier_info}, indent=2))
    else:
        print(f"Backlink Tier: {tier_info['tier']} -- {tier_info['description']}")
        if tier_info["missing"]:
            print("Run --setup for configuration instructions.")


if __name__ == "__main__":
    main()
