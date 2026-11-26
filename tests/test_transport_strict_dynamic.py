"""CSP3 strict-dynamic ignores compatibility sources for script loading."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from transport_check import analyze_headers  # noqa: E402


def issues(policy):
    return analyze_headers({
        "Content-Security-Policy": policy + "; object-src 'none'; base-uri 'none'"
    })["csp"]["issues"]


@pytest.mark.parametrize("directive", ["script-src", "default-src"])
@pytest.mark.parametrize("source", ["*", "https:", "http:", "data:"])
def test_strict_dynamic_ignores_broad_compatibility_sources(directive, source):
    assert issues(
        f"{directive} 'nonce-YWJjZGVmZw==' 'strict-dynamic' 'unsafe-inline' {source}"
    ) == []


@pytest.mark.parametrize("directive", ["script-src", "default-src"])
def test_strict_dynamic_without_nonce_or_hash_keeps_weak_source_findings(directive):
    assert issues(f"{directive} 'strict-dynamic' 'unsafe-inline' https:") == [
        f"'unsafe-inline' in {directive}.",
        f"https: in {directive} allows scripts from almost anywhere.",
    ]


@pytest.mark.parametrize("algorithm", ["sha256", "sha384", "sha512"])
def test_strict_dynamic_with_hash_ignores_compatibility_sources(algorithm):
    assert issues(f"script-src '{algorithm}-YWJjZGVmZw==' 'strict-dynamic' 'unsafe-inline' https:") == []


def test_element_override_cannot_borrow_nonce_from_script_src():
    result = issues(
        "script-src 'nonce-YWJjZGVmZw=='; "
        "script-src-elem 'strict-dynamic' 'unsafe-inline' https:"
    )
    assert "'unsafe-inline' in script-src-elem." in result
    assert "https: in script-src-elem allows scripts from almost anywhere." in result


def test_element_override_uses_its_own_strict_dynamic_sources():
    assert issues(
        "script-src 'none'; script-src-elem 'strict-dynamic' "
        "'nonce-YWJjZGVmZw==' 'unsafe-inline' https:"
    ) == []


def test_strict_dynamic_does_not_hide_unsafe_eval():
    assert issues(
        "script-src 'strict-dynamic' 'nonce-YWJjZGVmZw==' "
        "'unsafe-inline' 'unsafe-eval' https:"
    ) == ["'unsafe-eval' in script-src."]


def test_explicit_permissive_overrides_remain_findings():
    result = issues(
        "script-src 'strict-dynamic' 'nonce-YWJjZGVmZw=='; "
        "script-src-elem https: 'unsafe-inline'; script-src-attr 'unsafe-inline'"
    )
    assert "'unsafe-inline' in script-src-elem." in result
    assert "https: in script-src-elem allows scripts from almost anywhere." in result
    assert "'unsafe-inline' in script-src-attr." in result


def test_broad_source_without_strict_dynamic_is_still_reported():
    assert issues("script-src 'nonce-YWJjZGVmZw==' https:") == [
        "https: in script-src allows scripts from almost anywhere."
    ]
