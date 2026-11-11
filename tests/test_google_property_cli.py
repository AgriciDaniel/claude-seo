"""CLI-level property selection for ga4_report, gsc_query and gsc_inspect.

Issue #337: a Google report must never silently use another site's property.
Every test runs ``main()`` with a mocked config and no API client, so the JSON
result carries the chosen property without making a live API request.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

pytest.importorskip("googleapiclient")
pytest.importorskip("google.analytics.data_v1beta")

import ga4_report  # noqa: E402
import gsc_inspect  # noqa: E402
import gsc_query  # noqa: E402

LEGACY = {
    "default_property": "sc-domain:primary.example",
    "ga4_property_id": "properties/100",
}
MAPPED = {
    **LEGACY,
    "sites": {
        "example.com": {
            "gsc_property": "sc-domain:example.com",
            "ga4_property_id": "properties/200",
        }
    },
}
PAGE = "https://example.com/page"

# script -> (module, leading args, explicit property flag, explicit value,
#            property the example.com sites entry resolves to)
SCRIPTS = {
    "ga4": (ga4_report, [], "--property", "999", "200"),
    "gsc": (gsc_query, [], "--property", "sc-domain:other.example", "sc-domain:example.com"),
    "sitemaps": (
        gsc_query, ["sitemaps"], "--property", "sc-domain:other.example", "sc-domain:example.com",
    ),
    "inspect": (
        gsc_inspect, [PAGE], "--site-url", "sc-domain:other.example", "sc-domain:example.com",
    ),
}
ALL = pytest.mark.parametrize("script", sorted(SCRIPTS))


@pytest.fixture
def run(monkeypatch, capsys):
    """Run a script's main() offline; return (exit code, parsed stdout, stderr)."""
    built = []

    def no_client():
        built.append(True)
        return None

    monkeypatch.setattr(ga4_report, "_build_ga4_client", no_client)
    def gsc_result(prop, *args, **kwargs):
        built.append(True)
        return {"property": prop, "error": None}

    def inspect_result(url, prop, *args, **kwargs):
        return {"url": url, **gsc_result(prop)}

    def sites_result():
        built.append(True)
        return {"sites": [], "error": None}

    # Property routing is independent of API failures, which exit nonzero even
    # in JSON mode. Record the selected property with successful API stubs.
    monkeypatch.setattr(gsc_query, "query_search_analytics", gsc_result)
    monkeypatch.setattr(gsc_query, "list_sitemaps", gsc_result)
    monkeypatch.setattr(gsc_query, "list_sites", sites_result)
    monkeypatch.setattr(gsc_inspect, "inspect_url", inspect_result)

    def _run(script, extra: list[str], config: dict):
        """``script`` is a SCRIPTS key or a (module, leading args) pair."""
        module, leading = (SCRIPTS[script] if isinstance(script, str) else script)[:2]
        monkeypatch.setattr(module, "load_config", lambda: dict(config))
        monkeypatch.setattr(sys, "argv", [f"{module.__name__}.py", *leading, *extra, "--json"])
        del built[:]
        code = 0
        try:
            module.main()
        except SystemExit as exit_info:
            code = exit_info.code
        captured = capsys.readouterr()
        output = json.loads(captured.out) if captured.out.strip() else None
        if code:
            assert output is None and not built, "a refused run must not reach the API"
        return code, output, captured.err

    return _run


@ALL
def test_explicit_property_wins_over_sites_and_default(run, script):
    flag, explicit = SCRIPTS[script][2:4]
    code, output, err = run(script, [flag, explicit], MAPPED)
    assert code == 0
    assert output["property"] == explicit
    assert "Note:" not in err


@ALL
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_domain_is_an_error_not_the_default(run, script, value):
    code, output, err = run(script, ["--domain", value], LEGACY)
    assert code == 1
    assert "--domain was given an empty value" in err


@ALL
def test_empty_explicit_property_is_an_error_not_the_default(run, script):
    flag = SCRIPTS[script][2]
    code, output, err = run(script, [flag, ""], LEGACY)
    assert code == 1
    assert f"{flag} was given an empty value" in err


@ALL
@pytest.mark.parametrize(
    "domain",
    [
        "example.com",
        "https://www.example.com/pricing",  # www is the same site as the key
        "shop.example.com",  # sc-domain:example.com covers its subdomains
    ],
)
def test_domain_resolves_to_the_sites_entry(run, script, domain):
    code, output, err = run(script, ["--domain", domain], MAPPED)
    assert code == 0
    assert output["property"] == SCRIPTS[script][4]


@ALL
def test_www_key_matches_the_bare_host(run, script):
    config = {**LEGACY, "sites": {"www.example.com": MAPPED["sites"]["example.com"]}}
    code, output, err = run(script, ["--domain", "example.com"], config)
    assert code == 0
    assert output["property"] == SCRIPTS[script][4]


@ALL
@pytest.mark.parametrize("domain", ["notexample.com", "example.com.evil.test", "example.co"])
def test_lookalike_host_is_refused(run, script, domain):
    code, output, err = run(script, ["--domain", domain], MAPPED)
    assert code == 1
    assert "refusing to use a different site's default" in err


@pytest.mark.parametrize("script", ["ga4", "gsc", "sitemaps"])
def test_no_flag_with_sites_mapping_requires_a_choice(run, script):
    code, output, err = run(script, [], MAPPED)
    assert code == 1
    assert "--domain" in err and "--property" in err
    assert "sites mapping" in err


@pytest.mark.parametrize(
    ("script", "default"),
    [("ga4", "100"), ("gsc", "sc-domain:primary.example"), ("sitemaps", "sc-domain:primary.example")],
)
def test_no_flag_without_sites_names_the_default_property(run, script, default):
    code, output, err = run(script, [], LEGACY)
    assert code == 0
    assert output["property"] == default
    assert f"property {default} from config" in err


@pytest.mark.parametrize("script", ["ga4", "gsc"])
def test_no_flag_and_no_default_still_errors(run, script):
    code, output, err = run(script, [], {})
    assert code == 1
    assert "No " in err and "property specified" in err


def test_gsc_sites_listing_needs_no_property(run):
    code, output, err = run((gsc_query, ["sites"]), [], MAPPED)
    assert code == 0
    assert output["sites"] == []


def test_inspect_without_flags_binds_to_the_inspected_url(run):
    code, output, err = run("inspect", [], MAPPED)
    assert code == 0
    assert output["property"] == "sc-domain:example.com"

    code, output, err = run((gsc_inspect, ["https://notexample.com/page"]), [], MAPPED)
    assert code == 1
    assert "refusing to use a different site's default" in err


@pytest.mark.parametrize("flags", [[], ["--domain", ""]])
def test_inspect_batch_requires_a_non_empty_site(run, tmp_path, flags):
    batch = tmp_path / "urls.txt"
    batch.write_text(PAGE + "\n")
    code, output, err = run((gsc_inspect, ["--batch", str(batch)]), flags, LEGACY)
    assert code in (1, 2)
    assert "--domain" in err
