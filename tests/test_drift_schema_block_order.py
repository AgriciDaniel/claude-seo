"""Schema block ordering must not create a structured-data drift alert."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import drift_baseline as capture  # noqa: E402
import drift_compare as compare  # noqa: E402

BLOCKS = [
    {"@context": "https://schema.org", "@type": "Organization", "name": "Example"},
    {"@context": "https://schema.org", "@type": "WebSite", "url": "https://example.com/"},
]


def legacy_baseline(blocks):
    return {
        "schema_json": json.dumps(blocks),
        "schema_hash": capture.hash_content(json.dumps(blocks, sort_keys=True)) if blocks else None,
    }


def test_reordering_blocks_does_not_trigger_drift_for_existing_baselines():
    finding = compare.rule_14_schema_modified(legacy_baseline(BLOCKS), {"schema": BLOCKS[::-1]})
    assert not finding["triggered"]
    assert finding["old_value"] == finding["new_value"]


def test_property_order_does_not_trigger_drift():
    reordered = [dict(reversed(list(block.items()))) for block in BLOCKS]
    assert not compare.rule_14_schema_modified(legacy_baseline(BLOCKS), {"schema": reordered})["triggered"]


@pytest.mark.parametrize("change", ["value", "remove_block", "duplicate_block", "ordered_list", "context"])
def test_meaningful_changes_still_trigger_drift(change):
    before = copy.deepcopy(BLOCKS)
    before[0]["keywords"] = {"@list": ["alpha", "beta"]}
    before[0]["@context"] = ["https://schema.org", {"label": "name"}]
    after = copy.deepcopy(before)
    if change == "value":
        after[0]["name"] = "Changed"
    elif change == "remove_block":
        after.pop()
    elif change == "duplicate_block":
        after.append(copy.deepcopy(after[0]))
    elif change == "ordered_list":
        after[0]["keywords"]["@list"].reverse()
    else:
        after[0]["@context"].reverse()
    assert compare.rule_14_schema_modified(legacy_baseline(before), {"schema": after})["triggered"]


@pytest.mark.parametrize("old,new", [([], BLOCKS), (BLOCKS, [])])
def test_addition_and_removal_remain_the_other_rules_responsibility(old, new):
    assert not compare.rule_14_schema_modified(legacy_baseline(old), {"schema": new})["triggered"]


@pytest.mark.parametrize("changed", [False, True])
def test_hash_only_baselines_keep_their_existing_comparison(changed):
    baseline = legacy_baseline(BLOCKS)
    baseline.pop("schema_json")
    after = copy.deepcopy(BLOCKS)
    if changed:
        after[0]["name"] = "Changed"
    assert compare.rule_14_schema_modified(baseline, {"schema": after})["triggered"] is changed


def test_captured_baseline_ignores_block_order_without_rewriting_stored_json(monkeypatch, tmp_path):
    monkeypatch.setattr(capture, "DB_DIR", str(tmp_path))
    monkeypatch.setattr(capture, "DB_PATH", str(tmp_path / "baseline.db"))
    monkeypatch.setattr(capture, "validate_url", lambda url: True)
    page = {"status_code": 200, "html": "<html></html>", "parsed": {"schema": BLOCKS}, "error": None}
    monkeypatch.setattr(capture, "fetch_page_data", lambda url: page)
    first = capture.capture_baseline("https://example.com/", skip_cwv=True)
    page["parsed"]["schema"] = BLOCKS[::-1]
    second = capture.capture_baseline("https://example.com/", skip_cwv=True)
    conn = capture.init_db()
    try:
        records = conn.execute("SELECT schema_hash, schema_json FROM baselines ORDER BY id").fetchall()
        loaded = compare.load_baseline(conn, capture.url_hash("https://example.com/"), first["baseline_id"])
    finally:
        conn.close()
    assert first["status"] == second["status"] == "ok"
    assert json.loads(records[0][1]) == BLOCKS
    assert json.loads(records[1][1]) == BLOCKS[::-1]
    assert not compare.rule_14_schema_modified(loaded, page["parsed"])["triggered"]
