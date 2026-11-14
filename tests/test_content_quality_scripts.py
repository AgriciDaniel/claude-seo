"""Tokenisation rules of scripts/content_quality.py across writing systems.

ASCII text must tokenise exactly as it did before non-Latin support, words in
space-delimited scripts must stay whole (accents and vowel signs included),
the word rule must never run on into Hangul, kana or CJK, and the scripts
that cannot be segmented must be reported as low confidence.
"""

from __future__ import annotations

import os
import random
import re
import string
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import content_quality  # noqa: E402
import content_verify  # noqa: E402

# The tokeniser as it was before any non-Latin alphabetic support.
_OLD_TOKEN_RE = re.compile(
    r"[A-Za-z][A-Za-z'\-]*"
    r"|[가-힣]+"
    r"|[ぁ-ゖァ-ヺー]"
    r"|[㐀-䶿一-鿿]"
)

_ENGLISH_PARAGRAPHS = [
    "In today's fast-paced world, when it comes to SEO, it's important to "
    "note that state-of-the-art tooling won't replace well-researched copy.",
    "The 2025 study (n=1,204) found a 47% lift; see https://example.com/a_b?x=1 "
    "and e-mail jane.doe@example.com for the raw CSV. Don't quote v2.6.0-rc1!",
    "'Quoted' words, trailing- hyphens, -leading ones, rock'n'roll, O'Brien's, "
    "snake_case_names, CamelCase, x86-64, 3rd-party and A/B tests.",
    "def analyse(text: str) -> dict:\n    return {'tokens': len(text.split())}\n"
    "\tTabs\tand   runs  of spaces -- plus a double hyphen and an isolated ' mark.",
    "",
]


def _tokens(text: str) -> list[str]:
    return content_quality._tokenise(text)


@pytest.mark.parametrize("text", _ENGLISH_PARAGRAPHS)
def test_ascii_text_tokenises_exactly_as_the_original_regex(text: str) -> None:
    assert _tokens(text) == _OLD_TOKEN_RE.findall(text)
    assert content_quality.analyse(text)["tokens"] == len(_OLD_TOKEN_RE.findall(text))


def test_random_ascii_text_tokenises_exactly_as_the_original_regex() -> None:
    rng = random.Random(270)
    alphabet = string.printable
    for _ in range(300):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 200)))
        assert _tokens(text) == _OLD_TOKEN_RE.findall(text), text


@pytest.mark.parametrize("text", [
    "한국천문연구원 공표 절기를 기준으로 계산하는 정통 사주팔자 풀이입니다. 2025년 SEO 가이드.",
    "無料四柱推命で日柱と五行がわかります。カタカナとひらがな、スーパー。",
    "免费四柱推命，一分钟了解日柱与五行。SEO 优化指南 2025。",
])
def test_korean_japanese_and_chinese_are_unchanged(text: str) -> None:
    assert _tokens(text) == _OLD_TOKEN_RE.findall(text)


@pytest.mark.parametrize(("text", "expected"), [
    # Greek
    ("Η χορτοφαγία έχει πολλές μορφές.", ["Η", "χορτοφαγία", "έχει", "πολλές", "μορφές"]),
    # Cyrillic (Russian, and Ukrainian with an apostrophe inside a word)
    ("Привет, мир! Ёлка и съезд.", ["Привет", "мир", "Ёлка", "и", "съезд"]),
    ("Здоров'я понад усе", ["Здоров'я", "понад", "усе"]),
    # Arabic, plain and fully vowelled (the vowel marks are combining marks)
    ("مرحبا بالعالم، كيف الحال؟", ["مرحبا", "بالعالم", "كيف", "الحال"]),
    ("اَلْعَرَبِيَّةُ لُغَةٌ", ["اَلْعَرَبِيَّةُ", "لُغَةٌ"]),
    # Persian keeps a zero-width non-joiner inside one word
    ("می‌خواهم بروم", ["می‌خواهم", "بروم"]),
    # Hebrew, plain and pointed
    ("שלום עולם, מה שלומך?", ["שלום", "עולם", "מה", "שלומך"]),
    ("שָׁלוֹם עוֹלָם", ["שָׁלוֹם", "עוֹלָם"]),
    # Devanagari: vowel signs and viramas are combining marks
    ("हिन्दी भाषा में लिखना। नमस्ते दुनिया", ["हिन्दी", "भाषा", "में", "लिखना", "नमस्ते", "दुनिया"]),
    # Other space-delimited scripts with combining marks
    ("বাংলা ভাষা", ["বাংলা", "ভাষা"]),
    ("தமிழ் மொழி", ["தமிழ்", "மொழி"]),
    # Armenian and Georgian
    ("Բարեւ աշխարհ", ["Բարեւ", "աշխարհ"]),
    ("გამარჯობა მსოფლიო", ["გამარჯობა", "მსოფლიო"]),
])
def test_space_delimited_scripts_keep_whole_words(text: str, expected: list[str]) -> None:
    assert _tokens(text) == expected


def test_devanagari_is_not_broken_into_single_consonants() -> None:
    tokens = _tokens("हिन्दी")
    assert tokens == ["हिन्दी"]
    assert len(tokens[0]) == 6  # the whole cluster, marks included


@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_accented_latin_words_are_single_tokens(form: str) -> None:
    text = unicodedata.normalize(form, "Un café für über naïve São Paulo, l'été déjà-vu.")
    expected = ["Un", "café", "für", "über", "naïve", "São", "Paulo", "l'été", "déjà-vu"]
    assert _tokens(text) == expected


def test_nfc_and_nfd_spellings_count_as_the_same_tokens() -> None:
    text = "Le café est très bon. Le café était fermé. Über naïve São Tomé."
    nfc = content_quality.analyse(unicodedata.normalize("NFC", text))
    nfd = content_quality.analyse(unicodedata.normalize("NFD", text))
    assert unicodedata.normalize("NFD", text) != unicodedata.normalize("NFC", text)
    assert (nfc["tokens"], nfc["unique_tokens"]) == (nfd["tokens"], nfd["unique_tokens"])
    assert nfc["tokens"] == 13


@pytest.mark.parametrize(("text", "expected"), [
    ("Ελλάδα中文", ["Ελλάδα", "中", "文"]),
    ("中文Ελλάδα", ["中", "文", "Ελλάδα"]),
    ("Ελλάδαかなカナ", ["Ελλάδα", "か", "な", "カ", "ナ"]),
    ("Ελλάδα한국어 Ελλάδα", ["Ελλάδα", "한국어", "Ελλάδα"]),
    ("Привет世界hello한국", ["Привет", "世", "界", "hello", "한국"]),
    ("café日本語über", ["café", "日", "本", "語", "über"]),
])
def test_words_never_run_on_into_cjk_kana_or_hangul(text: str, expected: list[str]) -> None:
    assert _tokens(text) == expected


@pytest.mark.parametrize("text", [
    "가",          # Hangul conjoining jamo that do not compose
    "ｶﾅ",          # halfwidth katakana
    "\U00020000\U0002a700",  # CJK Extension B and C
    "ㄅㄆ",          # Bopomofo
])
def test_generic_word_rule_does_not_claim_other_east_asian_letters(text: str) -> None:
    for token in _tokens("Ελλάδα" + text + "мир"):
        assert token in ("Ελλάδα", "мир") or token == unicodedata.normalize("NFC", text), token
    assert content_quality._TOKEN_RE.findall("Ελλάδα" + text)[0] == "Ελλάδα"


def test_digits_and_underscores_still_split_words_in_every_script() -> None:
    assert _tokens("λέξη1λέξη_слово२शब्द") == ["λέξη", "λέξη", "слово", "शब्द"]


def test_letter_and_mark_classes_cover_the_whole_unicode_range() -> None:
    """The classes are scanned below U+20000 only; nothing above may be missed."""
    limit = content_quality._CLASS_SCAN_LIMIT
    for codepoint in range(limit, sys.maxunicode + 1):
        char = chr(codepoint)
        category = unicodedata.category(char)
        if category[0] == "L":
            assert unicodedata.name(char, "").startswith("CJK"), hex(codepoint)
        if category in ("Mn", "Mc"):
            assert 0xE0100 <= codepoint <= 0xE01EF, hex(codepoint)
    letter = re.compile(f"[{content_quality._LETTER_CLASS}]")
    mark = re.compile(f"[{content_quality._MARK_CLASS}]")
    for codepoint in range(limit):
        char = chr(codepoint)
        category = unicodedata.category(char)
        east_asian = content_quality._is_east_asian(codepoint)
        assert bool(letter.fullmatch(char)) == (category[0] == "L" and not east_asian), hex(codepoint)
        assert bool(mark.fullmatch(char)) == (category in ("Mn", "Mc") and not east_asian), hex(codepoint)


_UNSEGMENTED = {
    "thai": "ภาษาไทยเป็นภาษาที่ไม่มีการเว้นวรรคระหว่างคำ การตัดคำจึงต้องใช้พจนานุกรม",
    "lao": "ພາສາລາວບໍ່ມີການເວັ້ນວັກລະຫວ່າງຄຳ ການຕັດຄຳຕ້ອງໃຊ້ວັດຈະນານຸກົມ",
    "khmer": "ភាសាខ្មែរមិនមានដកឃ្លារវាងពាក្យទេ ការកាត់ពាក្យត្រូវការវចនានុក្រម",
    "myanmar": "မြန်မာဘာသာစကားတွင် စကားလုံးများကြား နေရာလွတ်မရှိပါ",
}


@pytest.mark.parametrize("name", sorted(_UNSEGMENTED))
def test_unsegmented_scripts_are_a_flagged_low_confidence_fallback(name: str) -> None:
    text = _UNSEGMENTED[name]
    result = content_quality.analyse(text)
    assert result["coverage"] == {
        "script": "unsegmented",
        "entity_density": "not_computed",
        "phrase_lists": "english_only",
        "tokenisation": "low_confidence",
    }
    # The fallback counts one token per run between spaces: no segmentation.
    assert result["tokens"] == len(text.split())


def test_unsegmented_human_output_says_token_counts_are_low_confidence() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "content_quality.py"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, str(script)],
        input=_UNSEGMENTED["thai"] * 3, capture_output=True, encoding="utf-8",
        errors="replace", env=env,
    )
    assert result.returncode in (0, 1)
    assert "unsegmented-script (Thai, Lao, Khmer or Myanmar) text detected" in result.stdout
    assert "low confidence" in result.stdout


@pytest.mark.parametrize(("text", "script"), [
    ("Η χορτοφαγία έχει πολλές μορφές και κανόνες.", "non_latin_alphabetic"),
    ("Привет, мир! Как дела сегодня?", "non_latin_alphabetic"),
    ("مرحبا بالعالم، كيف الحال اليوم؟", "non_latin_alphabetic"),
    ("שלום עולם, מה שלומך היום?", "non_latin_alphabetic"),
    ("हिन्दी भाषा में लिखना सरल है।", "non_latin_alphabetic"),
    ("免费四柱推命，一分钟了解日柱与五行。", "cjk"),
])
def test_supported_scripts_do_not_carry_a_tokenisation_warning(text: str, script: str) -> None:
    coverage = content_quality.analyse(text)["coverage"]
    assert coverage == {
        "script": script,
        "entity_density": "not_computed",
        "phrase_lists": "english_only",
    }


@pytest.mark.parametrize("form", ["NFC", "NFD"])
@pytest.mark.parametrize("text", [
    "Le café était fermé à Évry, où l'été dernier fut très chaud.",
    "Über Größe und Äpfel: schöne Grüße aus Köln.",
    "Tiếng Việt có rất nhiều dấu, đặc biệt là ở những từ ngắn.",
    "ÀÉÎÕÜ",
])
def test_accented_latin_text_is_latin_not_another_script(text: str, form: str) -> None:
    text = unicodedata.normalize(form, text)
    assert "coverage" not in content_quality.analyse(text)
    assert "coverage" not in content_verify.verify(text)


def test_docstring_names_the_supported_and_unsupported_scripts() -> None:
    doc = content_quality.__doc__
    assert "Tokenisation coverage" in doc
    for name in ("Greek", "Cyrillic", "Arabic", "Hebrew", "Devanagari", "Thai", "Lao", "Khmer", "Myanmar"):
        assert name in doc, name
    assert "Low confidence: Thai, Lao, Khmer and Myanmar" in doc
    assert "correct for all" not in doc


def test_long_documents_tokenise_quickly() -> None:
    paragraph = (
        "Search engines reward pages that answer the query. Η χορτοφαγία έχει "
        "πολλές μορφές. हिन्दी भाषा में लिखना। 無料四柱推命で日柱と五行。 한국어 문장입니다. "
    )
    text = paragraph * 20000  # about 2.9 million characters
    start = time.perf_counter()
    tokens = _tokens(text)
    elapsed = time.perf_counter() - start
    assert len(tokens) == 20000 * len(_tokens(paragraph))
    assert elapsed < 10, elapsed
