"""Unload signals must come from executable markup, not examples or data."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preload_check import analyse  # noqa: E402


@pytest.mark.parametrize("event", ["unload", "beforeunload"])
@pytest.mark.parametrize(
    "wrapper",
    [
        "<pre><code>{code}</code></pre>",
        "<!-- {code} -->",
        '<div data-example="{code}">Documentation</div>',
        '<script type="application/json">{code}</script>',
        '<script type="application/ld+json">{code}</script>',
        '<script src="/app.js">{code}</script>',
        "<template><script>{code}</script></template>",
        "<noscript><script>{code}</script></noscript>",
        "<textarea><script>{code}</script></textarea>",
    ],
)
def test_examples_and_inert_content_do_not_report_listeners(event, wrapper):
    code = f"window.addEventListener('{event}', cleanup);"
    result = analyse(wrapper.format(code=code))

    assert result["bfcache_signals"][f"{event}_listener"] is False
    assert result["score"] == analyse("")["score"]
    assert not any("listener" in advice for advice in result["recommendations"])


@pytest.mark.parametrize("event", ["unload", "beforeunload"])
@pytest.mark.parametrize("attrs", ["", 'type="module"', 'type="TEXT/JAVASCRIPT"', 'language="javascript"'])
def test_inline_executable_scripts_keep_their_listener_signals(event, attrs):
    result = analyse(f'<script {attrs}>window.addEventListener("{event}", cleanup);</script>')

    assert result["bfcache_signals"][f"{event}_listener"] is True
    expected = analyse("")["score"] - (25 if event == "unload" else 0)
    assert result["score"] == expected


@pytest.mark.parametrize("event", ["unload", "beforeunload"])
@pytest.mark.parametrize("tag", ["body", "frameset"])
def test_window_event_handler_attributes_are_detected(event, tag):
    result = analyse(f'<{tag} on{event}="cleanup()"></{tag}>')

    assert result["bfcache_signals"][f"{event}_listener"] is True


@pytest.mark.parametrize("argument", ['"unloading"', '"unload-custom"', "unloadCallback", '"UNLOAD"'])
def test_other_event_names_and_variable_names_are_not_unload(argument):
    result = analyse(f"<script>window.addEventListener({argument}, cleanup);</script>")

    assert result["bfcache_signals"]["unload_listener"] is False
    assert result["score"] == analyse("")["score"]


def test_single_quoted_jquery_listener_is_still_detected():
    result = analyse("<script>$(window).on('unload', cleanup);</script>")

    assert result["bfcache_signals"]["unload_listener"] is True


def test_template_handler_attributes_are_inert():
    result = analyse('<template><body onunload="cleanup()"></body></template>')

    assert result["bfcache_signals"]["unload_listener"] is False


def test_registration_inside_an_event_handler_is_still_detected():
    result = analyse('''<button onclick="window.addEventListener('unload', cleanup)">Save</button>''')

    assert result["bfcache_signals"]["unload_listener"] is True
