"""Tests for scripts/content_humanize.py.

The module ships user-facing prose, so a wrong replacement is not a crash: it is
broken English published to a live site. These pin the grammar contract.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from content_humanize import humanize  # noqa: E402


def clean(text: str) -> str:
    return humanize(text)["cleaned"]


class TestReplacementGrammar:
    def test_unlock_potential_of_keeps_the_object_readable(self):
        # Regression: the rule consumed "potential" but left "of", yielding
        # "use of your CRM".
        out = clean("Leverage the power of AI to unlock the potential of your CRM.")
        assert out == "Use AI to get more from your CRM."
        assert " use of " not in out

    def test_unlock_potential_without_of_still_replaced(self):
        assert clean("Unlock the full potential today.") == "Do more today."

    def test_game_changer_is_replaced_by_a_noun(self):
        # Regression: replacing the noun with the adjective "important" produced
        # "this is a important".
        assert clean("This is a game-changer.") == "This is a big change."
        assert clean("These are game-changers.") == "These are big changes."


class TestSentenceCapitalisation:
    @pytest.mark.parametrize(
        "source,expected",
        [
            ("In conclusion, this is fine.", "This is fine."),
            ("Moreover, teams struggle.", "Teams struggle."),
            ("Ultimately, it works.", "It works."),
            ("In essence, we ship.", "We ship."),
        ],
    )
    def test_deleted_opener_restores_the_capital(self, source, expected):
        assert clean(source) == expected

    def test_capital_restored_mid_paragraph(self):
        out = clean("We ship daily. Moreover, we test.")
        assert out == "We ship daily. We test."

    def test_no_capitalisation_pass_when_nothing_was_deleted(self):
        # Only a substitution, no deletion: leave the text's own casing alone.
        assert clean("we delve into it.") == "we explore it."


class TestArticleAgreement:
    def test_a_becomes_an_before_a_vowel(self):
        assert clean("It is a cutting-edge tool.") == "It is a modern tool."
        assert "a important" not in clean("This is a game-changer.")

    def test_an_becomes_a_before_a_consonant(self):
        assert clean("It is an ever-evolving field.") == "It is a changing field."

    def test_untouched_articles_are_left_alone(self):
        assert clean("An apple and a pear.") == "An apple and a pear."


class TestSpacing:
    def test_first_and_foremost_keeps_the_space(self):
        # Regression: the pattern ate the trailing space and the replacement did
        # not put one back, producing "First,explore".
        assert clean("First and foremost, delve into the data.") == "First, explore the data."

    def test_last_but_not_least_keeps_the_space(self):
        assert clean("Last but not least, leverage the power of AI.") == "Finally, use AI."

    def test_thousands_separator_is_not_touched(self):
        assert clean("Revenue grew 1,000 percent.") == "Revenue grew 1,000 percent."


class TestSafety:
    def test_urls_are_not_recapitalised(self):
        out = clean("Moreover, see https://example.com/in-conclusion/page for more.")
        assert "https://example.com/in-conclusion/page" in out

    def test_fenced_code_is_not_recapitalised(self):
        src = "Moreover, run this:\n\n```\nconst delve = 1;\n```\n"
        out = clean(src)
        assert "const delve = 1;" in out

    def test_unknown_idiom_is_left_alone(self):
        src = "The quick brown fox jumps over the lazy dog."
        assert clean(src) == src

    def test_change_log_counts_every_replacement(self):
        result = humanize("Moreover, this is a game-changer.")
        assert result["change_count"] == len(result["changes"])
        assert result["change_count"] >= 2
