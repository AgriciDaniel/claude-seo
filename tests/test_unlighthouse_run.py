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

import http.server
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import browser_proxy  # noqa: E402
import unlighthouse_run as ul  # noqa: E402

# --------------------------------------------------------------------------
# (a) config / argument builder
# --------------------------------------------------------------------------


def test_build_config_sets_scanner_max_routes_as_number():
    config = ul.build_config(50, 60_000, "http://127.0.0.1:12345")
    assert config["scanner"]["maxRoutes"] == 50
    assert config["puppeteerClusterOptions"]["timeout"] == 60_000


def test_build_config_none_max_routes_maps_to_false_unlimited():
    config = ul.build_config(None, 30_000, "http://127.0.0.1:12345")
    assert config["scanner"]["maxRoutes"] is False


def test_write_config_file_emits_valid_esm_default_export(tmp_path):
    config = ul.build_config(25, 45_000, "http://127.0.0.1:12345")
    path = ul.write_config_file(tmp_path, config)
    assert path.name == "unlighthouse.config.mjs"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("export default ")
    payload = json.loads(text.removeprefix("export default ").strip())
    assert payload == config


def test_build_config_routes_puppeteer_through_guarded_proxy():
    config = ul.build_config(25, 45_000, "http://127.0.0.1:12345")
    assert "--proxy-server=http://127.0.0.1:12345" in config["puppeteerOptions"]["args"]
    assert "--proxy-bypass-list=<-loopback>" in config["puppeteerOptions"]["args"]
    assert "--disable-quic" in config["puppeteerOptions"]["args"]


def test_build_config_keeps_robots_and_sitemap_discovery():
    """The egress guard does not need discovery switched off: the Node
    preload routes those fetches through it. Leaving the keys out keeps the
    upstream defaults, as before the guard (robots.txt and sitemaps read,
    HTML link discovery without JavaScript)."""
    scanner = ul.build_config(25, 45_000, "http://127.0.0.1:12345")["scanner"]
    assert scanner == {"maxRoutes": 25}


def test_preload_guards_node_http_and_https_requests():
    """Discovery is only safe while the preload covers both Node clients and
    fails closed without the guard address."""
    text = (ROOT / "scripts" / "unlighthouse_http_proxy.cjs").read_text(encoding="utf-8")
    for needle in (
        "http.request = guardedHttp",
        "https.request = guardedHttps",
        "http.get =",
        "https.get =",
        "new URL(process.env.CLAUDE_SEO_GUARD_PROXY)",
        "CONNECT ${authority}",
    ):
        assert needle in text


def test_run_keeps_guard_active_during_unlighthouse_process(monkeypatch, tmp_path):
    monkeypatch.setattr(ul, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(ul, "_check_node", lambda: None)

    def fake_run(cmd, **kwargs):
        config_path = Path(cmd[cmd.index("--config-file") + 1])
        config = json.loads(config_path.read_text(encoding="utf-8").removeprefix("export default "))
        proxy_flag = next(arg for arg in config["puppeteerOptions"]["args"]
                          if arg.startswith("--proxy-server="))
        proxy = urlsplit(proxy_flag.removeprefix("--proxy-server="))
        assert kwargs["env"]["CLAUDE_SEO_GUARD_PROXY"] == proxy.geturl()
        assert "unlighthouse_http_proxy.cjs" in kwargs["env"]["NODE_OPTIONS"]
        with socket.create_connection((proxy.hostname, proxy.port), timeout=3) as client:
            client.sendall(b"GET http://127.0.0.1:9999/ HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            assert b" 403 " in client.recv(1024)
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(ul.subprocess, "run", fake_run)
    result = ul.run("https://example.com", output_dir=str(tmp_path))
    assert result["ok"] is True


def test_node_preflight_redirect_cannot_reach_internal_server(monkeypatch):
    if not ul.shutil.which("node"):
        pytest.skip("Node.js is not installed")

    hits = {"public": 0, "internal": 0}

    class Internal(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits["internal"] += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    internal = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Internal)

    class Public(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits["public"] += 1
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{internal.server_port}/secret")
            self.end_headers()

        def log_message(self, *_args):
            pass

    public = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Public)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (internal, public)]
    for thread in threads:
        thread.start()

    real_destination = browser_proxy._destination

    def mapped_destination(url):
        if url.startswith("http://public-egress.example:"):
            return "127.0.0.1", "public-egress.example", public.server_port
        return real_destination(url)

    monkeypatch.setattr(browser_proxy, "_destination", mapped_destination)
    driver = """
      process.argv[1] = 'C:/test/unlighthouse-ci.cjs';
      require(process.env.CLAUDE_SEO_PRELOAD);
      const http = require('node:http');
      function get(url) {
        http.get(url, response => {
          response.resume();
          if (response.statusCode === 302) get(response.headers.location);
          else { console.log(response.statusCode); process.exit(0); }
        }).on('error', error => { console.error(error); process.exit(1); });
      }
      get(process.env.CLAUDE_SEO_TEST_URL);
    """
    try:
        with browser_proxy.guarded_proxy() as proxy:
            env = os.environ.copy()
            env.update({
                "CLAUDE_SEO_GUARD_PROXY": proxy,
                "CLAUDE_SEO_PRELOAD": str(ROOT / "scripts" / "unlighthouse_http_proxy.cjs"),
                "CLAUDE_SEO_TEST_URL": f"http://public-egress.example:{public.server_port}/",
            })
            proc = subprocess.run([ul.shutil.which("node"), "-e", driver], env=env,
                                  capture_output=True, text=True, timeout=15, check=False)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "403"
        assert hits == {"public": 1, "internal": 0}
    finally:
        for server in (public, internal):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)


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
    assert Path(cmd[0]).stem.lower() == "npx" and cmd[1] == "--yes"
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


# --------------------------------------------------------------------------
# (c) installer no longer hard-requires the manual skill directory
# --------------------------------------------------------------------------


def test_installer_detects_plugin_install_paths():
    text = (ROOT / "extensions" / "unlighthouse" / "install.sh").read_text(encoding="utf-8")
    assert "CLAUDE_PLUGIN_ROOT" in text
    assert "plugins/cache" in text
    # The old unconditional abort before any plugin-path check is gone.
    assert '[ ! -d "${SKILL_DIR}/seo" ] && { echo "✗ claude-seo base not installed."; exit 1; }' not in text
