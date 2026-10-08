"""CLAUDE_SEO_PROFILE_DIR points the credential scripts at one project's files.

The path constants are set at import, so the import-level tests run in a
subprocess, as tests/test_dataforseo_costs.py does. No test touches the network.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import profile_paths  # noqa: E402


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.mark.parametrize("value", [None, ""])
def test_unset_or_empty_variable_selects_the_default_directory(
    home: Path, monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("CLAUDE_SEO_PROFILE_DIR", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", value)
    assert profile_paths.profile_dir() == home / ".config" / "claude-seo"


@pytest.mark.parametrize("value", ["~/profiles/a", "~/profiles/a/"])
def test_tilde_expands_under_the_home_directory(
    home: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", value)
    assert profile_paths.profile_dir() == (home / "profiles" / "a").resolve()


@pytest.mark.parametrize("value", ["profiles/a", ".", " "])
def test_relative_path_is_rejected(
    home: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", value)
    with pytest.raises(ValueError, match="CLAUDE_SEO_PROFILE_DIR") as exc:
        profile_paths.profile_dir()
    assert repr(value) in str(exc.value)


def test_filesystem_root_is_rejected(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path.cwd().anchor
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", root)
    with pytest.raises(ValueError, match="CLAUDE_SEO_PROFILE_DIR") as exc:
        profile_paths.profile_dir()
    assert repr(root) in str(exc.value)


@pytest.mark.parametrize("value", ["~", "~/"])
def test_home_directory_is_rejected(
    home: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", value)
    with pytest.raises(ValueError, match="CLAUDE_SEO_PROFILE_DIR"):
        profile_paths.profile_dir()


def test_symlink_to_the_home_directory_is_rejected(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    link = tmp_path / "link-to-home"
    try:
        link.symlink_to(home, target_is_directory=True)
    except OSError:
        pytest.skip("this filesystem cannot create symlinks")
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", str(link))
    with pytest.raises(ValueError, match="CLAUDE_SEO_PROFILE_DIR"):
        profile_paths.profile_dir()


def test_or_exit_turns_a_rejected_value_into_exit_code_1(
    home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", "profiles/a")
    with pytest.raises(SystemExit) as exc:
        profile_paths.profile_dir_or_exit()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "CLAUDE_SEO_PROFILE_DIR" in err
    assert "'profiles/a'" in err


def test_cli_prints_the_directory_as_json(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    env = {**os.environ, "CLAUDE_SEO_PROFILE_DIR": str(profile)}
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "profile_paths.py")],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"profile_dir": str(profile.resolve())}


_CONSTANTS = {
    "google_auth": {"CONFIG_PATH": "google-api.json", "TOKEN_PATH": "oauth-token.json"},
    "backlinks_auth": {"CONFIG_PATH": "backlinks-api.json"},
    "matomo_auth": {"CONFIG_PATH": "matomo.json"},
}

_CREDENTIAL_ENV_PREFIXES = (
    "CLAUDE_SEO_", "GOOGLE_", "GSC_", "GA4_", "MOZ_", "BING_",
    "KEYWORDSEVERYWHERE_", "MATOMO_",
)


def _isolated_env(tmp_path: Path, profile: str | None) -> dict[str, str]:
    """The current environment without credential variables, with a fresh
    home and gcloud directory, and the profile variable when given."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(_CREDENTIAL_ENV_PREFIXES)}
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["CLOUDSDK_CONFIG"] = str(tmp_path / "gcloud")
    if profile is not None:
        env["CLAUDE_SEO_PROFILE_DIR"] = profile
    return env


def _python(code: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code], cwd=SCRIPTS, capture_output=True, text=True, env=env
    )


def _constants(module: str, env: dict[str, str]) -> dict[str, str]:
    names = sorted(_CONSTANTS[module])
    code = (
        f"import json, {module}\n"
        f"print(json.dumps({{name: getattr({module}, name) for name in {names!r}}}))"
    )
    proc = _python(code, env)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("module", sorted(_CONSTANTS))
def test_set_variable_moves_every_credential_file(tmp_path: Path, module: str) -> None:
    profile = tmp_path / "profiles" / "project-xyz"
    constants = _constants(module, _isolated_env(tmp_path, str(profile)))
    assert constants == {
        name: str(profile.resolve() / filename) for name, filename in _CONSTANTS[module].items()
    }


@pytest.mark.parametrize("module", sorted(_CONSTANTS))
def test_unset_variable_keeps_todays_paths(tmp_path: Path, module: str) -> None:
    constants = _constants(module, _isolated_env(tmp_path, None))
    home = tmp_path / "home"
    assert {name: os.path.normpath(path) for name, path in constants.items()} == {
        name: os.path.normpath(os.path.join(home, ".config", "claude-seo", filename))
        for name, filename in _CONSTANTS[module].items()
    }


@pytest.mark.parametrize("module", sorted(_CONSTANTS))
def test_default_directory_set_explicitly_matches_unset(tmp_path: Path, module: str) -> None:
    explicit = _constants(module, _isolated_env(tmp_path, "~/.config/claude-seo"))
    unset = _constants(module, _isolated_env(tmp_path, None))
    assert {n: Path(p).resolve() for n, p in explicit.items()} == {
        n: Path(p).resolve() for n, p in unset.items()
    }


@pytest.mark.parametrize("module", sorted(_CONSTANTS))
def test_rejected_value_stops_the_import_without_a_traceback(tmp_path: Path, module: str) -> None:
    proc = _python(f"import {module}", _isolated_env(tmp_path, "profiles/project-xyz"))
    assert proc.returncode == 1
    assert "CLAUDE_SEO_PROFILE_DIR" in proc.stderr
    assert "'profiles/project-xyz'" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_dataforseo_budget_ignores_the_profile(tmp_path: Path) -> None:
    proc = _python(
        "import dataforseo_costs; print(dataforseo_costs.CONFIG_DIR)",
        _isolated_env(tmp_path, str(tmp_path / "profile")),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == str(tmp_path / "home" / ".config" / "claude-seo")


def test_keyword_planner_reads_the_token_from_google_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import google_auth
    import keyword_planner

    token = tmp_path / "oauth-token.json"
    token.write_text(json.dumps({"refresh_token": "profile-refresh"}))
    client = tmp_path / "client_secret.json"
    client.write_text(json.dumps({"installed": {"client_id": "id", "client_secret": "secret"}}))
    # A home without a token file, so only google_auth.TOKEN_PATH can supply one.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(google_auth, "TOKEN_PATH", str(token))
    monkeypatch.setattr(keyword_planner, "HAS_GOOGLE_ADS", True)
    monkeypatch.setattr(keyword_planner, "load_config", lambda: {
        "ads_developer_token": "dev",
        "ads_customer_id": "123-456-7890",
        "oauth_client_path": str(client),
    })
    captured: dict[str, str] = {}

    class FakeAdsClient:
        @staticmethod
        def load_from_dict(config: dict[str, str]) -> str:
            captured.update(config)
            return "client"

    monkeypatch.setattr(keyword_planner, "GoogleAdsClient", FakeAdsClient, raising=False)
    assert keyword_planner._build_ads_client() == ("client", "1234567890")
    assert captured["refresh_token"] == "profile-refresh"


def test_describe_config_dir_shows_an_existing_directory(tmp_path: Path) -> None:
    assert profile_paths.describe_config_dir(str(tmp_path / "google-api.json")) == str(tmp_path)


def test_describe_config_dir_marks_a_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert (
        profile_paths.describe_config_dir(str(missing / "google-api.json"))
        == f"{missing} (does not exist)"
    )


def test_describe_config_dir_marks_a_file(tmp_path: Path) -> None:
    not_a_dir = tmp_path / "profile"
    not_a_dir.write_text("")
    assert (
        profile_paths.describe_config_dir(str(not_a_dir / "google-api.json"))
        == f"{not_a_dir} (not a directory)"
    )


_AUTH_SCRIPTS = ["backlinks_auth.py", "google_auth.py", "matomo_auth.py"]


def _check(script: str, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--check", *args],
        capture_output=True, text=True, env=env,
    )


@pytest.mark.parametrize("script", _AUTH_SCRIPTS)
def test_check_json_names_the_profile_directory(tmp_path: Path, script: str) -> None:
    profile = tmp_path / "missing-profile"
    proc = _check(script, ["--json"], _isolated_env(tmp_path, str(profile)))
    payload = json.loads(proc.stdout)
    assert payload["config_dir"] == str(profile.resolve()), proc.stderr
    assert payload["config_dir_exists"] is False


@pytest.mark.parametrize("script", _AUTH_SCRIPTS)
def test_check_json_reports_an_existing_profile_directory(tmp_path: Path, script: str) -> None:
    profile = tmp_path / "profile"
    profile.mkdir(parents=True)
    proc = _check(script, ["--json"], _isolated_env(tmp_path, str(profile)))
    assert json.loads(proc.stdout)["config_dir_exists"] is True, proc.stderr


@pytest.mark.parametrize("script", _AUTH_SCRIPTS)
def test_check_text_marks_a_missing_profile_directory(tmp_path: Path, script: str) -> None:
    profile = tmp_path / "missing-profile"
    proc = _check(script, [], _isolated_env(tmp_path, str(profile)))
    assert f"Config directory: {profile.resolve()} (does not exist)" in proc.stdout, proc.stderr


@pytest.mark.parametrize(
    "value",
    [
        "~.config/claude-seo/profiles/x",
        "~no-such-user-xyz/profiles/x",
        "~root/p",
        "~.config\\x",
    ],
)
def test_tilde_typo_is_rejected_with_the_variable_name(
    home: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", value)
    with pytest.raises(ValueError, match="CLAUDE_SEO_PROFILE_DIR") as exc:
        profile_paths.profile_dir()
    assert repr(value) in str(exc.value)


def test_home_directory_in_different_case_is_rejected(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other_case = Path(str(home).swapcase())
    if not other_case.exists():
        pytest.skip("this filesystem is case-sensitive")
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", str(other_case))
    with pytest.raises(ValueError, match="CLAUDE_SEO_PROFILE_DIR") as exc:
        profile_paths.profile_dir()
    assert repr(str(other_case)) in str(exc.value)


def test_describe_config_dir_marks_an_inaccessible_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(self: Path) -> bool:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "exists", denied)
    assert (
        profile_paths.describe_config_dir(str(tmp_path / "google-api.json"))
        == f"{tmp_path} (not accessible)"
    )


def test_missing_home_does_not_break_a_valid_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "no-such-home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "no-such-home"))
    profile = tmp_path / "profile"
    profile.mkdir()
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", str(profile))
    assert profile_paths.profile_dir() == profile.resolve()


def test_unset_variable_does_not_need_path_home(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_home(cls: type[Path]) -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.delenv("CLAUDE_SEO_PROFILE_DIR", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(no_home))
    assert profile_paths.profile_dir() == home / ".config" / "claude-seo"


def test_keyword_planner_error_names_the_config_in_use(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    import google_auth
    import keyword_planner

    config = tmp_path / "profile" / "google-api.json"
    monkeypatch.setattr(google_auth, "CONFIG_PATH", str(config))
    monkeypatch.setattr(keyword_planner, "HAS_GOOGLE_ADS", True)
    monkeypatch.setattr(keyword_planner, "load_config", lambda: {})
    assert keyword_planner._build_ads_client() is None
    assert str(config) in capsys.readouterr().err


@pytest.mark.parametrize("script", _AUTH_SCRIPTS)
def test_check_text_marks_a_profile_that_is_a_file(tmp_path: Path, script: str) -> None:
    profile = tmp_path / "profile-file"
    profile.write_text("")
    proc = _check(script, [], _isolated_env(tmp_path, str(profile)))
    assert f"Config directory: {profile.resolve()} (not a directory)" in proc.stdout, proc.stderr


@pytest.mark.parametrize(
    ("module", "filename", "key"),
    [
        ("google_auth", "google-api.json", "api_key"),
        ("backlinks_auth", "backlinks-api.json", "moz_api_key"),
        ("matomo_auth", "matomo.json", "matomo_token"),
    ],
)
def test_set_profile_ignores_the_default_directory(
    tmp_path: Path, module: str, filename: str, key: str
) -> None:
    env = _isolated_env(tmp_path, str(tmp_path / "missing-profile"))
    default = tmp_path / "home" / ".config" / "claude-seo"
    default.mkdir(parents=True)
    (default / filename).write_text(json.dumps({key: "from-default-dir"}))
    proc = _python(f"import json, {module}; print(json.dumps({module}.load_config()))", env)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout).get(key) != "from-default-dir"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_profile_under_an_unsearchable_parent_is_accepted(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", str(locked / "profile"))
        assert profile_paths.profile_dir() == (locked / "profile").resolve()
    finally:
        locked.chmod(0o700)


def test_missing_passwd_entry_does_not_break_a_valid_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_passwd_entry(cls: type[Path]) -> Path:
        raise KeyError("uid")

    profile = tmp_path / "profile"
    monkeypatch.setattr(Path, "home", classmethod(no_passwd_entry))
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", str(profile))
    assert profile_paths.profile_dir() == profile.resolve()


def test_unresolvable_path_is_rejected_with_the_variable_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def loop(self: Path, strict: bool = False) -> Path:
        raise RuntimeError("Symlink loop from 'x'")

    value = str(tmp_path / "profile")
    monkeypatch.setattr(Path, "resolve", loop)
    monkeypatch.setenv("CLAUDE_SEO_PROFILE_DIR", value)
    with pytest.raises(ValueError, match="CLAUDE_SEO_PROFILE_DIR") as exc:
        profile_paths.profile_dir()
    assert repr(value) in str(exc.value)


def test_setup_instructions_print_the_real_config_path(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "google_auth.py"), "--setup"],
        capture_output=True, text=True, env=_isolated_env(tmp_path, str(profile)),
    )
    assert str(profile.resolve() / "google-api.json") in proc.stdout, proc.stderr


def test_config_dir_fields_agree_with_describe_when_inaccessible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(self: Path) -> bool:
        raise PermissionError("denied")

    config = str(tmp_path / "google-api.json")
    monkeypatch.setattr(Path, "exists", denied)
    assert profile_paths.config_dir_fields(config) == {
        "config_dir": str(tmp_path),
        "config_dir_exists": False,
    }
    assert profile_paths.describe_config_dir(config) == f"{tmp_path} (not accessible)"
