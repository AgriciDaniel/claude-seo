"""WebMCP drafts preserve multiple selections in their schema and submitted form."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
pytest.importorskip("bs4")
pytest.importorskip("lxml")

import agentic_fix as drafter  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402


def _fields(markup):
    return drafter._form_fields(BeautifulSoup(f"<form>{markup}</form>", "lxml").form)


@pytest.mark.parametrize("markup,values", [
    ('<input type="checkbox" name="choice" value="a">'
     '<input type="checkbox" name="choice" value="b">', ["a", "b"]),
    ('<input type="CHECKBOX" name="choice">'
     '<input type="checkbox" name="choice" value="">'
     '<input type="checkbox" name="choice" value="on">', ["on", ""]),
    ('<select name="choice" multiple><option value="a">A</option>'
     '<option value="b">B</option></select>', ["a", "b"]),
    ('<select name="choice" multiple><option value="">Empty</option>'
     '<option>Default</option><option value="Default">Repeated</option></select>', ["", "Default"]),
])
def test_multi_value_controls_use_arrays_of_available_values(markup, values):
    fields = _fields(markup)

    assert len(fields) == 1
    schema = fields[0]["schema"]
    assert schema["type"] == "array"
    assert schema["items"] == {"type": "string", "enum": values}
    assert schema["uniqueItems"] is True


@pytest.mark.parametrize("markup,expected", [
    ('<input type="checkbox" name="choice" value="yes">', {"type": "boolean"}),
    ('<select name="choice"><option value="a">A</option></select>',
     {"type": "string", "enum": ["a"]}),
    ('<input type="radio" name="choice" value="a">'
     '<input type="radio" name="choice" value="b">', {"type": "string", "enum": ["a", "b"]}),
])
def test_single_value_controls_keep_their_existing_types(markup, expected):
    schema = _fields(markup)[0]["schema"]

    assert {key: schema[key] for key in expected} == expected


def test_checkboxes_with_different_names_remain_independent_booleans():
    fields = _fields('<input type="checkbox" name="a"><input type="checkbox" name="b">')

    assert [field["schema"]["type"] for field in fields] == ["boolean", "boolean"]


def test_required_group_is_emitted_once_and_retains_required_metadata():
    fields = _fields('<input type="checkbox" name="choice" value="a">'
                     '<input type="checkbox" name="choice" value="b" required>')

    assert len(fields) == 1
    assert fields[0]["required"] is True


def test_multivalue_options_cannot_close_the_generated_script():
    html = ('<form><select name="choice" multiple>'
            '<option value="&lt;/script&gt;">Example</option></select></form>')
    script = drafter.draft_webmcp("https://example.com/", html)[0]["imperative_js"]

    assert "</script" not in script.rsplit("</script>", 1)[0]
    assert r"\u003c/script>" in script


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    import browser_proxy

    with playwright.sync_playwright() as pw:
        if not Path(pw.chromium.executable_path).exists():
            pytest.skip("Playwright Chromium is not installed")
        with browser_proxy.guarded_chromium(pw.chromium) as instance:
            yield instance


@pytest.mark.parametrize("markup,values,expected", [
    ('<input type="checkbox" name="choice" value="a" checked>'
     '<input type="checkbox" name="choice" value="b">', {"choice": ["b"]}, [["choice", "b"]]),
    ('<input type="checkbox" name="choice" value="a" checked>'
     '<input type="checkbox" name="choice" value="b" checked>', {"choice": []}, []),
    ('<input type="checkbox" name="choice">'
     '<input type="checkbox" name="choice" value="">', {"choice": ["on", ""]},
     [["choice", "on"], ["choice", ""]]),
    ('<select name="choice" multiple><option value="a" selected>A</option>'
     '<option value="b">B</option><option value="c">C</option></select>',
     {"choice": ["b", "c"]}, [["choice", "b"], ["choice", "c"]]),
    ('<select name="choice" multiple><option value="a" selected>A</option>'
     '<option value="b" selected>B</option></select>', {"choice": []}, []),
    ('<input type="checkbox" name="choice" value="yes">', {"choice": True}, [["choice", "yes"]]),
    ('<input type="checkbox" name="choice" value="yes" checked>', {"choice": False}, []),
    ('<input type="hidden" name="choice" value="no">'
     '<input type="checkbox" name="choice" value="yes">', {"choice": True},
     [["choice", "no"], ["choice", "yes"]]),
    ('<input type="radio" name="choice" value="a" checked>'
     '<input type="radio" name="choice" value="b">', {"choice": "b"}, [["choice", "b"]]),
    ('<select name="choice"><option value="a">A</option>'
     '<option value="b">B</option></select>', {"choice": "b"}, [["choice", "b"]]),
])
def test_generated_tool_submits_the_selected_dom_values(browser, markup, values, expected):
    html = f'<form id="sample">{markup}</form>'
    script = drafter.draft_webmcp("https://example.com/", html)[0]["imperative_js"]
    source = script.split(">", 1)[1].rsplit("</script>", 1)[0]
    page = browser.new_page()
    try:
        # Controlled fixtures only. No form submission or other request leaves the test.
        page.route("**/*", lambda route: route.abort())
        page.set_content(html)
        result = page.evaluate("""async ({source, values}) => {
            let registered;
            Object.defineProperty(document, "modelContext", {
                value: {registerTool(tool) { registered = tool; }}, configurable: true
            });
            let entries = null;
            let submits = 0;
            document.forms[0].addEventListener("submit", event => {
                event.preventDefault();
                entries = Array.from(new FormData(event.target).entries());
                submits += 1;
            });
            new Function(source)();
            await registered.execute(values);
            return {entries, submits};
        }""", {"source": source, "values": values})
        assert result == {"entries": expected, "submits": 1}
    finally:
        page.close()
