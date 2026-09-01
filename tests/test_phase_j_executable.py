"""
Tests for Phase J executable layer:
    scripts/ucp_check.py             — UCP profile discovery + validation
    scripts/iptc_ai_label.py         — IPTC DigitalSourceType audit + inject
    scripts/agent_ux_check.py        — agent-friendly page scorer
    scripts/render_page.py           — extract_accessibility extension

Tests are pure (no network, no exiftool, no Playwright). External
dependencies are either mocked or short-circuited via the public API
surface of each script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import agent_ux_check  # noqa: E402
import iptc_ai_label  # noqa: E402
import render_page  # noqa: E402
import ucp_check  # noqa: E402

# ---------------------------------------------------------------------------
# ucp_check
# ---------------------------------------------------------------------------


def test_discovery_url_for_normalizes_to_well_known():
    assert (
        ucp_check.discovery_url_for("https://store.example.com")
        == "https://store.example.com/.well-known/ucp"
    )
    # Bare hostname gets https:// prefixed.
    assert (
        ucp_check.discovery_url_for("store.example.com")
        == "https://store.example.com/.well-known/ucp"
    )
    # Path on the input is discarded.
    assert (
        ucp_check.discovery_url_for("https://store.example.com/path/here")
        == "https://store.example.com/.well-known/ucp"
    )


def test_parse_profile_rejects_malformed_json():
    report = ucp_check.parse_profile("{ not json")
    assert report["valid_json"] is False
    assert any("invalid-json" in issue for issue in report["issues"])


def test_parse_profile_valid_minimal_profile():
    payload = json.dumps({
        "version": "1.0",
        "merchant": {"name": "Example Co.", "id": "MC-42"},
        "capabilities": [
            {
                "id": "dev.ucp.shopping.checkout",
                "version": "1.0",
                "endpoint": "https://api.example.com/ucp/checkout",
            }
        ],
    })
    report = ucp_check.parse_profile(payload)
    assert report["valid_json"] is True
    assert report["version"] == "1.0"
    assert report["merchant"] == {"name": "Example Co.", "id": "MC-42"}
    assert len(report["capabilities"]) == 1
    assert report["capabilities"][0]["id"] == "dev.ucp.shopping.checkout"
    assert report["issues"] == []


def test_parse_profile_flags_missing_fields_and_unknown_capability():
    payload = json.dumps({
        "capabilities": [
            {
                "id": "dev.ucp.unknown.thing",
                # missing version, missing endpoint
            },
            {
                # missing id
                "version": "1.0",
                "endpoint": "https://api.example.com/x",
            },
        ],
    })
    report = ucp_check.parse_profile(payload)
    assert "missing-version" in report["issues"]
    assert "missing-merchant" in report["issues"]
    assert "dev.ucp.unknown.thing" in report["unknown_capabilities"]
    cap0 = report["capabilities"][0]
    assert "missing-version" in cap0["issues"]
    assert "missing-endpoint" in cap0["issues"]
    cap1 = report["capabilities"][1]
    assert "missing-id" in cap1["issues"]


def test_parse_profile_rejects_non_object_root():
    report = ucp_check.parse_profile(json.dumps(["not", "an", "object"]))
    assert "profile-not-object" in report["issues"]


def test_known_capabilities_cover_core_commerce_verbs():
    # Sanity check on the documented vocabulary.
    for cap in ("dev.ucp.shopping.checkout",
                 "dev.ucp.shopping.fulfillment",
                 "dev.ucp.shopping.discount"):
        assert cap in ucp_check.KNOWN_CAPABILITIES


# ---------------------------------------------------------------------------
# iptc_ai_label
# ---------------------------------------------------------------------------


def test_iptc_vocab_contains_required_merchant_center_value():
    # Google Merchant Center requires this exact label on AI-generated images.
    assert "trainedAlgorithmicMedia" in iptc_ai_label.IPTC_VOCAB
    uri = iptc_ai_label.IPTC_VOCAB["trainedAlgorithmicMedia"]
    assert uri.startswith("https://cv.iptc.org/")
    assert uri.endswith("/trainedAlgorithmicMedia")


def test_audit_reports_target_not_found(tmp_path):
    report = iptc_ai_label.audit(tmp_path / "nope.jpg")
    assert report["summary"] == {"error": "target-not-found"}


def test_audit_reports_exiftool_unavailable(tmp_path, monkeypatch):
    # Create a real file so we get past the target-exists check.
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")  # tiny stub
    monkeypatch.setattr(iptc_ai_label, "exiftool_available", lambda: False)
    report = iptc_ai_label.audit(img)
    assert report["summary"] == {"error": "exiftool-not-installed"}


def test_inject_rejects_unknown_source_type(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    out = iptc_ai_label.inject(img, "totallyMadeUpType")
    assert out["ok"] is False
    assert "unknown source_type" in out["error"]


def test_inject_reports_missing_exiftool(tmp_path, monkeypatch):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(iptc_ai_label, "exiftool_available", lambda: False)
    out = iptc_ai_label.inject(img, "trainedAlgorithmicMedia")
    assert out["ok"] is False
    assert out["error"] == "exiftool-not-installed"


def test_inject_succeeds_when_subprocess_returns_zero(tmp_path, monkeypatch):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(iptc_ai_label, "exiftool_available", lambda: True)

    fake_result = mock.Mock(returncode=0, stdout="ok", stderr="")
    with mock.patch.object(iptc_ai_label.subprocess, "run", return_value=fake_result):
        out = iptc_ai_label.inject(img, "trainedAlgorithmicMedia")
    assert out["ok"] is True
    assert out["error"] is None


def test_audit_classifies_files_via_mocked_exiftool(tmp_path, monkeypatch):
    # Lay out three images: one labeled correctly, one unlabeled, one with a
    # different source type. Mock _read_source_type to return canned values.
    for name in ("ai.jpg", "missing.jpg", "real.jpg"):
        (tmp_path / name).write_bytes(b"\xff\xd8\xff\xd9")

    monkeypatch.setattr(iptc_ai_label, "exiftool_available", lambda: True)
    values = {
        tmp_path / "ai.jpg": (
            "https://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
        ),
        tmp_path / "missing.jpg": None,
        tmp_path / "real.jpg": (
            "https://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture"
        ),
    }
    monkeypatch.setattr(iptc_ai_label, "_read_source_type",
                        lambda p: values[p])
    report = iptc_ai_label.audit(tmp_path)
    summary = report["summary"]
    assert summary["total"] == 3
    assert summary["trainedAlgorithmicMedia"] == 1
    assert summary["digitalCapture"] == 1
    assert summary["missing"] == 1


# ---------------------------------------------------------------------------
# agent_ux_check
# ---------------------------------------------------------------------------


def test_analyze_html_counts_semantic_tags_and_widgets():
    html = """
    <html><body>
      <nav><a href="/x">x</a></nav>
      <main>
        <button>Click</button>
        <button>Other</button>
        <div onclick="doThing()">Fake button</div>
      </main>
    </body></html>
    """
    findings = agent_ux_check.analyze_html(html)
    assert findings["real_buttons"] == 2
    assert findings["real_anchors"] == 1
    assert findings["div_onclick_widgets"] == 1
    assert findings["semantic_landmarks"] >= 2  # nav + main


def test_analyze_html_detects_unlabeled_inputs():
    html = """
    <form>
      <label for="email">Email</label>
      <input id="email" type="email">
      <input id="phone" type="tel">
    </form>
    """
    findings = agent_ux_check.analyze_html(html)
    # phone has no <label for="phone"> — should count as unlabeled.
    assert findings["inputs_without_label"] == 1
    # Both inputs lack ARIA labels (one has visible label, but no aria-*).
    assert findings["inputs_without_aria"] >= 1


def test_analyze_accessibility_tree_handles_none_input():
    findings = agent_ux_check.analyze_accessibility_tree(None)
    assert findings["tree_present"] is False
    assert findings["total_nodes"] == 0


def test_agent_ux_rejects_empty_rendered_document(monkeypatch):
    monkeypatch.setattr(
        agent_ux_check,
        "render_page",
        lambda *_args, **_kwargs: {
            "url": "https://empty.example/",
            "status_code": 200,
            "error": None,
            "content": "<html><head></head><body></body></html>",
            "accessibility_tree": None,
            "accessibility_error": "no nodes",
            "accessibility_partial": True,
        },
    )
    report = agent_ux_check.audit("https://empty.example/")
    assert report["score"] is None
    assert report["score_status"] == "unavailable"
    assert "no meaningful body content" in report["render_error"]


def test_agent_ux_labels_missing_accessibility_tree_as_partial(monkeypatch):
    monkeypatch.setattr(
        agent_ux_check,
        "render_page",
        lambda *_args, **_kwargs: {
            "url": "https://partial.example/",
            "status_code": 200,
            "error": None,
            "content": "<html><body><main>Useful content</main></body></html>",
            "accessibility_tree": None,
            "accessibility_error": "CDP unavailable",
            "accessibility_partial": True,
        },
    )
    report = agent_ux_check.audit("https://partial.example/")
    assert report["score"] is not None
    assert report["score_status"] == "partial"
    assert report["partial"] is True
    assert report["partial_reasons"] == ["CDP unavailable"]


def test_analyze_accessibility_tree_counts_roles_and_names():
    tree = {
        "role": "WebArea",
        "name": "Example",
        "children": [
            {"role": "button", "name": "Submit"},
            {"role": "button", "name": ""},   # unnamed interactive
            {"role": "link", "name": "Home"},
            {"role": "generic", "name": "", "children": [
                {"role": "generic", "name": ""},
            ]},
        ],
    }
    findings = agent_ux_check.analyze_accessibility_tree(tree)
    assert findings["tree_present"] is True
    assert findings["role_button"] == 2
    assert findings["role_link"] == 1
    assert findings["role_generic"] == 2
    assert findings["unnamed_interactive"] == 1
    # WebArea + 2 buttons + 1 link + 2 generics
    assert findings["total_nodes"] == 6


def test_score_clean_page_scores_high():
    html_findings = {
        "real_buttons": 5,
        "real_anchors": 10,
        "div_onclick_widgets": 0,
        "semantic_landmarks": 3,
        "inputs_without_aria": 0,
        "inputs_without_label": 0,
    }
    a11y_findings = {
        "tree_present": True,
        "total_nodes": 50,
        "interactive_nodes": 15,
        "role_button": 5,
        "role_link": 10,
        "role_generic": 10,
        "unnamed_interactive": 0,
    }
    scored = agent_ux_check.score(html_findings, a11y_findings)
    assert scored["score"] == 100
    assert scored["issues"] == []


def test_score_deducts_for_div_onclick_and_unnamed_interactives():
    html_findings = {
        "real_buttons": 0,
        "real_anchors": 0,
        "div_onclick_widgets": 3,         # -> -15
        "semantic_landmarks": 1,
        "inputs_without_aria": 0,
        "inputs_without_label": 0,
    }
    a11y_findings = {
        "tree_present": True,
        "total_nodes": 20,
        "interactive_nodes": 5,
        "role_button": 0,
        "role_link": 0,
        "role_generic": 2,
        "unnamed_interactive": 2,          # -> -6
    }
    scored = agent_ux_check.score(html_findings, a11y_findings)
    assert scored["score"] < 100
    assert any("div onclick" in issue for issue in scored["issues"])
    assert any("accessible name" in issue for issue in scored["issues"])


# ---------------------------------------------------------------------------
# render_page extension
# ---------------------------------------------------------------------------


def test_render_page_result_dict_includes_accessibility_tree_key():
    # The new key must always be present, defaulting to None when not requested,
    # so downstream consumers can treat the field as optional without KeyError.
    result = render_page.render_page(
        "http://this-host-should-not-resolve.invalid.example/",
        mode="never",
    )
    assert "accessibility_tree" in result
    assert result["accessibility_tree"] is None


def test_render_page_accepts_extract_accessibility_kwarg():
    # Pure signature check: passing extract_accessibility must not raise.
    # The actual URL fails (intentional invalid host), but the kwarg must be
    # accepted by the function signature even on the error path.
    result = render_page.render_page(
        "http://this-host-should-not-resolve.invalid.example/",
        mode="never",
        extract_accessibility=True,
    )
    assert "accessibility_tree" in result


def test_render_page_cli_exposes_a11y_tree_flag():
    # Smoke check: the argparse parser knows --a11y-tree. Invoking the parser
    # via render_page._cli with --help would sys.exit, so just inspect the
    # source module instead.
    import inspect
    src = inspect.getsource(render_page._cli)
    assert "--a11y-tree" in src
    assert "extract_accessibility" in src
