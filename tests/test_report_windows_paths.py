"""Windows path rules of scripts/google_report.py, tested on every platform.

Windows cannot be run locally, so the Windows rules are reproduced with
``ntpath`` and ``nturl2path`` from the standard library, and the checks that
must hold on the real platform run against the real path functions too.

- A ``file:`` URL naming a UNC share or a device is refused from the string
  alone. Resolving such a path on Windows connects to the named host.
- A report file name built from any domain can be created on Windows.
- A failed report write is an error in the result, not a traceback.
"""

from __future__ import annotations

import builtins
import ntpath
import os
import posixpath
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import google_report  # noqa: E402

CHART = "C:\\Users\\me\\out dir\\charts\\top_queries.png"
LOGO = "C:\\plugin\\charts\\google_logo.png"
ALLOWED = [(CHART, ntpath.dirname(CHART)), (LOGO, ntpath.dirname(LOGO))]

# What a hostile page title, query or domain could put into the markup.
UNC_AND_DEVICE_URLS = [
    "file:////evil.example/share/x.png",
    "file://///evil.example/share/x.png",
    "file:///%5C%5Cevil.example%5Cshare%5Cx.png",
    "file:///%5c%5cevil.example%5cshare%5cx.png",
    "file:///%2F%2Fevil.example/share/x.png",
    "file:///\\\\evil.example\\share\\x.png",
    "file:\\\\evil.example\\share\\x.png",
    "file:////evil.example@80/share/x.png",
    "file:////evil.example/C$/Users/me/out%20dir/charts/top_queries.png",
    "file://localhost//evil.example/share/x.png",
    "file:////?/C:/Users/me/out%20dir/charts/top_queries.png",
    "file:////./C:/Users/me/out%20dir/charts/top_queries.png",
    "file:////?/UNC/evil.example/share/x.png",
    "file:///%5C%5C%3F%5CUNC%5Cevil.example%5Cshare%5Cx.png",
    "file:////./pipe/x.png",
]


def _nt_url2pathname():
    """The Windows ``url2pathname``, whatever platform the tests run on."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import nturl2path
    except ImportError:
        pytest.skip("nturl2path is no longer in this Python's standard library")
    return nturl2path.url2pathname


def _as_windows(url: str, allowed=ALLOWED):
    """The string checks under Windows rules; a raised error is a refusal,
    as it is in ``_resolve_report_resource``."""
    to_path = _nt_url2pathname()
    try:
        return google_report._report_resource_candidate(url, allowed, pathmod=ntpath, to_path=to_path)
    except (OSError, ValueError):
        return None


class _NoFileAccess:
    """Fail the test if the code under test reaches the file system."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self.calls: list[str] = []

    def __enter__(self):
        self._context = self._monkeypatch.context()
        patch = self._context.__enter__()

        def trap(name):
            def touched(*args, **kwargs):
                self.calls.append(f"{name}{args[:1]!r}")
                raise OSError(f"file system reached through {name}")
            return touched

        for module, names in (
            (os.path, ("realpath", "isfile", "exists", "isdir", "islink", "getsize")),
            (os, ("stat", "lstat", "readlink", "listdir", "scandir")),
            (builtins, ("open",)),
        ):
            for name in names:
                patch.setattr(module, name, trap(name))
        return self

    def __exit__(self, *exc_info):
        return self._context.__exit__(*exc_info)


# ── 1. UNC and device URLs ───────────────────────────────────────────────────

@pytest.mark.parametrize("url", UNC_AND_DEVICE_URLS)
def test_unc_and_device_urls_are_refused_under_windows_rules(url: str) -> None:
    assert _as_windows(url) is None


@pytest.mark.parametrize("url", UNC_AND_DEVICE_URLS)
def test_unc_and_device_urls_never_reach_the_file_system(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runs against the real path functions, so Windows CI checks Windows."""
    chart = tmp_path / "charts" / "top_queries.png"
    allowed = [(chart, chart.parent)]
    with _NoFileAccess(monkeypatch) as guard:
        resolved = google_report._resolve_report_resource(url, allowed)
    assert resolved is None
    assert guard.calls == []


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "file:///C:/Windows/win.ini",
    "file:///C:/Users/me/out%20dir/charts/other.png",
    "file:///C:/Users/me/out%20dir/charts/../../secret.png",
    "file:///C:/Users/me/out%20dir/charts/top_queries.png/",
    "file:///C:/Users/me/out%20dir/charts/top_queries.png::$DATA",
    "file:///C:/Users/me/out%20dir/charts/top_queries.txt",
    "file:///D:/Users/me/out%20dir/charts/top_queries.png",
    "file://evil.example/C:/Users/me/out%20dir/charts/top_queries.png",
    "http://evil.example/x.png",
    "https://evil.example/x.png",
    "",
])
def test_other_urls_are_refused_under_windows_rules(url: str) -> None:
    assert _as_windows(url) is None


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "file:///etc/x.png",
    "file:///C:/Windows/win.ini",
    "file:///C:/Windows/x.png",
    "http://evil.example/x.png",
    "data:image/png;base64,iVBORw0KGgo=",
    "file://evil.example/x.png",
    "relative.png",
])
def test_urls_that_match_no_report_asset_never_reach_the_file_system(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    chart = tmp_path / "charts" / "top_queries.png"
    with _NoFileAccess(monkeypatch) as guard:
        resolved = google_report._resolve_report_resource(url, [(chart, chart.parent)])
    assert resolved is None
    assert guard.calls == []


@pytest.mark.parametrize("url", [
    "file:///C:/Users/me/out%20dir/charts/top_queries.png",
    "file://localhost/C:/Users/me/out%20dir/charts/top_queries.png",
    "file:///C|/Users/me/out%20dir/charts/top_queries.png",
    "file:///c:/users/ME/out%20dir/charts/TOP_QUERIES.PNG",
    "file:///C:/Users/me/out%20dir/charts/./top_queries.png",
])
def test_a_chart_on_a_normal_drive_passes_the_string_checks(url: str) -> None:
    candidate = _as_windows(url)
    assert candidate is not None
    assert ntpath.normcase(ntpath.normpath(candidate)) == ntpath.normcase(CHART)


def test_the_bundled_logo_passes_the_string_checks() -> None:
    assert _as_windows("file:///C:/plugin/charts/google_logo.png") == LOGO


def test_charts_in_a_unc_output_directory_are_refused() -> None:
    """Fail closed: a report written to a UNC share has no charts in its PDF."""
    chart = "\\\\fileserver\\reports\\charts\\top_queries.png"
    allowed = [(chart, ntpath.dirname(chart))]
    assert _as_windows("file://fileserver/reports/charts/top_queries.png", allowed) is None
    assert _as_windows("file:////fileserver/reports/charts/top_queries.png", allowed) is None


@pytest.mark.parametrize("path", [
    "\\\\host\\share\\x.png", "//host/share/x.png", "\\/host/share/x.png",
    "\\\\\\host\\share\\x.png", "\\\\?\\C:\\x.png", "\\\\.\\C:\\x.png",
    "\\\\?\\UNC\\host\\share\\x.png", "\\\\.\\NUL", "//./pipe/x", "\\\\",
])
def test_unc_and_device_paths_are_recognised_from_the_string(path: str) -> None:
    assert google_report._is_unc_or_device_path(path, ntpath) is True


@pytest.mark.parametrize("path", [
    "C:\\out\\x.png", "C:/out/x.png", "c:x.png", "\\out\\x.png", "/out/x.png",
    "x.png", "out\\\\x.png", "C:\\out\\\\x.png", "",
])
def test_ordinary_windows_paths_are_not_unc_or_device_paths(path: str) -> None:
    assert google_report._is_unc_or_device_path(path, ntpath) is False


def test_posix_has_no_unc_paths() -> None:
    assert google_report._is_unc_or_device_path("//host/share/x.png", posixpath) is False


def test_real_chart_still_resolves_on_this_platform(tmp_path: Path) -> None:
    charts = tmp_path / "out dir" / "charts"
    charts.mkdir(parents=True)
    chart = charts / "top_queries.png"
    chart.write_bytes(b"\x89PNG\r\n\x1a\n")
    url = Path(os.path.abspath(str(chart))).as_uri()
    assert google_report._resolve_report_resource(url, [(chart, charts)]) == os.path.realpath(chart)


# ── 2. File names ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("domain", [
    "example.com", "shop.example-site.com", "sub.example.co.uk", "xn--mnchen-3ya.de",
    "example.com_8080", "EXAMPLE.com", "m\u00fcnchen.de", "console.example.com",
    "com10.example.com", "=1+1", "a b",
])
def test_ordinary_domains_keep_their_file_name(domain: str) -> None:
    assert google_report._safe_filename_part(domain) == domain


@pytest.mark.parametrize("domain, expected", [
    ("example.com:8080", "example.com_8080"),
    ("https://example.com/a", "https___example.com_a"),
    ("a\\b", "a_b"),
    ("../../evil/=x", ".._.._evil_=x"),
    ('a<b>c"d|e?f*g', "a_b_c_d_e_f_g"),
    ("a\x00b\x1fc\td\ne", "a_b_c_d_e"),
    ("caf\ud800e", "caf_e"),
    ("example.com.", "example.com"),
    ("example.com . .", "example.com"),
    ("", "_"),
    (".", "_"),
    (" ", "_"),
    ("...", "_"),
    ("CON", "_CON"),
    ("nul", "_nul"),
    ("Aux.example.com", "_Aux.example.com"),
    ("com1", "_com1"),
    ("LPT9.txt", "_LPT9.txt"),
    ("nul.", "_nul"),
    ("prn ", "_prn"),
    (None, "None"),
    (12, "12"),
])
def test_file_name_part_is_safe_on_windows(domain, expected: str) -> None:
    assert google_report._safe_filename_part(domain) == expected


@pytest.mark.parametrize("domain", [
    "x" * 5000, "a." * 300, "x" * 99 + ". " * 50, '<>:"/\\|?*' * 40, "CON" + " " * 300,
])
def test_file_name_part_is_capped_and_never_ends_in_a_dot_or_space(domain: str) -> None:
    part = google_report._safe_filename_part(domain)
    assert 1 <= len(part) <= 101
    assert part[-1] not in ". "
    assert not set(part) & set('<>:"/\\|?*')


@pytest.mark.parametrize("domain", [
    'x"; } </style><b id=dom>', "a|b?c*d", "trailing.dot.", "trailing space ", "NUL", "com1.example.com",
    "tab\there", "x" * 400,
])
def test_html_report_is_written_for_a_domain_windows_would_refuse(tmp_path: Path, domain: str) -> None:
    pytest.importorskip("matplotlib")
    result = google_report.generate_report(
        "full", {"summary": {"health_score": 80}}, domain, tmp_path, output_format="html",
    )
    assert result["error"] is None
    written = Path(result["files"][0])
    assert written.is_file() and written.parent == tmp_path
    name = written.name
    assert not set(name) & set('<>:"/\\|?*') and name.isprintable()
    assert len(name) < 200


# ── 3. Failed writes ─────────────────────────────────────────────────────────

def test_a_failed_html_write_is_reported_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("matplotlib")
    real_open = builtins.open

    def refusing_open(file, mode="r", *args, **kwargs):
        if str(file).endswith(".html") and "w" in mode:
            raise OSError(22, "Invalid argument", str(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", refusing_open)
    result = google_report.generate_report(
        "full", {"summary": {"health_score": 80}}, "example.com", tmp_path, output_format="html",
    )
    assert result["files"] == []
    assert result["error"].startswith("HTML report could not be written: ")
    assert "Invalid argument" in result["error"]


def test_a_failed_html_write_keeps_its_message_when_the_pdf_fails_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("matplotlib")
    real_open = builtins.open

    def refusing_open(file, mode="r", *args, **kwargs):
        if str(file).endswith(".html") and "w" in mode:
            raise OSError(22, "Invalid argument", str(file))
        return real_open(file, mode, *args, **kwargs)

    class BrokenHTML:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def write_pdf(self, target) -> None:
            raise OSError(28, "No space left on device", str(target))

    monkeypatch.setattr(builtins, "open", refusing_open)
    monkeypatch.setattr(google_report, "HTML", BrokenHTML)
    result = google_report.generate_report(
        "full", {"summary": {"health_score": 80}}, "example.com", tmp_path, output_format="both",
    )
    assert result["files"] == []
    html_error, pdf_error = result["error"].split("; ", 1)
    assert html_error.startswith("HTML report could not be written: ")
    assert pdf_error.startswith("PDF generation failed: ") and "No space left" in pdf_error

    monkeypatch.setattr(google_report, "HTML", None)
    result = google_report.generate_report(
        "full", {"summary": {"health_score": 80}}, "example.com", tmp_path, output_format="both",
    )
    assert result["error"].startswith("HTML report could not be written: ")
    assert "; weasyprint is required for PDF generation." in result["error"]
