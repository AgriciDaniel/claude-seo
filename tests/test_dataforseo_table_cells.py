"""Product titles and review text must not create extra Markdown table cells."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dataforseo_normalize import format_markdown_table  # noqa: E402


def test_pipes_and_multiline_text_stay_in_their_cells():
    table = format_markdown_table(
        [{"title": "Widget | Blue", "review": "First line\r\nSecond line\nThird"}],
        ["title", "review"], headers=["Product | Variant", "Review"],
    )
    assert table.splitlines() == [
        r"| Product \| Variant | Review |",
        "| --- | --- |",
        r"| Widget \| Blue | First line Second line Third |",
    ]


def test_literal_backslashes_do_not_escape_delimiters():
    table = format_markdown_table([{"path": "folder\\", "value": "a\\|b"}], ["path", "value"])
    assert table.splitlines()[2] == r"| folder\\ | a\\\|b |"


def test_numeric_null_and_truncation_behavior_is_preserved():
    table = format_markdown_table([{"a": 2.5, "b": None}, {"a": 3, "b": "x"}],
                                  ["a", "b"], max_rows=1)
    assert "| 2.50 | -- |" in table
    assert "1 more rows" in table
