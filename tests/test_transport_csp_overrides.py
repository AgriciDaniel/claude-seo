"""CSP audit findings follow the effective directive for each script use."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from transport_check import analyze_headers  # noqa: E402


def issues(policy):
    return analyze_headers({"Content-Security-Policy": policy + "; object-src 'none'; base-uri 'none'"})["csp"]["issues"]


def test_script_element_override_is_graded():
    result = issues("script-src 'none'; script-src-elem * 'unsafe-inline'")
    assert any("* in script-src-elem" in issue for issue in result)
    assert any("'unsafe-inline' in script-src-elem" in issue for issue in result)


def test_event_handler_override_is_graded():
    assert "'unsafe-inline' in script-src-attr." in issues(
        "default-src 'none'; script-src-attr 'unsafe-inline'",
    )


def test_restricted_overrides_do_not_inherit_loose_inline_sources():
    assert issues("script-src 'unsafe-inline'; script-src-elem 'none'; script-src-attr 'none'") == []


def test_eval_uses_script_src_even_when_elements_are_restricted():
    result = issues("script-src 'unsafe-eval'; script-src-elem 'none'; script-src-attr 'none'")
    assert result == ["'unsafe-eval' in script-src."]


def test_eval_keyword_in_element_directive_has_no_effect():
    assert issues("script-src 'none'; script-src-elem 'self' 'unsafe-eval'") == []
