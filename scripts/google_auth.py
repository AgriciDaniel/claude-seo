#!/usr/bin/env python3
"""
Google API credential management for Claude SEO.

Loads and validates credentials for Google Search Console, PageSpeed Insights,
CrUX, Indexing API, and GA4. Supports service accounts, OAuth web credentials
with token refresh, API keys, and environment variable fallbacks.

Usage:
    python google_auth.py --check                  # Check all credentials
    python google_auth.py --check gsc              # Check specific service
    python google_auth.py --check --json            # JSON output
    python google_auth.py --setup                   # Show setup instructions
    python google_auth.py --tier                    # Show detected credential tier
    python google_auth.py --auth --creds /path/to/client_secret.json  # OAuth browser flow
"""

import argparse
import json
import os
import sys
import time
from typing import Optional

CONFIG_PATH = os.path.expanduser("~/.config/claude-seo/google-api.json")
TOKEN_PATH = os.path.expanduser("~/.config/claude-seo/oauth-token.json")

# Service-to-scope mapping
SCOPES = {
    "gsc_readonly": "https://www.googleapis.com/auth/webmasters.readonly",
    "gsc_write": "https://www.googleapis.com/auth/webmasters",
    "indexing": "https://www.googleapis.com/auth/indexing",
    "ga4": "https://www.googleapis.com/auth/analytics.readonly",
}

# Which services need which auth type
SERVICE_AUTH = {
    "psi": "api_key",
    "crux": "api_key",
    "crux_history": "api_key",
    "gsc": "oauth_or_sa",
    "indexing": "oauth_or_sa",
    "ga4": "oauth_or_sa",
}

OAUTH_SCOPES = (
    "https://www.googleapis.com/auth/indexing "
    "https://www.googleapis.com/auth/webmasters "
    "https://www.googleapis.com/auth/analytics.readonly"
)
OAUTH_REDIRECT_URI = "http://localhost:8085"

# Human-readable service names
SERVICE_NAMES = {
    "psi": "PageSpeed Insights v5",
    "crux": "Chrome UX Report (CrUX) API",
    "crux_history": "CrUX History API",
    "gsc": "Google Search Console API",
    "indexing": "Google Indexing API v3",
    "ga4": "GA4 Data API v1beta",
}


def load_config() -> dict:
    """
    Load configuration from config file with environment variable fallbacks.

    Reads ~/.config/claude-seo/google-api.json first. Any missing fields
    are filled from environment variables.

    Returns:
        Dictionary with keys: service_account_path, api_key,
        default_property, ga4_property_id. Missing values are None.
    """
    config = {
        "service_account_path": None,
        "api_key": None,
        "default_property": None,
        "ga4_property_id": None,
    }

    # Load from config file
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                file_config = json.load(f)
            config.update({k: v for k, v in file_config.items() if v})
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read config file: {e}", file=sys.stderr)

    # Environment variable fallbacks
    if not config["service_account_path"]:
        config["service_account_path"] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if not config["api_key"]:
        config["api_key"] = os.environ.get("GOOGLE_API_KEY")

    if not config["ga4_property_id"]:
        config["ga4_property_id"] = os.environ.get("GA4_PROPERTY_ID")

    if not config["default_property"]:
        config["default_property"] = os.environ.get("GSC_PROPERTY")

    return config


def get_service_account_credentials(scopes: list):
    """
    Load Google service account credentials.

    Args:
        scopes: List of OAuth scope URLs.

    Returns:
        google.oauth2.service_account.Credentials object, or None on failure.
    """
    try:
        from google.oauth2 import service_account
    except ImportError:
        print(
            "Error: google-auth library required. "
            "Install with: pip install google-auth",
            file=sys.stderr,
        )
        return None

    config = load_config()
    sa_path = config.get("service_account_path")

    if not sa_path:
        return None

    sa_path = os.path.expanduser(sa_path)
    if not os.path.exists(sa_path):
        print(
            f"Error: Service account file not found: {sa_path}",
            file=sys.stderr,
        )
        return None

    try:
        credentials = service_account.Credentials.from_service_account_file(
            sa_path, scopes=scopes
        )
        return credentials
    except Exception as e:
        print(f"Error loading service account: {e}", file=sys.stderr)
        return None


def _load_oauth_client(creds_path: str) -> Optional[dict]:
    """Load OAuth client credentials from a client_secret JSON file."""
    try:
        with open(creds_path, "r") as f:
            data = json.load(f)
        return data.get("web", data.get("installed", {}))
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading OAuth client file: {e}", file=sys.stderr)
        return None


def _load_oauth_token() -> Optional[dict]:
    """Load saved OAuth token from TOKEN_PATH."""
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _save_oauth_token(token_data: dict):
    """Save OAuth token to TOKEN_PATH."""
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump(token_data, f, indent=2)


def _refresh_oauth_token(client: dict, token_data: dict) -> Optional[dict]:
    """Refresh an expired OAuth token using the refresh_token."""
    import urllib.parse
    import urllib.request

    if not token_data.get("refresh_token"):
        return None

    params = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()

    try:
        req = urllib.request.Request(client.get("token_uri", "https://oauth2.googleapis.com/token"), data=params)
        with urllib.request.urlopen(req) as resp:
            new_data = json.loads(resp.read())
        token_data["access_token"] = new_data["access_token"]
        token_data["expires_at"] = time.time() + new_data.get("expires_in", 3600)
        _save_oauth_token(token_data)
        return token_data
    except Exception as e:
        print(f"Error refreshing OAuth token: {e}", file=sys.stderr)
        return None


def get_oauth_credentials(scopes: list):
    """
    Get OAuth credentials from saved token, refreshing if needed.

    Falls back to service account if no OAuth token is available.

    Args:
        scopes: List of OAuth scope URLs (used for service account fallback).

    Returns:
        google.oauth2.credentials.Credentials or service_account.Credentials, or None.
    """
    config = load_config()

    # Try OAuth token first
    token_data = _load_oauth_token()
    if token_data and token_data.get("access_token"):
        # Check if token needs refresh
        if time.time() > token_data.get("expires_at", 0) - 60:
            oauth_creds_path = config.get("oauth_client_path")
            if oauth_creds_path:
                client = _load_oauth_client(os.path.expanduser(oauth_creds_path))
                if client:
                    token_data = _refresh_oauth_token(client, token_data)
                    if not token_data:
                        print("OAuth token refresh failed. Re-run --auth.", file=sys.stderr)
                        return get_service_account_credentials(scopes)

        if token_data and token_data.get("access_token"):
            try:
                from google.oauth2.credentials import Credentials
                # Read client_secret from client file, never from stored token
                client_secret = None
                oauth_path = config.get("oauth_client_path")
                if oauth_path:
                    client_data = _load_oauth_client(os.path.expanduser(oauth_path))
                    if client_data:
                        client_secret = client_data.get("client_secret")
                return Credentials(
                    token=token_data["access_token"],
                    refresh_token=token_data.get("refresh_token"),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=token_data.get("client_id"),
                    client_secret=client_secret,
                )
            except ImportError:
                print("Error: google-auth required. Install with: pip install google-auth", file=sys.stderr)

    # Fall back to service account
    return get_service_account_credentials(scopes)


def run_oauth_flow(creds_path: str):
    """
    Run OAuth browser-based authentication flow.

    Opens a browser for consent, captures the auth code via local HTTP server,
    exchanges for tokens, and saves them.

    Args:
        creds_path: Path to the OAuth client_secret JSON file.
    """
    import http.server
    import urllib.parse
    import urllib.request
    import webbrowser

    client = _load_oauth_client(creds_path)
    if not client:
        print("Error: Could not load OAuth client credentials.", file=sys.stderr)
        sys.exit(1)

    auth_url = (
        f"{client.get('auth_uri', 'https://accounts.google.com/o/oauth2/auth')}"
        f"?client_id={client['client_id']}"
        f"&redirect_uri={urllib.parse.quote(OAUTH_REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope={urllib.parse.quote(OAUTH_SCOPES)}"
        f"&access_type=offline&prompt=consent"
    )

    auth_code = [None]

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in params:
                auth_code[0] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authentication successful!</h1><p>Close this tab.</p>")
            else:
                self.send_response(400)
                self.end_headers()
        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("localhost", 8085), Handler)
    server.timeout = 300

    print(f"\nOpen this URL in your browser:\n\n{auth_url}\n")
    print("Waiting up to 5 minutes for authentication...")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    server.handle_request()
    server.server_close()

    if not auth_code[0]:
        print("\nAuthentication failed or timed out.", file=sys.stderr)
        print("If the browser showed 'localhost refused to connect', copy the full URL")
        print("from the browser address bar and run:")
        print(f"  python scripts/google_auth.py --exchange --creds {creds_path} --code 'THE_CODE'")
        sys.exit(1)

    # Exchange code for tokens
    _exchange_code(client, auth_code[0])


def _exchange_code(client: dict, code: str):
    """Exchange an authorization code for tokens."""
    import urllib.parse
    import urllib.request

    params = urllib.parse.urlencode({
        "code": code,
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "redirect_uri": OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    try:
        req = urllib.request.Request(
            client.get("token_uri", "https://oauth2.googleapis.com/token"), data=params
        )
        with urllib.request.urlopen(req) as resp:
            token_data = json.loads(resp.read())
        token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        token_data["client_id"] = client["client_id"]
        # SECURITY: Never store client_secret in token file. It stays in client_secret.json only.
        token_data.pop("client_secret", None)
        _save_oauth_token(token_data)
        print("OAuth token saved successfully!")

        # Also save the OAuth client path to config
        config = load_config()
        # Don't overwrite existing config, just suggest
        print(f"\nToken saved to: {TOKEN_PATH}")
    except Exception as e:
        print(f"Error exchanging authorization code: {e}", file=sys.stderr)
        sys.exit(1)


def validate_url(url: str) -> bool:
    """
    Validate a URL for use with Google APIs. Rejects private/loopback addresses.

    Args:
        url: URL string to validate.

    Returns:
        True if the URL is a valid public http/https URL, False otherwise.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    blocked = [
        "localhost", "127.0.0.1", "0.0.0.0", "::1",
        "metadata.google.internal",
    ]
    if parsed.hostname in blocked:
        return False
    # Block private IP ranges (10.x, 172.16-31.x, 192.168.x)
    try:
        import ipaddress
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        pass  # Not an IP address (hostname), which is fine
    return True


def get_api_key() -> Optional[str]:
    """
    Get the Google API key from config or environment.

    Returns:
        API key string, or None if not configured.
    """
    config = load_config()
    return config.get("api_key")


def build_service(api_name: str, version: str, scopes: list):
    """
    Build a Google API discovery service client.

    Args:
        api_name: API name (e.g., 'searchconsole', 'indexing', 'pagespeedonline').
        version: API version (e.g., 'v1', 'v3', 'v5').
        scopes: OAuth scopes needed.

    Returns:
        googleapiclient.discovery.Resource object, or None on failure.
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print(
            "Error: google-api-python-client required. "
            "Install with: pip install google-api-python-client",
            file=sys.stderr,
        )
        return None

    credentials = get_oauth_credentials(scopes)
    if not credentials:
        return None

    try:
        service = build(api_name, version, credentials=credentials)
        return service
    except Exception as e:
        print(f"Error building {api_name} service: {e}", file=sys.stderr)
        return None


def check_credentials(service: str) -> dict:
    """
    Validate credentials for a specific Google API service.

    Args:
        service: One of 'psi', 'crux', 'crux_history', 'gsc', 'indexing', 'ga4'.

    Returns:
        Dictionary with:
            - available: bool
            - method: 'api_key' or 'service_account'
            - service: service name
            - error: error message or None
    """
    result = {
        "available": False,
        "method": SERVICE_AUTH.get(service, "unknown"),
        "service": SERVICE_NAMES.get(service, service),
        "error": None,
    }

    config = load_config()

    if SERVICE_AUTH.get(service) == "api_key":
        api_key = config.get("api_key")
        if api_key:
            result["available"] = True
        else:
            result["error"] = (
                "No API key found. Set GOOGLE_API_KEY environment variable "
                f"or add 'api_key' to {CONFIG_PATH}"
            )

    elif SERVICE_AUTH.get(service) == "oauth_or_sa":
        # Check OAuth token first
        token_data = _load_oauth_token()
        if token_data and token_data.get("access_token"):
            result["available"] = True
            result["method"] = "oauth_token"
            expired = time.time() > token_data.get("expires_at", 0) - 60
            if expired and token_data.get("refresh_token"):
                result["note"] = "Token expired but refresh_token available (will auto-refresh)"
            elif expired:
                result["available"] = False
                result["error"] = "OAuth token expired and no refresh_token. Re-run --auth."
        else:
            # Fall back to service account
            sa_path = config.get("service_account_path")
            if not sa_path:
                result["error"] = (
                    "No OAuth token or service account found. Either:\n"
                    "         1. Run: python scripts/google_auth.py --auth --creds /path/to/client_secret.json\n"
                    f"         2. Or add 'service_account_path' to {CONFIG_PATH}"
                )
            else:
                sa_path = os.path.expanduser(sa_path)
                if not os.path.exists(sa_path):
                    result["error"] = f"Service account file not found: {sa_path}"
                else:
                    try:
                        with open(sa_path, "r") as f:
                            sa_data = json.load(f)
                        if "client_email" not in sa_data or "private_key" not in sa_data:
                            result["error"] = "Service account JSON missing required fields (client_email, private_key)"
                        else:
                            result["available"] = True
                            result["method"] = "service_account"
                            result["client_email"] = sa_data.get("client_email")
                    except (json.JSONDecodeError, IOError) as e:
                        result["error"] = f"Invalid service account file: {e}"

        # GA4 also needs property ID
        if service == "ga4" and result["available"]:
            ga4_id = config.get("ga4_property_id")
            if not ga4_id:
                result["available"] = False
                result["error"] = (
                    "Credentials found but no GA4 property ID configured. "
                    f"Set GA4_PROPERTY_ID or add 'ga4_property_id' to {CONFIG_PATH}"
                )
    else:
        result["error"] = f"Unknown service: {service}"

    return result


def detect_tier() -> dict:
    """
    Detect the credential tier available.

    Returns:
        Dictionary with:
            - tier: 0, 1, or 2
            - description: human-readable tier description
            - capabilities: list of available API groups
            - missing: what's needed for the next tier
    """
    config = load_config()

    has_api_key = bool(config.get("api_key"))
    has_authenticated = False
    has_ga4 = False
    auth_method = None

    # Check OAuth token
    token_data = _load_oauth_token()
    if token_data and token_data.get("access_token"):
        has_authenticated = True
        auth_method = "oauth_token"

    # Check service account
    if not has_authenticated:
        sa_path = config.get("service_account_path")
        if sa_path:
            sa_path = os.path.expanduser(sa_path)
            if os.path.exists(sa_path):
                try:
                    with open(sa_path, "r") as f:
                        sa_data = json.load(f)
                    if "client_email" in sa_data and "private_key" in sa_data:
                        has_authenticated = True
                        auth_method = "service_account"
                except (json.JSONDecodeError, IOError):
                    pass

    if has_authenticated and config.get("ga4_property_id"):
        has_ga4 = True

    if has_ga4:
        return {
            "tier": 2,
            "description": "Full (API key + Service Account + GA4)",
            "capabilities": [
                "PageSpeed Insights", "CrUX", "CrUX History",
                "Search Console", "URL Inspection", "Sitemaps",
                "Indexing API", "GA4 Organic Traffic",
            ],
            "missing": None,
        }
    elif has_authenticated:
        return {
            "tier": 1,
            "description": "Authenticated (API key + OAuth/Service Account)",
            "capabilities": [
                "PageSpeed Insights", "CrUX", "CrUX History",
                "Search Console", "URL Inspection", "Sitemaps",
                "Indexing API",
            ],
            "missing": "Add 'ga4_property_id' to unlock GA4 organic traffic reports",
        }
    elif has_api_key:
        return {
            "tier": 0,
            "description": "API Key Only",
            "capabilities": [
                "PageSpeed Insights", "CrUX", "CrUX History",
            ],
            "missing": "Add a service account to unlock Search Console, URL Inspection, and Indexing API",
        }
    else:
        return {
            "tier": -1,
            "description": "No credentials configured",
            "capabilities": [],
            "missing": (
                f"Create config at {CONFIG_PATH} with at minimum an 'api_key' field. "
                "Run with --setup for full instructions."
            ),
        }


def print_setup_instructions():
    """Print step-by-step setup instructions."""
    print("""
Google SEO API Setup Instructions
=================================

1. CREATE A GOOGLE CLOUD PROJECT
   - Go to https://console.cloud.google.com
   - Create a new project (or select existing)
   - Note the project ID

2. ENABLE APIs
   In API Library (APIs & Services > Library), enable:
   - Google Search Console API
   - PageSpeed Insights API
   - Chrome UX Report API
   - Web Search Indexing API (for Indexing API)
   - Google Analytics Data API (for GA4)

3. CREATE AN API KEY (for PSI, CrUX -- free, no service account needed)
   - APIs & Services > Credentials > Create Credentials > API key
   - Restrict to: PageSpeed Insights API, Chrome UX Report API

4. CREATE A SERVICE ACCOUNT (for GSC, Indexing API, GA4)
   - IAM & Admin > Service Accounts > Create Service Account
   - Download JSON key file, store securely

5. GRANT ACCESS
   - Search Console: Settings > Users and permissions > Add user
     Paste the service account client_email, set as Owner (for Indexing API) or Full (read-only)
   - GA4: Admin > Property Access Management > Add
     Paste email, set Viewer role

6. CREATE CONFIG FILE
   mkdir -p ~/.config/claude-seo
   Save to ~/.config/claude-seo/google-api.json:

   {
     "service_account_path": "/path/to/service_account.json",
     "api_key": "AIzaSy...",
     "default_property": "sc-domain:example.com",
     "ga4_property_id": "properties/123456789"
   }

7. VERIFY
   python scripts/google_auth.py --check

ENVIRONMENT VARIABLE ALTERNATIVES:
   GOOGLE_API_KEY              - API key
   GOOGLE_APPLICATION_CREDENTIALS - Path to service account JSON
   GA4_PROPERTY_ID             - GA4 property ID (e.g., properties/123456789)
   GSC_PROPERTY                - Default Search Console property
""")


def main():
    parser = argparse.ArgumentParser(
        description="Google API credential management for Claude SEO"
    )
    parser.add_argument(
        "--check",
        nargs="?",
        const="all",
        metavar="SERVICE",
        help="Check credentials. Optionally specify service: psi, crux, gsc, indexing, ga4",
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
        "--auth",
        action="store_true",
        help="Run OAuth browser-based authentication flow",
    )
    parser.add_argument(
        "--exchange",
        action="store_true",
        help="Manually exchange an auth code for tokens",
    )
    parser.add_argument(
        "--creds",
        help="Path to OAuth client_secret JSON file (for --auth and --exchange)",
    )
    parser.add_argument(
        "--code",
        help="Authorization code to exchange (for --exchange)",
    )

    args = parser.parse_args()

    if args.auth:
        if not args.creds:
            print("Error: --creds is required with --auth", file=sys.stderr)
            sys.exit(1)
        run_oauth_flow(args.creds)
        return

    if args.exchange:
        if not args.creds or not args.code:
            print("Error: --creds and --code are required with --exchange", file=sys.stderr)
            sys.exit(1)
        client = _load_oauth_client(args.creds)
        if client:
            _exchange_code(client, args.code)
        return

    if args.setup:
        print_setup_instructions()
        return

    if args.tier:
        tier_info = detect_tier()
        if args.json:
            print(json.dumps(tier_info, indent=2))
        else:
            print(f"Credential Tier: {tier_info['tier']} -- {tier_info['description']}")
            if tier_info["capabilities"]:
                print(f"Available APIs: {', '.join(tier_info['capabilities'])}")
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
            output = {"tier": tier_info, "services": results}
            print(json.dumps(output, indent=2))
        else:
            tier_info = detect_tier()
            print(f"Credential Tier: {tier_info['tier']} -- {tier_info['description']}")
            print()
            for svc, result in results.items():
                status = "OK" if result["available"] else "MISSING"
                print(f"  [{status}] {result.get('service', svc)}")
                if result.get("error"):
                    print(f"         {result['error']}")
                if result.get("client_email"):
                    print(f"         Service account: {result['client_email']}")
            print()
            if tier_info["missing"]:
                print(f"Tip: {tier_info['missing']}")
        return

    # Default: show tier
    tier_info = detect_tier()
    if args.json:
        print(json.dumps(tier_info, indent=2))
    else:
        print(f"Credential Tier: {tier_info['tier']} -- {tier_info['description']}")
        if tier_info["missing"]:
            print(f"Run --setup for configuration instructions.")


if __name__ == "__main__":
    main()
