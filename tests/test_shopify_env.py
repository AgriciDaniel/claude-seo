"""`.shopify-env` parsing, lookup precedence, and the audit precheck contract."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("shopify_env", ROOT / "scripts" / "shopify_env.py")
assert SPEC and SPEC.loader
shopify_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shopify_env)

FUTURE = int(time.time()) + 30 * 86400
PAST = int(time.time()) - 86400


def _signature_input(expires: int, tag: str = "web-bot-auth") -> str:
    return (f'sig1=("@authority" "signature-agent");keyid="key-1";nonce="n";'
            f'tag="{tag}";created=1700000000;expires={expires}')


def _write_env(directory: Path, body: str) -> Path:
    path = directory / shopify_env.ENV_FILENAME
    path.write_text(body, encoding="utf-8")
    return path


def test_blocks_globals_and_verbatim_header_values(tmp_path: Path) -> None:
    path = _write_env(tmp_path, f"""
        # shared settings
        Max-Pages = 0
        Concurrency = 6
        Save-HTML = yes

        Domain = Shop.Example
        Signature-Input = {_signature_input(FUTURE)}
        Signature = sig1=:AbC==:
        Signature-Agent = https://shopify.com
        Concurrency = 3

        [second.example]
        Signature-Input = {_signature_input(FUTURE)}
        Signature = sig1=:XyZ==:
    """)
    env = shopify_env.parse_env_file(path)
    assert env["problems"] == []
    assert env["crawl"] == {"max_pages": 0, "concurrency": 6, "save_html": True}
    shop = env["authorities"]["shop.example"]
    assert shop["signature"] == "sig1=:AbC==:"
    assert shop["signature_agent"] == '"https://shopify.com"'
    assert shop["keyid"] == "key-1"
    assert shop["expires"] == FUTURE
    assert shop["crawl"] == {"concurrency": 3}
    assert "second.example" in env["authorities"]


def test_incomplete_blocks_are_skipped_with_a_problem(tmp_path: Path) -> None:
    path = _write_env(tmp_path, f"""
        Signature = sig1=:orphan:
        Domain = shop.example
        Signature-Input = {_signature_input(FUTURE)}
        Domain = other.example
        Signature-Input = {_signature_input(FUTURE, tag="wrong")}
        Signature = sig1=:ok:
        Unknown-Key = 1
        no equals sign here
    """)
    env = shopify_env.parse_env_file(path)
    assert "shop.example" not in env["authorities"]
    # A block that fails validation is kept so precheck can name the reason,
    # but it is marked and never used for signing.
    assert env["authorities"]["other.example"]["invalid"]
    assert shopify_env.signing_state(env["authorities"]["other.example"])[0] == "invalid"
    joined = "\n".join(env["problems"])
    assert "before any Domain=" in joined
    assert "shop.example: missing signature" in joined
    assert "other.example: tag is 'wrong'" in joined
    assert "unknown key 'unknown-key'" in joined
    assert "no '='" in joined


def test_env_file_is_found_in_parents_and_via_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(shopify_env.ENV_PATH_VAR, raising=False)
    path = _write_env(tmp_path, "Domain = shop.example\n")
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert shopify_env.find_env_file(nested) == path

    explicit = tmp_path / "elsewhere.env"
    explicit.write_text("Domain = shop.example\n", encoding="utf-8")
    monkeypatch.setenv(shopify_env.ENV_PATH_VAR, str(explicit))
    assert shopify_env.find_env_file(nested) == explicit
    monkeypatch.setenv(shopify_env.ENV_PATH_VAR, str(tmp_path / "missing.env"))
    assert shopify_env.find_env_file(nested) is None


def test_precheck_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(shopify_env.ENV_PATH_VAR, raising=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert shopify_env.precheck("https://shop.example", empty)["reason"] == "no_env_file"
    assert shopify_env.precheck("http://shop.example", empty)["reason"] == "no_env_file"

    _write_env(tmp_path, f"""
        Domain = shop.example
        Signature-Input = {_signature_input(FUTURE)}
        Signature = sig1=:ok:
        Domain = old.example
        Signature-Input = {_signature_input(PAST)}
        Signature = sig1=:old:
    """)
    signed = shopify_env.precheck("https://shop.example/products/x", tmp_path)
    assert signed["mode"] == "signed"
    assert signed["authority"] == "shop.example"
    assert 28 <= signed["days_left"] <= 30
    assert shopify_env.precheck("https://www.shop.example", tmp_path)["reason"] == "no_signature"
    assert shopify_env.precheck("https://old.example", tmp_path)["reason"] == "signature_expired"
    plain = shopify_env.precheck("http://shop.example", tmp_path)
    assert (plain["mode"], plain["reason"]) == ("fallback", "insecure_scheme")
    for result in (signed, shopify_env.precheck("https://old.example", tmp_path)):
        assert result["mode"] in ("signed", "fallback")


def test_precheck_never_raises_on_an_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(shopify_env.ENV_PATH_VAR, raising=False)
    path = _write_env(tmp_path, "Domain = shop.example\n")
    path.write_bytes(b"\xff\xfe\x00broken")
    result = shopify_env.precheck("https://shop.example", tmp_path)
    assert result["mode"] == "fallback"
    assert result["reason"] == "env_unreadable"


def test_signature_headers_are_the_three_verbatim_values(tmp_path: Path) -> None:
    path = _write_env(tmp_path, f"""
        Domain = shop.example
        Signature-Input = {_signature_input(FUTURE)}
        Signature = sig1=:ok:
    """)
    entry = shopify_env.parse_env_file(path)["authorities"]["shop.example"]
    headers = shopify_env.signature_headers(entry)
    assert set(headers) == {"Signature-Agent", "Signature-Input", "Signature"}
    assert headers["Signature-Agent"] == '"https://shopify.com"'
    assert headers["Signature"] == "sig1=:ok:"


def test_no_cli_command_prints_signature_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(shopify_env.ENV_PATH_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    _write_env(tmp_path, f"""
        Domain = shop.example
        Signature-Input = {_signature_input(FUTURE)}
        Signature = sig1=:SECRETVALUE:
    """)
    for argv in (["list"], ["list", "--json"], ["check", "https://shop.example"],
                 ["check", "https://shop.example", "--json"], ["precheck", "https://shop.example"]):
        shopify_env.main(argv)
        captured = capsys.readouterr()
        assert "SECRETVALUE" not in captured.out + captured.err, argv
    with pytest.raises(SystemExit):
        shopify_env.main(["headers", "https://shop.example"])


def test_list_json_never_prints_signature_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(shopify_env.ENV_PATH_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    _write_env(tmp_path, f"""
        Domain = shop.example
        Signature-Input = {_signature_input(FUTURE)}
        Signature = sig1=:SECRETVALUE:
    """)
    assert shopify_env.main(["list", "--json"]) == 0
    out = capsys.readouterr().out
    assert "SECRETVALUE" not in out
    assert json.loads(out)["authorities"]["shop.example"]["keyid"] == "key-1"


def test_out_of_range_concurrency_and_delay_are_ignored(tmp_path: Path) -> None:
    path = _write_env(tmp_path, f"""
        Concurrency = 64
        Delay = -2
        Domain = shop.example
        Signature-Input = {_signature_input(FUTURE)}
        Signature = sig1=:ok:
        Concurrency = 4
        Delay = nan
    """)
    env = shopify_env.parse_env_file(path)
    assert env["crawl"] == {}
    assert env["authorities"]["shop.example"]["crawl"] == {"concurrency": 4}
    assert len([p for p in env["problems"] if "must be between" in p]) == 3


def _block(signature_input: str, signature: str = "sig1=:ok:", extra: str = "") -> str:
    return (f"Domain = shop.example\nSignature-Input = {signature_input}\n"
            f"Signature = {signature}\n{extra}")


@pytest.mark.parametrize("signature_input, signature, expected", [
    (_signature_input(FUTURE, tag="other"), "sig1=:ok:", "tag is 'other'"),
    (f'sig1=("signature-agent");keyid="k";tag="web-bot-auth";expires={FUTURE}', "sig1=:ok:",
     'do not include "@authority"'),
    (f'sig1=("@authority");tag="web-bot-auth";expires={FUTURE}', "sig1=:ok:", "no keyid"),
    ('sig1=("@authority");keyid="k";tag="web-bot-auth";created=1700000000', "sig1=:ok:", "no expires"),
    (f'sig1=("@authority");keyid="k";tag="web-bot-auth";created={FUTURE + 5};expires={FUTURE}',
     "sig1=:ok:", "expires is not after created"),
    (_signature_input(FUTURE), "sig2=:ok:", "label does not match"),
    (_signature_input(FUTURE), "not-a-signature", "not in the form label=:base64:"),
    (_signature_input(FUTURE), "sig1=:o\tk:", "not a plain header value"),
    (_signature_input(FUTURE) + ';x="\u00e9"', "sig1=:ok:", "not a plain header value"),
])
def test_block_that_fails_validation_is_not_usable_for_signing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    signature_input: str, signature: str, expected: str,
) -> None:
    monkeypatch.delenv(shopify_env.ENV_PATH_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    path = _write_env(tmp_path, _block(signature_input, signature))
    env = shopify_env.parse_env_file(path)
    entry = env["authorities"]["shop.example"]
    assert any(expected in problem for problem in env["problems"]), env["problems"]
    assert all("signature not used" in problem for problem in env["problems"])
    assert shopify_env.signing_state(entry)[0] == "invalid"
    with pytest.raises(ValueError):
        shopify_env.signature_headers(entry)

    result = shopify_env.precheck("https://shop.example", tmp_path)
    assert (result["mode"], result["reason"]) == ("fallback", "signature_invalid")
    assert expected in result["detail"]

    assert shopify_env.main(["check", "https://shop.example", "--json"]) == 4
    checked = json.loads(capsys.readouterr().out)
    assert checked["signed"] is False and checked["state"] == "invalid"
    assert shopify_env.main(["check", "https://shop.example"]) == 4
    assert "not usable" in capsys.readouterr().out
    assert shopify_env.main(["list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["authorities"]["shop.example"]["state"] == "invalid"


def test_expired_block_has_no_headers(tmp_path: Path) -> None:
    path = _write_env(tmp_path, _block(_signature_input(PAST)))
    entry = shopify_env.parse_env_file(path)["authorities"]["shop.example"]
    assert shopify_env.signing_state(entry)[0] == "expired"
    with pytest.raises(ValueError):
        shopify_env.signature_headers(entry)


def test_env_file_cannot_switch_robots_handling_off(tmp_path: Path) -> None:
    path = _write_env(tmp_path, "Ignore-Robots = yes\n" + _block(
        _signature_input(FUTURE), extra="ignore_robots = true\n"))
    env = shopify_env.parse_env_file(path)
    assert "ignore_robots" not in env["crawl"]
    assert "crawl" not in env["authorities"]["shop.example"]
    refused = [p for p in env["problems"] if "ignore-robots is not accepted here" in p]
    assert len(refused) == 2
    assert "ignore-robots" not in shopify_env.CRAWL_KEYS


def test_unrecognised_lines_are_not_echoed(tmp_path: Path) -> None:
    path = _write_env(tmp_path, "c2VjcmV0LXRva2Vu/PASTED+SECRET==\nTypo-Key = 1\n")
    problems = "\n".join(shopify_env.parse_env_file(path)["problems"])
    assert "PASTED" not in problems and "c2VjcmV0" not in problems
    assert "line 1: not a recognised setting" in problems
    assert "unknown key 'typo-key'" in problems


def test_out_of_range_numeric_settings_are_ignored(tmp_path: Path) -> None:
    path = _write_env(tmp_path, "Max-Pages = -5\nTimeout = 0\nSample-Per-Template = 0\n"
                                "Timeout = 100000\nMax-Pages = 200\n")
    env = shopify_env.parse_env_file(path)
    assert env["crawl"] == {"max_pages": 200}
    assert len([p for p in env["problems"] if "must be between" in p]) == 4
