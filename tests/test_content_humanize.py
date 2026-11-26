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


def test_zwnj_preserved_in_persian_orthography():
    # ZWNJ between letters is orthographic in Persian (a "pseudo-space" that
    # blocks glyph joining), not a hidden-text fingerprint. Deleting it
    # changes the word's correct letter-joining shape.
    for word in ("می‌رود", "کتاب‌ها"):
        cleaned, removed = strip_invisible(word)
        assert cleaned == word
        assert removed == {}


def test_zwj_preserved_in_devanagari_conjunct():
    # ZWJ between letters requests an explicit half-form/conjunct in
    # Devanagari; it is orthographic, not a watermark.
    word = "कार्य‍कर्ता"
    cleaned, removed = strip_invisible(word)
    assert cleaned == word
    assert removed == {}


def test_stray_zwj_between_digits_still_stripped():
    # A ZWJ with no letter or emoji neighbour is still a fingerprint.
    cleaned, removed = strip_invisible("12‍34")
    assert cleaned == "1234"
    assert removed == {"zero-width-joiner": 1}


def test_markdown_indentation_survives():
    # Drafts are Markdown: leading spaces are structure (indented code,
    # nested list items), not stray spacing from a deleted phrase.
    text = (
        "Install it:\n"
        "\n"
        "    pip install foo\n"
        "    foo --check\n"
        "\n"
        "- First item\n"
        "    - Nested item\n"
        "        - Deeper item\n"
    )
    result = humanize(text)
    assert result["cleaned"] == text
    assert result["change_count"] == 0


def test_markdown_hard_line_break_survives():
    # Two trailing spaces are a Markdown hard line break.
    text = "Call us today  \nWe answer within the hour."
    assert humanize(text)["cleaned"] == text


def test_indentation_survives_a_phrase_swap_on_the_same_line():
    result = humanize("- Roofing\n    - Delve into the gutters first.\n")
    assert result["cleaned"] == "- Roofing\n    - Explore the gutters first.\n"


def test_spacing_inside_a_line_is_still_tidied():
    assert humanize("Roofs  and gutters , all year.")["cleaned"] == "Roofs and gutters, all year."
