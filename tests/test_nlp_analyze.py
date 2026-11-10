"""Functional tests for Google Cloud Natural Language routing."""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
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


def test_each_endpoint_gets_its_own_language_field_name() -> None:
    """v1 analyzeEntities names the field "language" and rejects "languageCode"
    with HTTP 400; v2 annotateText names it "languageCode"."""
    bodies: dict[str, dict] = {}

    def fake_post(url: str, **kwargs):
        bodies[url] = kwargs["json"]
        if url == nlp_analyze.NLP_V1_ENTITIES_ENDPOINT:
            return FakeResponse({"entities": []})
        return FakeResponse({"documentSentiment": {"score": 0.0, "magnitude": 0.0}})

    with patch.object(nlp_analyze.requests, "post", side_effect=fake_post):
        nlp_analyze.analyze_text(
            "O Quénia tem corredores de maratona.",
            features=["entities", "sentiment"],
            api_key="AI" + "zaSyDUMMYSECRET",
            language="pt",
        )

    v1_document = bodies[nlp_analyze.NLP_V1_ENTITIES_ENDPOINT]["document"]
    v2_document = bodies[nlp_analyze.NLP_ENDPOINT]["document"]
    assert v1_document["language"] == "pt"
    assert "languageCode" not in v1_document
    assert v2_document["languageCode"] == "pt"
    assert "language" not in v2_document
    assert v1_document["content"] == v2_document["content"]


def _capture_bodies(bodies: dict[str, dict]):
    def fake_post(url: str, **kwargs):
        bodies[url] = kwargs["json"]
        if url == nlp_analyze.NLP_V1_ENTITIES_ENDPOINT:
            return FakeResponse({"entities": [], "language": "pt"})
        return FakeResponse({
            "documentSentiment": {"score": 0.0, "magnitude": 0.0},
            "languageCode": "pt",
        })

    return fake_post


@pytest.mark.parametrize("features", [["entities", "sentiment"], ["entities"], ["sentiment"]])
def test_language_is_omitted_by_default_so_the_api_detects_it(features) -> None:
    """Issue #322: the language was hard-coded to "en" for every document."""
    bodies: dict[str, dict] = {}

    with patch.object(nlp_analyze.requests, "post", side_effect=_capture_bodies(bodies)):
        result = nlp_analyze.analyze_text(
            "O Quenia tem corredores de maratona.",
            features=features,
            api_key="AI" + "zaSyDUMMYSECRET",
        )

    assert bodies
    for body in bodies.values():
        assert "language" not in body["document"]
        assert "languageCode" not in body["document"]
    assert result["language"] == "pt"
    assert result["error"] is None


@pytest.mark.parametrize("source", ["text", "url"])
def test_cli_language_option_reaches_both_request_bodies(source, capsys) -> None:
    bodies: dict[str, dict] = {}
    page = "<html><body><p>" + "O Quenia tem corredores de maratona. " * 3 + "</p></body></html>"
    argv = ["nlp_analyze.py", "--language", "pt-BR", "--features", "entities,sentiment",
            "--api-key", "AI" + "zaSyDUMMYSECRET", "--json"]
    argv += ["--text", "O Quenia tem corredores."] if source == "text" else ["--url", "https://example.com/"]

    with patch.object(sys, "argv", argv), \
         patch.object(nlp_analyze, "validate_url", return_value=True), \
         patch.object(nlp_analyze, "safe_requests_get", return_value=FakeResponse({})), \
         patch.object(nlp_analyze, "decode_response_text", return_value=page), \
         patch.object(nlp_analyze.requests, "post", side_effect=_capture_bodies(bodies)):
        nlp_analyze.main()

    assert bodies[nlp_analyze.NLP_V1_ENTITIES_ENDPOINT]["document"]["language"] == "pt-BR"
    assert bodies[nlp_analyze.NLP_ENDPOINT]["document"]["languageCode"] == "pt-BR"
    assert json.loads(capsys.readouterr().out)["language"] == "pt-BR"


@pytest.mark.parametrize("value", ["", "english!", "pt_BR", "e", "en-", "en us"])
def test_cli_rejects_a_value_that_is_not_a_language_code(value, capsys) -> None:
    argv = ["nlp_analyze.py", "--text", "Kenya has marathon runners.", "--language", value]

    with patch.object(sys, "argv", argv), \
         patch.object(nlp_analyze.requests, "post") as post, \
         pytest.raises(SystemExit) as exit_info:
        nlp_analyze.main()

    assert exit_info.value.code == 2
    assert "not a language code" in capsys.readouterr().err
    post.assert_not_called()


@pytest.mark.parametrize("value", ["en", "pt-BR", "zh-Hant", "zh-Hant-TW", "fil", "es-419"])
def test_language_code_accepts_bcp47_looking_tags(value) -> None:
    assert nlp_analyze.language_code(f" {value} ") == value
