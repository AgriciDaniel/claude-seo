"""Template headings cannot change the main content's heading sequence."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
pytest.importorskip("bs4")
import page_checks  # noqa: E402


def check(body):
    return page_checks.run_checks(body, "https://example.com/")


@pytest.mark.parametrize("container", ['main', 'article', 'div role="main"', 'body'])
@pytest.mark.parametrize("region", ["nav", "aside", "footer"])
def test_template_heading_cannot_bridge_a_main_content_skip(container, region):
    close = container.split()[0]
    out = check(f'<{container}><h1>Title</h1><{region}><h2>Widget</h2></{region}>'
                f'<h3>Main subsection</h3></{close}>')

    assert out["facts"]["heading_level_skips"] == 1
    assert out["facts"]["template_heading_level_skips"] == 0
    finding = next(item for item in out["findings"] if item["id"] == "heading-level-skip")
    assert finding["count"] == 1


@pytest.mark.parametrize("region", ["nav", "aside", "footer"])
def test_template_heading_cannot_reset_a_valid_content_sequence(region):
    out = check(f'<main><h1>Title</h1><h2>Section</h2><{region}><h1>Widget</h1></{region}>'
                '<h3>Subsection</h3></main>')

    assert out["facts"]["heading_level_skips"] == 0
    assert not any(item["id"] == "heading-level-skip" for item in out["findings"])
    # Region separation affects the order check, not the existing H1 inventory.
    assert out["facts"]["h1_count"] == 2


def test_template_sequence_is_measured_independently_of_main_headings():
    out = check('<main><h1>Title</h1><nav><h2>Menu</h2></nav><h2>Section</h2><h3>Subsection</h3>'
                '<aside><h4>Widget</h4></aside><h4>Detail</h4></main>')

    assert out["facts"]["heading_level_skips"] == 0
    assert out["facts"]["template_heading_level_skips"] == 1


@pytest.mark.parametrize("container", ['main', 'article', 'div role="main"'])
def test_content_header_still_starts_the_main_heading_sequence(container):
    close = container.split()[0]
    out = check(f'<{container}><header><h1>Article title</h1></header><h3>Skipped section</h3></{close}>')

    assert out["facts"]["heading_level_skips"] == 1
    assert out["facts"]["template_heading_level_skips"] == 0


def test_heading_inside_a_content_header_is_not_a_template_skip():
    out = check('<main><h1>Title</h1><header><h3>Section introduction</h3></header><h4>Detail</h4></main>')

    assert out["facts"]["heading_level_skips"] == 1
    assert out["facts"]["template_heading_level_skips"] == 0


def test_header_inside_a_sidebar_stays_in_the_template_sequence():
    out = check('<main><h1>Title</h1><aside><header><h2>Widget</h2></header><h4>Detail</h4></aside>'
                '<h3>Main subsection</h3></main>')

    assert out["facts"]["heading_level_skips"] == 1
    assert out["facts"]["template_heading_level_skips"] == 1


def test_site_header_does_not_reset_a_document_without_an_explicit_main():
    out = check('<h1>Title</h1><h2>Section</h2><header><h1>Site title</h1></header><h3>Subsection</h3>')

    assert out["facts"]["heading_level_skips"] == 0
    assert out["facts"]["template_heading_level_skips"] == 0


def test_headings_outside_an_explicit_main_remain_template_headings():
    out = check('<header><h2>Site</h2><h4>Widget</h4></header><main><h1>Title</h1><h2>Section</h2></main>'
                '<footer><h3>Footer</h3></footer>')

    assert out["facts"]["heading_level_skips"] == 0
    assert out["facts"]["template_heading_level_skips"] == 1


def test_hidden_and_empty_headings_do_not_reset_either_sequence():
    out = check('<main><h1>Title</h1><h2 aria-hidden="true">Ignored</h2><h2></h2>'
                '<nav><h2>Menu</h2><h3 aria-hidden="true">Ignored</h3><h4>Menu detail</h4></nav>'
                '<h3>Main subsection</h3></main>')

    assert out["facts"]["heading_level_skips"] == 1
    assert out["facts"]["template_heading_level_skips"] == 1
