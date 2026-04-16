#!/usr/bin/env python3
"""
Google Ads API - Keyword Planner for SEO keyword research.

Gold-standard source for keyword search volume, CPC, and competition data.
Requires a Google Ads Manager account with a developer token.

Usage:
    python keyword_planner.py ideas "seo tools" --json
    python keyword_planner.py volume "seo tools,seo audit,seo checker" --json
    python keyword_planner.py forecast "seo tools" --json

Prerequisites:
    - Google Ads Manager account (can be free)
    - Developer Token (apply at Google Ads API Center)
    - OAuth credentials or service account
    - google-ads Python library: pip install google-ads
    - Config: ~/.config/claude-seo/google-api.json with:
      {
        "ads_developer_token": "YOUR_DEV_TOKEN",
        "ads_customer_id": "123-456-7890",
        "ads_login_customer_id": "123-456-7890"
      }

Note: Accounts without active ad spend receive bucketed volume ranges
(e.g., "1K-10K") instead of exact numbers.
"""

import argparse
import json
import sys
from typing import Optional

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    HAS_GOOGLE_ADS = True
except ImportError:
    HAS_GOOGLE_ADS = False

try:
    from google_auth import load_config
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from google_auth import load_config


def _build_ads_client() -> Optional[object]:
    """Build Google Ads client from config."""
    if not HAS_GOOGLE_ADS:
        print(
            "Error: google-ads library required. Install with: pip install google-ads",
            file=sys.stderr,
        )
        return None

    config = load_config()
    dev_token = config.get("ads_developer_token")
    customer_id = config.get("ads_customer_id", "").replace("-", "")
    login_customer_id = config.get("ads_login_customer_id", "").replace("-", "")
    oauth_client_path = config.get("oauth_client_path")

    if not dev_token:
        print(
            "Error: No Google Ads developer token configured. "
            "Add 'ads_developer_token' to ~/.config/claude-seo/google-api.json. "
            "Get a token at: https://ads.google.com/aw/apicenter",
            file=sys.stderr,
        )
        return None

    if not customer_id:
        print(
            "Error: No Google Ads customer ID configured. "
            "Add 'ads_customer_id' (format: 123-456-7890) to config.",
            file=sys.stderr,
        )
        return None

    try:
        # Build from dict configuration
        ads_config = {
            "developer_token": dev_token,
            "use_proto_plus": True,
        }
        if login_customer_id:
            ads_config["login_customer_id"] = login_customer_id

        # Try to use OAuth token if available
        token_path = os.path.expanduser("~/.config/claude-seo/oauth-token.json")
        if os.path.exists(token_path):
            with open(token_path) as f:
                token_data = json.load(f)
            if oauth_client_path:
                with open(os.path.expanduser(oauth_client_path)) as f:
                    client_data = json.load(f)
                client_info = client_data.get("web", client_data.get("installed", {}))
                ads_config["client_id"] = client_info.get("client_id")
                ads_config["client_secret"] = client_info.get("client_secret")
                ads_config["refresh_token"] = token_data.get("refresh_token")

        client = GoogleAdsClient.load_from_dict(ads_config)
        return client, customer_id

    except Exception as e:
        print(f"Error building Google Ads client: {e}", file=sys.stderr)
        return None


def generate_keyword_ideas(
    seed_keywords: list,
    language_id: str = "1000",
    location_id: str = "2840",
    limit: int = 50,
) -> dict:
    """
    Generate keyword ideas from seed keywords.

    Args:
        seed_keywords: List of seed keyword strings.
        language_id: Language ID (1000 = English).
        location_id: Location ID (2840 = United States).
        limit: Max results.

    Returns:
        Dictionary with keyword ideas and metrics.
    """
    result = {
        "seed_keywords": seed_keywords,
        "ideas": [],
        "error": None,
    }

    client_data = _build_ads_client()
    if not client_data:
        result["error"] = "Could not build Google Ads client. Check config."
        return result

    client, customer_id = client_data

    try:
        kp_service = client.get_service("KeywordPlanIdeaService")
        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = customer_id
        request.language = f"languageConstants/{language_id}"
        request.geo_target_constants.append(f"geoTargetConstants/{location_id}")
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        request.keyword_seed.keywords.extend(seed_keywords)

        response = kp_service.generate_keyword_ideas(request=request)

        for idea in response.results:
            metrics = idea.keyword_idea_metrics
            monthly_volumes = []
            for mv in metrics.monthly_search_volumes:
                monthly_volumes.append({
                    "year": mv.year,
                    "month": mv.month,
                    "volume": mv.monthly_searches,
                })

            result["ideas"].append({
                "keyword": idea.text,
                "avg_monthly_searches": metrics.avg_monthly_searches,
                "competition": metrics.competition.name if metrics.competition else "UNSPECIFIED",
                "competition_index": metrics.competition_index,
                "low_top_of_page_bid": metrics.low_top_of_page_bid_micros / 1_000_000 if metrics.low_top_of_page_bid_micros else None,
                "high_top_of_page_bid": metrics.high_top_of_page_bid_micros / 1_000_000 if metrics.high_top_of_page_bid_micros else None,
                "monthly_volumes": monthly_volumes[-12:] if monthly_volumes else [],
            })

            if len(result["ideas"]) >= limit:
                break

        # Sort by volume descending
        result["ideas"].sort(key=lambda k: k.get("avg_monthly_searches", 0) or 0, reverse=True)

    except GoogleAdsException as e:
        errors = [err.message for err in e.failure.errors]
        result["error"] = f"Google Ads API error: {'; '.join(errors)}"
    except Exception as e:
        result["error"] = f"Keyword Planner error: {e}"

    return result


def get_keyword_volumes(
    keywords: list,
    language_id: str = "1000",
    location_id: str = "2840",
) -> dict:
    """
    Get search volume for specific keywords.

    Args:
        keywords: List of keywords to check.
        language_id: Language ID.
        location_id: Location ID.

    Returns:
        Dictionary with keyword metrics.
    """
    result = {
        "keywords": [],
        "error": None,
    }

    client_data = _build_ads_client()
    if not client_data:
        result["error"] = "Could not build Google Ads client."
        return result

    client, customer_id = client_data

    try:
        kp_service = client.get_service("KeywordPlanIdeaService")
        request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
        request.customer_id = customer_id
        request.keywords.extend(keywords)
        request.language = f"languageConstants/{language_id}"
        request.geo_target_constants.append(f"geoTargetConstants/{location_id}")
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

        response = kp_service.generate_keyword_historical_metrics(request=request)

        for kw_result in response.results:
            metrics = kw_result.keyword_metrics
            result["keywords"].append({
                "keyword": kw_result.text,
                "avg_monthly_searches": metrics.avg_monthly_searches,
                "competition": metrics.competition.name if metrics.competition else "UNSPECIFIED",
                "competition_index": metrics.competition_index,
                "low_top_of_page_bid": metrics.low_top_of_page_bid_micros / 1_000_000 if metrics.low_top_of_page_bid_micros else None,
                "high_top_of_page_bid": metrics.high_top_of_page_bid_micros / 1_000_000 if metrics.high_top_of_page_bid_micros else None,
            })

    except GoogleAdsException as e:
        errors = [err.message for err in e.failure.errors]
        result["error"] = f"Google Ads API error: {'; '.join(errors)}"
    except Exception as e:
        result["error"] = f"Keyword volume error: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Google Ads Keyword Planner - SEO keyword research"
    )
    parser.add_argument(
        "command",
        choices=["ideas", "volume"],
        help="Command: ideas (keyword suggestions), volume (search volume lookup)",
    )
    parser.add_argument("keywords", help="Seed keyword(s), comma-separated for volume")
    parser.add_argument("--limit", type=int, default=50, help="Max results for ideas (default: 50)")
    parser.add_argument("--language", default="1000", help="Language ID (default: 1000 = English)")
    parser.add_argument("--location", default="2840", help="Location ID (default: 2840 = US)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "ideas":
        seeds = [k.strip() for k in args.keywords.split(",")]
        result = generate_keyword_ideas(seeds, language_id=args.language, location_id=args.location, limit=args.limit)
    elif args.command == "volume":
        kws = [k.strip() for k in args.keywords.split(",")]
        result = get_keyword_volumes(kws, language_id=args.language, location_id=args.location)

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        if not args.json:
            sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        if args.command == "ideas":
            print(f"=== Keyword Ideas ===")
            for i, idea in enumerate(result.get("ideas", [])[:20], 1):
                vol = idea.get("avg_monthly_searches", "?")
                comp = idea.get("competition", "?")
                bid_low = idea.get("low_top_of_page_bid")
                bid_high = idea.get("high_top_of_page_bid")
                bid_str = f"${bid_low:.2f}-${bid_high:.2f}" if bid_low and bid_high else "N/A"
                print(f"  {i:2d}. {idea['keyword']:40s} | Vol: {vol:>8} | Comp: {comp:8s} | CPC: {bid_str}")
        elif args.command == "volume":
            print(f"=== Keyword Volumes ===")
            for kw in result.get("keywords", []):
                vol = kw.get("avg_monthly_searches", "?")
                comp = kw.get("competition", "?")
                print(f"  {kw['keyword']:40s} | Vol: {vol:>8} | Comp: {comp}")


if __name__ == "__main__":
    main()
