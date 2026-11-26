"""Keyword ideas must follow the real Ads SDK pager without exceeding the cap."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

pytest.importorskip("google.ads.googleads")

import keyword_planner  # noqa: E402
from google.ads.googleads.client import GoogleAdsClient  # noqa: E402
from google.auth.credentials import AnonymousCredentials  # noqa: E402


def _idea(text, volume):
    return {
        "text": text,
        "keyword_idea_metrics": {
            "avg_monthly_searches": volume,
            "competition": "MEDIUM",
            "competition_index": 50,
            "low_top_of_page_bid_micros": 1_250_000,
            "high_top_of_page_bid_micros": 3_500_000,
            "monthly_search_volumes": [
                {"year": 2026, "month": "JANUARY", "monthly_searches": volume},
            ],
        },
    }


@pytest.fixture
def ads(monkeypatch):
    # The generated service constructs its real pager; only its RPC is replaced.
    # No credentials, network requests, or paid API calls are used.
    client = GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="unit-test",
        use_proto_plus=True,
    )
    service = client.get_service("KeywordPlanIdeaService")
    monkeypatch.setattr(client, "get_service", lambda name: service)
    monkeypatch.setattr(keyword_planner, "_build_ads_client", lambda: (client, "1234567890"))

    def install(pages):
        calls = []
        response_type = type(client.get_type("GenerateKeywordIdeaResponse"))

        def rpc(request, **kwargs):
            calls.append(type(request)(request))
            page = pages[request.page_token]
            if isinstance(page, Exception):
                raise page
            return response_type(**page)

        monkeypatch.setitem(
            service._transport._wrapped_methods,
            service._transport.generate_keyword_ideas,
            rpc,
        )
        return calls

    yield install
    service._transport.close()


def test_short_pages_reach_the_cap_and_preserve_metrics_and_targeting(ads):
    calls = ads({
        "": {"results": [_idea("one", 100)], "next_page_token": "second"},
        "second": {
            "results": [_idea("two", 300), _idea("three", 200), _idea("four", 900)],
        },
    })

    result = keyword_planner.generate_keyword_ideas(
        ["seo", "audit"], language_id="1001", location_id="2276", limit=3,
    )

    assert result["error"] is None
    assert [idea["keyword"] for idea in result["ideas"]] == ["two", "three", "one"]
    assert [call.page_token for call in calls] == ["", "second"]
    for call in calls:
        assert call.customer_id == "1234567890"
        assert call.language == "languageConstants/1001"
        assert list(call.geo_target_constants) == ["geoTargetConstants/2276"]
        assert list(call.keyword_seed.keywords) == ["seo", "audit"]
        assert call.keyword_plan_network.name == "GOOGLE_SEARCH"
    assert result["ideas"][0] == {
        "keyword": "two",
        "avg_monthly_searches": 300,
        "competition": "MEDIUM",
        "competition_index": 50,
        "low_top_of_page_bid": 1.25,
        "high_top_of_page_bid": 3.5,
        "monthly_volumes": [{"year": 2026, "month": 2, "volume": 300}],
    }


@pytest.mark.parametrize("limit", [1, 2])
def test_limit_within_or_at_first_page_does_not_request_next_page(ads, limit):
    calls = ads({
        "": {
            "results": [_idea("one", 100), _idea("two", 200)],
            "next_page_token": "must-not-fetch",
        },
    })

    result = keyword_planner.generate_keyword_ideas(["seo"], limit=limit)

    assert result["error"] is None
    assert len(result["ideas"]) == limit
    assert [call.page_token for call in calls] == [""]


def test_exact_later_page_boundary_does_not_request_another_page(ads):
    calls = ads({
        "": {"results": [_idea("one", 100)], "next_page_token": "second"},
        "second": {"results": [_idea("two", 200)], "next_page_token": "must-not-fetch"},
    })

    result = keyword_planner.generate_keyword_ideas(["seo"], limit=2)

    assert result["error"] is None
    assert len(result["ideas"]) == 2
    assert [call.page_token for call in calls] == ["", "second"]


def test_default_limit_is_honored_across_short_pages(ads):
    calls = ads({
        "": {"results": [_idea(f"first-{i}", 100) for i in range(49)], "next_page_token": "second"},
        "second": {
            "results": [_idea("fiftieth", 200), _idea("beyond-limit", 300)],
            "next_page_token": "must-not-fetch",
        },
    })

    result = keyword_planner.generate_keyword_ideas(["seo"])

    assert result["error"] is None
    assert len(result["ideas"]) == 50
    assert result["ideas"][0]["keyword"] == "fiftieth"
    assert [call.page_token for call in calls] == ["", "second"]


def test_empty_intermediate_page_follows_its_continuation_token(ads):
    calls = ads({
        "": {"results": [_idea("one", 100)], "next_page_token": "empty"},
        "empty": {"next_page_token": "last"},
        "last": {"results": [_idea("two", 200)]},
    })

    result = keyword_planner.generate_keyword_ideas(["seo"], limit=5)

    assert result["error"] is None
    assert [idea["keyword"] for idea in result["ideas"]] == ["two", "one"]
    assert [call.page_token for call in calls] == ["", "empty", "last"]


def test_empty_final_page_is_a_successful_empty_result(ads):
    calls = ads({"": {}})

    result = keyword_planner.generate_keyword_ideas(["seo"])

    assert result["error"] is None
    assert result["ideas"] == []
    assert len(calls) == 1


def test_following_page_failure_is_reported_instead_of_silent_truncation(ads):
    calls = ads({
        "": {"results": [_idea("one", 100)], "next_page_token": "second"},
        "second": RuntimeError("upstream unavailable"),
    })

    result = keyword_planner.generate_keyword_ideas(["seo"], limit=2)

    assert result["error"] == "Keyword Planner error: upstream unavailable"
    assert [idea["keyword"] for idea in result["ideas"]] == ["one"]
    assert len(calls) == 2


@pytest.mark.parametrize("json_output", [False, True])
def test_cli_includes_an_idea_from_the_following_page(ads, monkeypatch, capsys, json_output):
    ads({
        "": {"results": [_idea("first-page", 100)], "next_page_token": "second"},
        "second": {"results": [_idea("later-page", 200)]},
    })
    argv = ["keyword_planner.py", "ideas", "seo", "--limit", "2"]
    if json_output:
        argv.append("--json")
    monkeypatch.setattr(sys, "argv", argv)

    keyword_planner.main()

    output = capsys.readouterr()
    assert output.err == ""
    if json_output:
        assert [idea["keyword"] for idea in json.loads(output.out)["ideas"]] == [
            "later-page", "first-page",
        ]
    else:
        assert "later-page" in output.out
        assert "first-page" in output.out
