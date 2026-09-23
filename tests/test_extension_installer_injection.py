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
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# rel path -> (extra argv after the settings path, env var carrying the secret).
# Secrets travel in the environment: argv is readable by other local users
# through ps, the environment of a process is not.
INSTALLERS = {
    "extensions/dataforseo/install.sh": (["field.json"], "CLAUDE_SEO_SECRET"),
    "extensions/firecrawl/install.sh": ([], "CLAUDE_SEO_SECRET"),
    "extensions/banana/install.sh": ([], "CLAUDE_SEO_SECRET"),
    "extensions/ahrefs/install.sh": ([], "CLAUDE_SEO_SECRET"),
    "extensions/profound/install.sh": ([], "CLAUDE_SEO_SECRET"),
    "extensions/seranking/install.sh": ([], "CLAUDE_SEO_SECRET"),
    "extensions/bing-webmaster/install.sh": (["https://e.test/key.txt"], "CLAUDE_SEO_SECRET"),
}
BASE_ENV = {"CLAUDE_SEO_USERNAME": "user", "CLAUDE_SEO_INDEXNOW_KEY": "idx"}

_HEREDOC_RE = re.compile(r"python3 - [^\n]*<<'PY'\n(.*?)\nPY\n", re.DOTALL)


def _extract_writer(text: str) -> str:
    matches = [m.group(1) for m in _HEREDOC_RE.finditer(text)]
    writers = [m for m in matches if "os.replace" in m]
    assert writers, "no quoted <<'PY' settings writer found in installer"
    return writers[0]


def _run(tmp_path: Path, rel: str, secret: str, settings: Path):
    extra, env_name = INSTALLERS[rel]
    script = tmp_path / "writer.py"
    script.write_text(_extract_writer((ROOT / rel).read_text(encoding="utf-8")), encoding="utf-8")
    env = {**os.environ, **BASE_ENV, env_name: secret}
    return subprocess.run([sys.executable, str(script), str(settings), *extra],
                          cwd=tmp_path, env=env, capture_output=True, text=True)


@pytest.mark.parametrize("rel", INSTALLERS)
def test_installer_uses_safe_credential_pattern(rel: str) -> None:
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "\'\'\'${" not in text, f"{rel} still interpolates a credential into Python source"
    assert "<<'PY'" in text, f"{rel} missing quoted heredoc"
    assert "os.environ" in text, f"{rel} not reading the secret from the environment"
    assert "0o600" in text, f"{rel} not writing settings with 0600 perms"


@pytest.mark.skipif(
    os.name != "posix", reason="asserts 0o600 mode bits, which Windows does not represent"
)
@pytest.mark.parametrize("rel", INSTALLERS)
def test_installer_credential_injection_is_inert(tmp_path: Path, rel: str) -> None:
    settings = tmp_path / "settings.json"
    marker = tmp_path / "PWNED"
    payload = f"x\'\'\'; open({str(marker)!r}, 'w').write('pwned'); y=\'\'\'"
    result = _run(tmp_path, rel, payload, settings)
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), f"{rel}: credential injection executed code"
    blob = json.dumps(json.loads(settings.read_text(encoding="utf-8")))
    assert payload in blob, f"{rel}: credential not stored literally"
    assert (settings.stat().st_mode & 0o777) == 0o600, f"{rel}: settings not 0600"


@pytest.mark.parametrize("rel", INSTALLERS)
def test_installer_never_overwrites_an_unparseable_config(tmp_path: Path, rel: str) -> None:
    """A malformed ~/.claude.json or settings.json must survive untouched."""
    settings = tmp_path / "settings.json"
    original = '{"mcpServers": {"mine": {}}, oops'
    settings.write_text(original, encoding="utf-8")
    result = _run(tmp_path, rel, "secret-value", settings)
    assert result.returncode != 0
    assert settings.read_text(encoding="utf-8") == original
    assert "Nothing was changed" in result.stderr


@pytest.mark.parametrize("rel", sorted(Path(ROOT, "extensions").glob("*/install.sh")))
def test_no_installer_passes_a_secret_on_the_command_line(rel: Path) -> None:
    text = rel.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "python3 -" in line and "<<'PY'" in line:
            args = line.split("python3 -", 1)[1]
            for word in ("KEY", "TOKEN", "PASSWORD", "SECRET"):
                assert word not in args.split("<<")[0].replace("CONFIG", ""), (rel, line)
