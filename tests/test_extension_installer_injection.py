"""Regression: extension installers must not source-inject credentials.

Before the fix, the DataForSEO / Firecrawl / Banana shell installers
interpolated user-supplied credentials directly into a ``python3 -c``
source string, so a credential containing ``'''`` broke out of the string
literal and executed arbitrary code at install time. The fix passes
credentials as ``sys.argv`` via a quoted heredoc and writes the
credential-bearing settings file atomically with ``0600`` perms.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# rel path -> number of argv slots the heredoc consumes (incl. settings path)
INSTALLERS = {
    "extensions/dataforseo/install.sh": 4,  # settings, username, password, field_config
    "extensions/firecrawl/install.sh": 2,   # settings, api_key
    "extensions/banana/install.sh": 2,      # settings, api_key
    "extensions/crw/install.sh": 3,         # settings, api_key, api_url
}

_HEREDOC_RE = re.compile(r"<<'PY'\n(.*?)\nPY\n", re.DOTALL)


def _extract_writer(text: str) -> str:
    match = _HEREDOC_RE.search(text)
    assert match, "no quoted <<'PY' heredoc found in installer"
    return match.group(1)


@pytest.mark.parametrize("rel,argc", INSTALLERS.items())
def test_installer_uses_safe_credential_pattern(rel: str, argc: int) -> None:
    text = (ROOT / rel).read_text(encoding="utf-8")
    # The unsafe signature was a shell variable interpolated into a Python
    # triple-quoted string literal (e.g. '''${DFSE_PASSWORD}''').
    assert "'''${" not in text, f"{rel} still interpolates a credential into Python source"
    assert "<<'PY'" in text, f"{rel} missing quoted heredoc"
    assert "sys.argv" in text, f"{rel} not reading credentials from argv"
    assert "0o600" in text, f"{rel} not writing settings with 0600 perms"


@pytest.mark.parametrize("rel,argc", INSTALLERS.items())
def test_installer_credential_injection_is_inert(tmp_path: Path, rel: str, argc: int) -> None:
    writer = _extract_writer((ROOT / rel).read_text(encoding="utf-8"))
    script = tmp_path / "writer.py"
    script.write_text(writer, encoding="utf-8")

    settings = tmp_path / "settings.json"
    marker = tmp_path / "PWNED"
    payload = f"x'''; open({str(marker)!r}, 'w').write('pwned'); y='''"

    # settings path + credential slots; the first credential carries the payload
    argv = [sys.executable, str(script), str(settings), payload]
    argv += ["filler"] * (argc - 2)
    subprocess.run(argv, check=True, cwd=tmp_path)

    assert not marker.exists(), f"{rel}: credential injection executed code"
    blob = json.dumps(json.loads(settings.read_text(encoding="utf-8")))
    assert payload in blob, f"{rel}: credential not stored literally"
    assert (settings.stat().st_mode & 0o777) == 0o600, f"{rel}: settings not 0600"
