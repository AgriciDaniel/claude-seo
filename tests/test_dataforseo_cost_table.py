"""The DataForSEO cost table is keyed on v3 paths, priced from the pricing page.

COST_TABLE keys are the endpoint paths DataForSEO bills (and that
dataforseo-mcp-server 3.x takes as `path`). V2_ALIASES keeps the 2.8.10 tool
names working, so skills that still pass them hit the same budget gate.
Prices: https://dataforseo.com/pricing, read 2026-11-15.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dataforseo_costs.py"
_spec = importlib.util.spec_from_file_location("dataforseo_costs", _SCRIPT)
costs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(costs)


def _run(config_dir: Path, *argv: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("DATAFORSEO_")}
    env["CLAUDE_SEO_CONFIG_DIR"] = str(config_dir)
    proc = subprocess.run([sys.executable, str(_SCRIPT), *argv],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# --- table shape ------------------------------------------------------------


def test_every_key_is_a_v3_path_with_a_valid_price_shape() -> None:
    for path, price in costs.COST_TABLE.items():
        assert path.startswith("/v3/") and not path.endswith("/"), path
        assert price["task"] > 0, path
        assert ("block" in price) != ("item" in price), path
        if "block" in price:
            assert isinstance(price["block"], int) and price["block"] > 0, path


def test_every_v2_alias_points_at_a_priced_path() -> None:
    missing = {k: v for k, v in costs.V2_ALIASES.items() if v not in costs.COST_TABLE}
    assert not missing


def test_warn_endpoints_are_priced_paths() -> None:
    assert costs.WARN_ENDPOINTS <= set(costs.COST_TABLE)


def test_images_regular_has_no_v3_endpoint_and_is_not_priced() -> None:
    assert "serp_google_images_live_regular" not in costs.V2_ALIASES
    assert costs.canonical_endpoint("serp_google_images_live_regular") not in costs.COST_TABLE


# --- name resolution --------------------------------------------------------


@pytest.mark.parametrize("spelling", [
    "serp_organic_live_advanced",
    "/v3/serp/google/organic/live/advanced",
    "v3/serp/google/organic/live/advanced",
    "/v3/serp/google/organic/live/advanced/",
    "/v3/serp/google/organic/live/advanced.ai",
    "serp/google/organic/live/advanced",
    "  /v3/serp/google/organic/live/advanced  ",
])
def test_spellings_resolve_to_the_same_key(spelling: str) -> None:
    assert costs.canonical_endpoint(spelling) == "/v3/serp/google/organic/live/advanced"


def test_unknown_names_are_returned_unchanged() -> None:
    assert costs.canonical_endpoint("not_an_endpoint") == "not_an_endpoint"
    assert costs.canonical_endpoint("/v3/serp/google/news/live/advanced") == \
        "/v3/serp/google/news/live/advanced"


# --- prices (figures from the pricing pages) --------------------------------


@pytest.mark.parametrize("endpoint, items, expected", [
    # SERP: $0.002 per SERP of 10 results, depth rounded up to the next ten
    ("/v3/serp/google/organic/live/advanced", None, 0.002),
    ("/v3/serp/google/organic/live/advanced", 15, 0.004),
    ("/v3/serp/google/organic/live/advanced", 100, 0.02),
    # Images: $0.002 per SERP of 100 results
    ("/v3/serp/google/images/live/advanced", 100, 0.002),
    # Labs: $0.012 per task + $0.00012 per item
    ("/v3/dataforseo_labs/google/keyword_suggestions/live", 100, 0.024),
    ("/v3/dataforseo_labs/google/keyword_suggestions/live", 0, 0.012),
    # Google Ads: $0.09 per task, billed for setting the task only
    ("/v3/keywords_data/google_ads/search_volume/live", 1000, 0.09),
    # LLM Mentions: $0.1 per task + $0.001 per row
    ("/v3/ai_optimization/llm_mentions/search/live", 100, 0.2),
    # Backlinks: $0.024 per task + $0.000036 per row
    ("/v3/backlinks/backlinks/live", 1000, 0.06),
    # On-Page Instant Pages: $0.00015 per task
    ("/v3/on_page/instant_pages", None, 0.00015),
    # Merchant Google Shopping, standard queue: $0.001 per SERP of 40 products
    ("/v3/merchant/google/products/task_post", 120, 0.003),
])
def test_call_cost(endpoint: str, items, expected: float) -> None:
    cost, _ = costs.call_cost(endpoint, items)
    assert cost == pytest.approx(expected)


def test_per_item_endpoints_assume_default_items_when_not_given() -> None:
    cost, items = costs.call_cost("/v3/ai_optimization/llm_mentions/search/live")
    assert items == costs.DEFAULT_ITEMS
    assert cost == pytest.approx(0.1 + 0.001 * costs.DEFAULT_ITEMS)


# --- CLI ----------------------------------------------------------------------


def test_check_with_v2_name_and_path_agree(tmp_path) -> None:
    by_name = _run(tmp_path, "check", "dataforseo_labs_google_ranked_keywords", "--items", "500")
    by_path = _run(tmp_path, "check", "/v3/dataforseo_labs/google/ranked_keywords/live",
                   "--items", "500")
    assert by_name["endpoint"] == by_path["endpoint"]
    assert by_name["total_cost_usd"] == by_path["total_cost_usd"] == pytest.approx(0.072)


def test_check_multiplies_by_count(tmp_path) -> None:
    out = _run(tmp_path, "check", "serp_organic_live_advanced", "--count", "50")
    assert out["status"] == "approved"
    assert out["total_cost_usd"] == pytest.approx(0.1)


def test_warn_endpoint_reached_by_v2_name(tmp_path) -> None:
    out = _run(tmp_path, "check", "ai_opt_llm_ment_search")
    assert out["status"] == "needs_approval"
    assert out["approval_reason"] == "warn_endpoint"


def test_saved_config_with_v2_warn_names_still_warns(tmp_path) -> None:
    (tmp_path / "dataforseo-costs.json").write_text(json.dumps({
        "mode": "none", "threshold": 0.5, "daily_limit": 10.0,
        "warn_endpoints": ["backlinks_backlinks"],
    }))
    out = _run(tmp_path, "check", "/v3/backlinks/backlinks/live", "--items", "10")
    assert out["approval_reason"] == "warn_endpoint"


def test_unknown_endpoint_fails_closed(tmp_path) -> None:
    out = _run(tmp_path, "check", "serp_google_images_live_regular")
    assert out["status"] == "needs_approval"
    assert out["approval_reason"] == "unknown_endpoint"


def test_estimate_suggests_matches_for_a_partial_name(tmp_path) -> None:
    out = _run(tmp_path, "estimate", "llm_mentions")
    assert out["status"] == "unknown_endpoint"
    assert "/v3/ai_optimization/llm_mentions/search/live" in out["suggestions"]


def test_log_stores_the_v3_path_for_a_v2_name(tmp_path) -> None:
    _run(tmp_path, "log", "on_page_lighthouse", "0.005")
    entries = json.loads((tmp_path / "dataforseo-ledger.json").read_text())["entries"]
    assert entries[-1]["endpoint"] == "/v3/on_page/lighthouse/live/json"


def test_negative_items_are_rejected(tmp_path) -> None:
    env = dict(os.environ, CLAUDE_SEO_CONFIG_DIR=str(tmp_path))
    proc = subprocess.run([sys.executable, str(_SCRIPT), "estimate",
                           "backlinks_summary", "--items", "-1"],
                          capture_output=True, text=True, env=env)
    assert proc.returncode != 0
    assert "must be 0 or greater" in proc.stderr
