"""Tests for content_humanize.py: phrase swaps + invisible-character strip."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from content_humanize import humanize, strip_invisible  # noqa: E402


def test_zero_width_space_removed_inside_word():
    cleaned, removed = strip_invisible("wat​er​mark")
    assert cleaned == "watermark"
    assert removed == {"zero-width-space": 2}


def test_exotic_spaces_normalised():
    cleaned, removed = strip_invisible("10 GW and more")
    assert cleaned == "10 GW and more"
    assert removed["space"] == 2


def test_line_separator_becomes_newline():
    cleaned, _ = strip_invisible("a b")
    assert cleaned == "a\nb"


def test_emoji_sequences_preserved():
    family = "\U0001f468‍\U0001f469‍\U0001f467"
    warning = "⚠️"
    keycap = "1️⃣"
    text = f"{family} {warning} {keycap}"
    cleaned, removed = strip_invisible(text)
    assert cleaned == text
    assert removed == {}


def test_stray_variation_selector_stripped():
    # VS-16 sandwiched between plain ASCII is a fingerprint, not an emoji.
    cleaned, removed = strip_invisible("pla️in")
    assert cleaned == "plain"
    assert removed == {"variation-selector-16": 1}


def test_unicode_tag_characters_stripped():
    # Tag characters (U+E0000 block) are used to smuggle hidden text.
    hidden = "".join(chr(0xE0000 + ord(c)) for c in "hi")
    cleaned, removed = strip_invisible(f"visible{hidden}")
    assert cleaned == "visible"
    assert removed == {"unicode-tag-character": 2}


def test_directional_override_stripped():
    cleaned, removed = strip_invisible("safe‮vil")
    assert cleaned == "safevil"
    assert removed == {"rlo-override": 1}


def test_humanize_strips_invisible_before_phrase_matching():
    # A zero-width space inside "delve" must not defeat the \b pattern.
    result = humanize("Let's del​ve into roofing.")
    assert "delve" not in result["cleaned"]
    assert result["invisible_count"] == 1
    assert any(c["label"] == "delve-into" for c in result["changes"])


def test_humanize_reports_zero_on_clean_text():
    result = humanize("Plain honest prose about roof repair.")
    assert result["cleaned"] == "Plain honest prose about roof repair."
    assert result["invisible_count"] == 0
    assert result["change_count"] == 0
