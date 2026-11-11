"""Use real input elements and supported label associations in the UX audit."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import agent_ux_check  # noqa: E402


@pytest.mark.parametrize("html", [
    '<input id="q" aria-label="Search">',
    '<span id="name">Name</span><input id="q" aria-labelledby="name">',
    '<label>Name <input id="q"></label>',
    '<label for=q>Name</label><input id=q>',
    '<input id="q" title="Search">',
    '<input id="q" type="submit" value="Send">',
    '<input id="q" type="image" alt="Search">',
    '<input id="token" type="hidden">',
    '<!-- <input id="q"> -->',
])
def test_named_or_noninteractive_input_is_not_penalized(html):
    assert agent_ux_check.analyze_html(html)["inputs_without_label"] == 0


@pytest.mark.parametrize("html", [
    '<input>',
    '<input aria-label=" ">',
    '<input aria-labelledby="missing">',
    '<label for="q"> </label><input id="q">',
    '<label for="other">Name <input></label>',
])
def test_unnamed_input_is_detected_even_without_id(html):
    assert agent_ux_check.analyze_html(html)["inputs_without_label"] == 1


def test_score_deducts_for_an_unnamed_input_without_an_id():
    findings = agent_ux_check.analyze_html('<main><input></main>')
    tree = agent_ux_check.analyze_accessibility_tree(None)
    assert agent_ux_check.score(findings, tree)["score"] == 96
