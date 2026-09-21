"""Unlighthouse extension regressions (issue #189).

Three confirmed bugs in scripts/unlighthouse_run.py and
extensions/unlighthouse/install.sh:

(a) ``--max-routes`` was forwarded as ``--scanner '{"maxRoutes": N}'``, a
    made-up CLI flag unlighthouse-ci's cac-based parser never reads
    (confirmed against packages/cli/src/{createCli,ci,util}.ts upstream).
    The only documented way to reach ``scanner.maxRoutes`` is
    ``--config-file <path>`` pointing at a config module. No per-page
    timeout guard existed at all.
(b) ``ci-result.json`` was parsed assuming a dict; the default
    ``jsonSimple`` reporter (used whenever ``--reporter`` isn't passed)
    writes a flat JSON array of per-route results instead.
(c) install.sh required ``~/.claude/skills/seo`` to exist, which is never
    true for a marketplace/plugin install, so the installer always
    aborted in that path.

These tests exercise the pure argument-builder and JSON-normalization
functions directly with fixture data: no network, no unlighthouse install,
no subprocess execution.
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import unlighthouse_run as ul  # noqa: E402

# --------------------------------------------------------------------------
# (a) config / argument builder
# --------------------------------------------------------------------------


def test_build_config_sets_scanner_max_routes_as_number():
    config = ul.build_config(50, 60_000)
    assert config["scanner"]["maxRoutes"] == 50
    assert config["puppeteerClusterOptions"]["timeout"] == 60_000


def test_build_config_none_max_routes_maps_to_false_unlimited():
    config = ul.build_config(None, 30_000)
    assert config["scanner"]["maxRoutes"] is False


def test_write_config_file_emits_valid_esm_default_export(tmp_path):
    config = ul.build_config(25, 45_000)
    path = ul.write_config_file(tmp_path, config)
    assert path.name == "unlighthouse.config.mjs"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("export default ")
    payload = json.loads(text.removeprefix("export default ").strip())
    assert payload == config


def test_build_cmd_never_uses_the_ignored_scanner_json_flag(tmp_path):
    config_path = tmp_path / "unlighthouse.config.mjs"
    cmd = ul.build_cmd(
        "https://example.com", device="mobile", out_dir=tmp_path, config_path=config_path,
    )
    assert "--scanner" not in cmd
    assert "--max-routes" not in cmd


def test_build_cmd_passes_config_file_and_documented_flags(tmp_path):
    config_path = tmp_path / "unlighthouse.config.mjs"
    cmd = ul.build_cmd(
        "https://example.com", device="desktop", out_dir=tmp_path, config_path=config_path,
    )
    assert cmd[0:2] == ["npx", "--yes"]
    assert "--site" in cmd and "https://example.com" in cmd
    assert "--desktop" in cmd and "--device" not in cmd
    assert "--config-file" in cmd
    assert str(config_path) in cmd
    assert "--output-path" in cmd and str(tmp_path) in cmd
    # The real CLI flag (packages/cli/src/ci.ts) is `--build-static`, not
    # the nonexistent `--build-static-files` the old code passed.
    assert "--build-static" in cmd
    assert "--build-static-files" not in cmd


# --------------------------------------------------------------------------
# (b) ci-result.json shape handling
# --------------------------------------------------------------------------

JSON_SIMPLE_FIXTURE = [
    {"path": "/", "score": 0.92, "performance": 0.9, "accessibility": 0.95,
     "best-practices": 1.0, "seo": 0.88},
    {"path": "/about", "score": 0.80, "performance": 0.7, "accessibility": 0.9,
     "best-practices": 0.92, "seo": 0.85},
]

JSON_EXPANDED_FIXTURE = {
    "summary": {"score": 0.86},
    "routes": [
        {
            "path": "/",
            "score": 0.92,
            "categories": {
                "performance": {"key": "performance", "score": 0.9},
                "accessibility": {"key": "accessibility", "score": 0.95},
                "best-practices": {"key": "best-practices", "score": 1.0},
                "seo": {"key": "seo", "score": 0.88},
            },
            "metrics": {},
        },
        {
            "path": "/about",
            "score": 0.80,
            "categories": {
                "performance": {"key": "performance", "score": 0.7},
                "accessibility": {"key": "accessibility", "score": 0.9},
                "best-practices": {"key": "best-practices", "score": 0.92},
                "seo": {"key": "seo", "score": 0.85},
            },
            "metrics": {},
        },
    ],
    "metadata": {},
}


def test_normalize_handles_default_jsonsimple_array_shape():
    normalized = ul.normalize_ci_result(JSON_SIMPLE_FIXTURE)
    assert normalized["route_count"] == 2
    assert normalized["routes"] == JSON_SIMPLE_FIXTURE
    assert normalized["aggregate_scores"]["performance"] == 0.8
    assert normalized["aggregate_scores"]["accessibility"] == pytest.approx(0.925)
    assert normalized["aggregate_scores"]["seo"] == pytest.approx(0.865)


def test_normalize_falls_back_to_object_shape_with_routes_key():
    normalized = ul.normalize_ci_result(JSON_EXPANDED_FIXTURE)
    assert normalized["route_count"] == 2
    assert normalized["aggregate_scores"]["performance"] == 0.8
    assert normalized["aggregate_scores"]["accessibility"] == pytest.approx(0.925)


def test_normalize_tolerates_garbage_input():
    assert ul.normalize_ci_result(None) == {
        "routes": [], "route_count": 0, "aggregate_scores": {},
    }
    assert ul.normalize_ci_result({"unexpected": "shape"}) == {
        "routes": [], "route_count": 0, "aggregate_scores": {},
    }
    assert ul.normalize_ci_result([1, 2, "not-a-dict"]) == {
        "routes": [], "route_count": 0, "aggregate_scores": {},
    }


def test_run_rejects_allowlisted_local_target_before_spawning_unlighthouse(
    monkeypatch, tmp_path,
):
    """The external Chromium crawler has no pinned-DNS or safe-route boundary,
    so the top-level local-target exemption must not cross into it."""
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "*.test")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))
        ],
    )
    spawned = False

    def record_spawn(*args, **kwargs):
        nonlocal spawned
        spawned = True
        raise AssertionError("Unlighthouse must not start for a local target")

    monkeypatch.setattr(ul.subprocess, "run", record_spawn)
    result = ul.run("https://attacker.test/", output_dir=str(tmp_path))

    assert result["ok"] is False
    assert "url_safety" in result["error"]
    assert spawned is False


# --------------------------------------------------------------------------
# (c) installer no longer hard-requires the manual skill directory
# --------------------------------------------------------------------------


def test_installer_detects_plugin_install_paths():
    text = (ROOT / "extensions" / "unlighthouse" / "install.sh").read_text(encoding="utf-8")
    assert "CLAUDE_PLUGIN_ROOT" in text
    assert "plugins/cache" in text
    # The old unconditional abort before any plugin-path check is gone.
    assert '[ ! -d "${SKILL_DIR}/seo" ] && { echo "✗ claude-seo base not installed."; exit 1; }' not in text
