"""Functional tests for Google Cloud Natural Language routing."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import nlp_analyze  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_entity_extraction_uses_v1_and_other_features_use_v2() -> None:
    calls: list[dict] = []

    def fake_post(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        if url == nlp_analyze.NLP_V1_ENTITIES_ENDPOINT:
            return FakeResponse({
                "entities": [
                    {
                        "name": "Kenya",
                        "type": "LOCATION",
                        "salience": 0.9,
                        "metadata": {
                            "mid": "/m/019rg5",
                            "wikipedia_url": "https://en.wikipedia.org/wiki/Kenya",
                        },
                        "mentions": [{"text": {"content": "Kenya"}}],
                    }
                ]
            })
        return FakeResponse({
            "documentSentiment": {"score": 0.4, "magnitude": 1.2},
            "categories": [{"name": "/Sports", "confidence": 0.7}],
        })

    with patch.object(nlp_analyze.requests, "post", side_effect=fake_post):
        result = nlp_analyze.analyze_text(
            "Kenya has marathon runners.",
            features=["entities", "sentiment", "classify"],
            api_key="AI" + "zaSyDUMMYSECRET",
        )

    assert [call["url"] for call in calls] == [
        nlp_analyze.NLP_V1_ENTITIES_ENDPOINT,
        nlp_analyze.NLP_ENDPOINT,
    ]
    assert "features" not in calls[0]["json"]
    assert "extractEntities" not in calls[1]["json"]["features"]
    assert result["entities"][0]["metadata"]["mid"] == "/m/019rg5"
    assert result["entities"][0]["salience"] == 0.9
    assert result["sentiment"]["tone"] == "positive"
    assert result["categories"][0]["name"] == "/Sports"


def test_entities_only_skips_v2_annotate_text_call() -> None:
    calls: list[str] = []

    def fake_post(url: str, **kwargs):
        calls.append(url)
        return FakeResponse({"entities": []})

    with patch.object(nlp_analyze.requests, "post", side_effect=fake_post):
        result = nlp_analyze.analyze_text(
            "Kenya has marathon runners.",
            features=["entities"],
            api_key="AI" + "zaSyDUMMYSECRET",
        )

    assert calls == [nlp_analyze.NLP_V1_ENTITIES_ENDPOINT]
    assert result["error"] is None
