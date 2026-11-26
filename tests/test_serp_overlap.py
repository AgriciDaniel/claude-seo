"""Saved SERPs produce deterministic overlap evidence without network requests."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from serp_overlap import MAX_KEYWORDS, analyse, normalise_url  # noqa: E402


def _serp(keyword, prefix):
    return {"keyword": keyword, "urls": [f"https://example.com/{prefix}/{rank}" for rank in range(10)]}


@pytest.mark.parametrize("shared, relationship", [
    (0, "separate"), (1, "separate"), (2, "interlink"), (3, "interlink"),
    (4, "same_cluster"), (5, "same_cluster"), (6, "same_cluster"),
    (7, "same_post"), (8, "same_post"), (9, "same_post"), (10, "same_post"),
])
def test_exact_overlap_thresholds_and_symmetric_matrix(shared, relationship):
    left, right = _serp("Left keyword", "left"), _serp("Right keyword", "right")
    right["urls"][:shared] = left["urls"][:shared]

    result = analyse({"serps": [left, right]})

    assert result["serp_matrix"] == {
        "keywords": ["Left keyword", "Right keyword"],
        "scores": [[10, shared], [shared, 10]],
    }
    pair = result["pairs"][0]
    assert pair["relationship"] == relationship
    assert pair["score"] == pair["observed_shared_count"] == shared
    assert pair["shared_urls"] == left["urls"][:shared]
    assert pair["needs_review"] is (shared in {3, 4})
    assert result["complete"] is True


@pytest.mark.parametrize("url", [
    "HTTPS://EXAMPLE.COM:443/%7euser?utm_source=mail&id=7#heading",
    "https://example.com/~user?id=7&gclid=click",
    "https://example.com/~user?UTM_MEDIUM=email&id=7&fbclid=click",
])
def test_equivalent_spelling_and_attribution_do_not_hide_overlap(url):
    assert normalise_url(url) == "https://example.com/~user?id=7"


def test_unicode_host_and_path_match_the_encoded_url():
    assert normalise_url("https://bücher.example/café") == "https://xn--bcher-kva.example/caf%C3%A9"
    assert normalise_url("https://example.com/?q=café") == "https://example.com/?q=caf%C3%A9"


def test_ipv6_and_default_port_normalization():
    assert normalise_url("http://[2001:db8:0:0::1]:80/#x") == "http://[2001:db8::1]/"
    assert normalise_url("https://example.com:8443/") == "https://example.com:8443/"


@pytest.mark.parametrize("different", [
    "http://example.com/Product?id=1",
    "https://example.com/product?id=1",
    "https://example.com/Product/?id=1",
    "https://example.com/Product?id=2",
    "https://www.example.com/Product?id=1",
    "https://example.com/Product?id=1&id=2",
])
def test_distinct_resource_identities_are_not_merged(different):
    assert normalise_url(different) != normalise_url("https://example.com/Product?id=1")


@pytest.mark.parametrize("bad", [
    "relative/page", "mailto:hello@example.com", "https://[bad/page",
    "https://example.com:bad/", "https://user:password@example.com/",
    "https://example.com/a b", "https://example.com/%zz", "\x00https://example.com/", None,
])
def test_invalid_urls_are_coverage_gaps_without_backfilling(bad):
    left, right = _serp("Left", "left"), _serp("Right", "right")
    left["urls"][0] = bad
    left["urls"].append(right["urls"][0])

    result = analyse({"serps": [left, right]})

    assert result["serp_matrix"]["scores"] == [[None, None], [None, 10]]
    assert result["coverage"][0]["unique_top_ten_urls"] == 9
    assert result["coverage"][0]["invalid_results"][0]["rank"] == 1
    assert result["pairs"][0]["observed_shared_count"] == 0
    assert result["pairs"][0]["relationship"] == "inconclusive"
    assert result["complete"] is False


def test_duplicate_urls_cannot_inflate_the_overlap_score():
    repeated = {"keyword": "Repeated", "urls": [f"https://example.com/?utm_source={i}" for i in range(10)]}
    full = _serp("Full", "full")
    full["urls"][0] = "https://example.com/"

    result = analyse({"serps": [repeated, full]})

    assert result["coverage"][0]["duplicate_results"] == 9
    assert result["coverage"][0]["unique_top_ten_urls"] == 1
    assert result["pairs"][0]["observed_shared_count"] == 1
    assert result["pairs"][0]["score"] is None


@pytest.mark.parametrize("count", [0, 1, 7, 9])
def test_missing_results_are_not_evidence_for_separate_pages(count):
    row = _serp("Incomplete", "same")
    row["urls"] = row["urls"][:count]

    result = analyse({"serps": [row, _serp("Complete", "same")]})

    assert result["pairs"][0]["relationship"] == "inconclusive"
    assert result["pairs"][0]["observed_shared_count"] == count
    assert result["pairs"][0]["needs_review"] is True


def test_fetch_errors_remain_inconclusive_even_with_ten_saved_urls():
    row = _serp("Failed refresh", "same")
    row["error"] = "Provider request timed out"

    result = analyse({"serps": [row, _serp("Complete", "same")]})

    assert result["coverage"][0]["error"] == row["error"]
    assert result["pairs"][0]["observed_shared_count"] == 10
    assert result["pairs"][0]["score"] is None


def test_only_the_first_ten_organic_results_are_compared():
    rows = [_serp("Left", "left"), _serp("Right", "right")]
    for row in rows:
        row["urls"].extend(f"https://example.com/common/{i}" for i in range(10))

    result = analyse({"serps": rows})

    assert result["pairs"][0]["score"] == 0


def test_all_pairs_are_computed_once_without_mutating_input():
    payload = {"serps": [_serp(f"Keyword {i}", f"term-{i}") for i in range(40)]}
    before = json.dumps(payload)

    result = analyse(payload)

    assert result["comparisons"] == 780
    assert len(result["pairs"]) == 780
    assert json.dumps(payload) == before
    assert result == analyse(payload)


@pytest.mark.parametrize("payload", [
    [], {}, {"serps": []}, {"serps": [{}]},
    {"serps": [{"keyword": "   ", "urls": []}]},
    {"serps": [{"keyword": "One", "urls": "https://example.com/"}]},
    {"serps": [{"keyword": "One", "error": True}]},
    {"serps": [{"keyword": "One"}, {"keyword": " one "}]},
    {"serps": [{"keyword": "One Two"}, {"keyword": "one  two"}]},
])
def test_invalid_input_is_rejected(payload):
    with pytest.raises(ValueError):
        analyse(payload)


def test_keyword_count_is_bounded():
    with pytest.raises(ValueError, match=str(MAX_KEYWORDS)):
        analyse({"serps": [_serp(str(i), str(i)) for i in range(MAX_KEYWORDS + 1)]})


def test_cli_reads_stdin_and_writes_strict_json():
    payload = {"serps": [_serp("Left", "same"), _serp("Right", "same")]}
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/serp_overlap.py"), "-"],
        input=json.dumps(payload), capture_output=True, text=True, check=True,
    )

    assert json.loads(process.stdout)["pairs"][0]["score"] == 10
    assert process.stderr == ""


def test_cli_preserves_unicode_keywords_on_an_ascii_console():
    payload = {"serps": [_serp("词典迭代", "same")]}
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/serp_overlap.py"), "-"],
        input=json.dumps(payload), capture_output=True, text=True,
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )

    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["serp_matrix"]["keywords"] == ["词典迭代"]


def test_cli_accepts_a_utf8_bom_file(tmp_path):
    source = tmp_path / "results.json"
    source.write_text(json.dumps({"serps": [_serp("Single", "one")]}), encoding="utf-8-sig")
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/serp_overlap.py"), str(source)],
        capture_output=True, text=True, check=True,
    )

    assert json.loads(process.stdout)["serp_matrix"]["scores"] == [[10]]


def test_cli_reports_bad_input_as_json_with_nonzero_status():
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/serp_overlap.py"), "-"],
        input="{invalid", capture_output=True, text=True,
    )

    assert process.returncode == 2
    assert "error" in json.loads(process.stdout)
