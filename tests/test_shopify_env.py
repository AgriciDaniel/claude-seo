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
    assert "other.example" in env["authorities"]
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
