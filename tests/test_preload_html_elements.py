"""Resource hints are HTML elements and attributes, not raw-text matches."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preload_check import analyse  # noqa: E402


def test_unquoted_attributes_and_rel_tokens_are_recognized():
    result = analyse('''
        <script type=speculationrules>{"prerender": []}</script>
        <link rel="PRELOAD stylesheet" href=/app.css as=style>
        <link rel=prerender href=/next>
        <img src=/hero.jpg fetchpriority=high>
    ''')
    assert result["speculation_rules"]["inline_blocks"] == 1
    assert result["speculation_rules"]["actions"] == ["prerender"]
    assert result["preload_hints"] == 1
    assert result["prerender_links"] == 1
    assert result["lcp_resource_hints"] == {
        "preload_lcp_candidate": True, "fetchpriority_high": 1,
    }


@pytest.mark.parametrize("html", [
    '''<!-- <script type="speculationrules">{"prefetch": []}</script>
        <link rel="preload"><link rel="prerender"><img fetchpriority="high"> -->''',
    '''<script data-type="speculationrules">{"prefetch": []}</script>
        <link data-rel="preload"><link data-rel="prerender"><img data-fetchpriority="high">''',
    '''<script>const example = '<link rel="preload"><img fetchpriority="high">';</script>''',
])
def test_inert_text_and_data_attributes_do_not_count_as_hints(html):
    result = analyse(html)
    assert result["speculation_rules"]["inline_blocks"] == 0
    assert result["preload_hints"] == 0
    assert result["prerender_links"] == 0
    assert result["lcp_resource_hints"] == {
        "preload_lcp_candidate": False, "fetchpriority_high": 0,
    }
