from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / ".opencode"


def test_config_is_strict_json_and_minimal() -> None:
    data = json.loads((ADAPTER / "opencode.json").read_text(encoding="utf-8"))
    assert data["$schema"] == "https://opencode.ai/config.json"
    assert data["skills"] == ["./skills"]
    assert data["instructions"] == [".opencode/instructions.md"]
    for key in (
        "model",
        "default_agent",
        "agents",
        "permissions",
        "mcp",
        "providers",
        "plugins",
    ):
        assert key not in data


def test_instructions_contract() -> None:
    text = (ADAPTER / "instructions.md").read_text(encoding="utf-8")
    for phrase in (
        ".claude-plugin/plugin.json",
        "CLAUDE_PLUGIN_ROOT",
        "CLAUDE_PLUGIN_DATA",
        "CLAUDE_SEO_DATA_DIR",
        "repository root",
        "./scripts/claude-seo",
        "CLAUDE.md",
        "CLAUDE_SKILL_DIR",
        "webfetch",
        "timeout",
        "doctor --json",
        "Windows",
        "py -3 scripts/runtime.py",
        "Build",
        'mode must be `"manual"`',
    ):
        assert phrase in text, phrase
    assert "/opt/" not in text
    assert "/Users/" not in text
    assert "export CLAUDE_PLUGIN_ROOT" not in text


def test_command_contract() -> None:
    text = (ADAPTER / "commands" / "seo.md").read_text(encoding="utf-8")
    assert "$ARGUMENTS" in text
    assert "skill" in text
    assert "repository root" in text
    assert "!`" not in text


def test_gitattributes_forces_lf() -> None:
    text = (ADAPTER / ".gitattributes").read_text(encoding="utf-8")
    assert "* text eol=lf" in text


ADAPTER_SCRIPT = ROOT / ".opencode" / "adapter" / "build_agents.py"
FIXTURE_ALPHA = "seo-alpha"
FIXTURE_BETA = "seo-beta"
FIXTURE_GAMMA = "seo-gamma"


def write_source(root: Path, rel: str | Path, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fixture_root(tmp_path: Path) -> Path:
    write_source(
        tmp_path,
        Path("agents", f"{FIXTURE_ALPHA}.md"),
        """---
name: seo-alpha
description: >
  Alpha agent that does
  useful things.
model: sonnet
maxTurns: 35
tools: Read, Bash, Write  # report output
---

Alpha body.
""",
    )
    write_source(
        tmp_path,
        Path("agents", f"{FIXTURE_BETA}.md"),
        """---
name: seo-beta
description: "Beta: quoted description."
model: opus
maxTurns: 15
tools: Read, WebFetch
---

Beta body.
""",
    )
    write_source(
        tmp_path,
        Path("extensions", "ext", "agents", f"{FIXTURE_GAMMA}.md"),
        """---
name: seo-gamma
description: Gamma agent.
model: sonnet
maxTurns: 30
tools:
  - Read
  - Glob
---

Gamma body.
""",
    )
    write_source(
        tmp_path,
        Path("extensions", "ext", "agents", f"{FIXTURE_ALPHA}.md"),
        """---
name: seo-alpha
description: Duplicate should be ignored.
maxTurns: 99
tools: Read
---

Duplicate body.
""",
    )
    return tmp_path


def load_generator():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_agents", ADAPTER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_folded_quoted_and_plain_descriptions(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    sources = {agent.id: agent for agent in module.discover_agents(root)}
    assert sources["seo-alpha"].description == "Alpha agent that does useful things."
    assert sources["seo-beta"].description == "Beta: quoted description."
    assert sources["seo-gamma"].description == "Gamma agent."
    assert sources["seo-alpha"].max_turns == 35
    assert sources["seo-alpha"].tools == ("Read", "Bash", "Write")
    assert sources["seo-gamma"].tools == ("Read", "Glob")
    assert sources["seo-alpha"].source == Path("agents", f"{FIXTURE_ALPHA}.md")
    assert len(sources) == 3


def test_render_wrapper_has_native_frontmatter_and_least_privilege(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    sources = {agent.id: agent for agent in module.discover_agents(root)}
    beta = module.render_wrapper(sources["seo-beta"])
    assert "mode: subagent" in beta
    assert "steps: 16" in beta
    assert "tools:" not in beta
    assert "name:" not in beta
    assert "model:" not in beta
    assert "maxTurns" not in beta
    assert "deny" in beta
    assert "- { action: webfetch" in beta
    assert "- { action: read" in beta
    assert "- { action: skill" in beta
    assert "- { action: shell" not in beta
    assert "- { action: edit" not in beta
    assert Path("agents", f"{FIXTURE_BETA}.md").as_posix() in beta
    assert str(root) not in beta
    assert "no shell access" in beta
    assert "Run bundled tools as" not in beta

    alpha = module.render_wrapper(sources["seo-alpha"])
    assert "- { action: shell" in alpha
    assert "- { action: edit" in alpha
    assert "Run bundled tools as" in alpha
    assert "./scripts/claude-seo" in alpha


def test_write_is_idempotent_and_prunes_only_generated(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    first = module.write_wrappers(root)
    assert first["written"] == ["seo-alpha", "seo-beta", "seo-gamma"]
    output = root / ".opencode" / "agents"
    assert sorted(p.name for p in output.glob("*.md")) == [
        f"{FIXTURE_ALPHA}.md",
        f"{FIXTURE_BETA}.md",
        f"{FIXTURE_GAMMA}.md",
    ]
    second = module.write_wrappers(root)
    assert second["written"] == []
    assert second["changed"] == []
    stale = output / "seo-stale.md"
    stale.write_text(
        "---\n"
        'description: "stale"\n'
        "mode: subagent\n"
        "steps: 2\n"
        "permissions:\n"
        '  - { action: "*", resource: "*", effect: deny }\n'
        "---\n"
        f"{module.GENERATED_MARKER}\nstale\n",
        encoding="utf-8",
    )
    third = module.write_wrappers(root)
    assert third["pruned"] == ["seo-stale"]
    assert not stale.exists()


def test_write_refuses_non_generated_file(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    output = root / ".opencode" / "agents"
    output.mkdir(parents=True)
    keep = output / "keep.md"
    keep.write_text("hand written\n", encoding="utf-8")
    result = module.write_wrappers(root)
    assert result["errors"]
    assert keep.exists()
    assert not (output / f"{FIXTURE_ALPHA}.md").exists()
    assert module.main(["--check", "--root", str(root)]) == 1


def test_check_detects_drift(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    module.write_wrappers(root)
    wrapper = root / ".opencode" / "agents" / f"{FIXTURE_ALPHA}.md"
    wrapper.write_text(wrapper.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
    result = module.check_wrappers(root)
    assert result["changed"] == [FIXTURE_ALPHA]
    assert module.main(["--check", "--root", str(root)]) == 1


def test_unknown_tool_is_an_error(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    write_source(
        tmp_path,
        Path("agents", "seo-delta.md"),
        "---\ndescription: Delta.\nmaxTurns: 15\ntools: Read, NotebookEdit\n---\n\nBody.\n",
    )
    with pytest.raises(ValueError, match="NotebookEdit"):
        module.discover_agents(root)


def test_duplicate_extension_agents_are_an_error(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    for extension in ("a", "b"):
        write_source(
            tmp_path,
            Path("extensions", extension, "agents", "seo-dup.md"),
            "---\ndescription: Dup.\nmaxTurns: 15\ntools: Read\n---\n\nBody.\n",
        )
    with pytest.raises(ValueError, match="seo-dup"):
        module.discover_agents(root)


def test_json_output_has_required_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    module.write_wrappers(root)
    assert module.main(["--check", "--json", "--root", str(root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {
        "written",
        "changed",
        "pruned",
        "missing",
        "stale",
        "errors",
        "sources",
    }
    assert {record["id"] for record in payload["sources"]} == {
        FIXTURE_ALPHA,
        FIXTURE_BETA,
        FIXTURE_GAMMA,
    }


def test_output_uses_lf_bytes(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    path = root / "agents" / "seo-crlf.md"
    path.write_text(
        "---\ndescription: CRLF agent.\nmaxTurns: 15\ntools: Read\n---\n\nBody.\n",
        encoding="utf-8",
        newline="\r\n",
    )
    module.write_wrappers(root)
    data = (root / ".opencode" / "agents" / "seo-crlf.md").read_bytes()
    assert b"\r\n" not in data


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs extra privileges on Windows")
def test_write_refuses_symlink(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    output = root / ".opencode" / "agents"
    output.mkdir(parents=True)
    target = root / "agents" / f"{FIXTURE_ALPHA}.md"
    (output / f"{FIXTURE_ALPHA}.md").symlink_to(target)
    result = module.write_wrappers(root)
    assert result["errors"]
    assert target.read_text(encoding="utf-8").startswith("---")
    assert module.GENERATED_MARKER not in target.read_text(encoding="utf-8")


SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"
EXTENSIONS = ROOT / "extensions"
WRAPPERS = ADAPTER / "agents"
HUB = SKILLS / "seo" / "SKILL.md"
AUDIT = SKILLS / "seo-audit" / "SKILL.md"


GENERATOR = load_generator()
split_frontmatter = GENERATOR.split_frontmatter
discover_agents = GENERATOR.discover_agents


def parse_wrapper(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    frontmatter, _ = split_frontmatter(text)
    data: dict[str, object] = {"permissions": []}
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("mode:"):
            data["mode"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("steps:"):
            data["steps"] = int(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("description:"):
            data["description"] = json.loads(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("- {") and "action:" in stripped:
            body = stripped.removeprefix("- {").removesuffix("}")
            rule = {}
            for part in body.split(","):
                key, value = part.split(":", 1)
                rule[key.strip()] = value.strip().strip('"')
            data["permissions"].append(rule)
    return data


def source_map() -> dict[str, object]:
    return {agent.id: agent for agent in discover_agents(ROOT)}


def test_wrapper_coverage() -> None:
    sources = source_map()
    assert "seo-matomo" in sources
    assert {p.stem for p in WRAPPERS.glob("*.md")} == set(sources)


def test_wrapper_frontmatter_parity() -> None:
    sources = source_map()
    for path in sorted(WRAPPERS.glob("seo-*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter, _ = split_frontmatter(text)
        keys = {
            line.split(":", 1)[0]
            for line in frontmatter.splitlines()
            if line and not line.startswith((" ", "-"))
        }
        for key in ("tools", "name", "model", "maxTurns"):
            assert key not in keys, (path, key)
        data = parse_wrapper(path)
        assert data["mode"] == "subagent", path
        source = sources[path.stem]
        assert data["description"] == source.description, path
        assert data["steps"] == source.max_turns + 1, path
        assert source.source.as_posix() in text, path
        assert str(ROOT) not in text, path


TOOL_ACTIONS = {
    "Read": "read",
    "Bash": "shell",
    "Write": "edit",
    "Glob": "glob",
    "Grep": "grep",
    "WebFetch": "webfetch",
    "WebSearch": "websearch",
}


def expected_actions(source) -> set[str]:
    actions = {TOOL_ACTIONS[tool] for tool in source.tools if tool in TOOL_ACTIONS}
    actions.add("skill")
    return actions


def test_permissions_mapping() -> None:
    sources = source_map()
    for path in sorted(WRAPPERS.glob("seo-*.md")):
        data = parse_wrapper(path)
        rules = data["permissions"]
        source = sources[path.stem]
        assert rules[0] == {"action": "*", "resource": "*", "effect": "deny"}, path
        assert rules[-1] == {
            "action": "skill",
            "resource": "seo*",
            "effect": "allow",
        }, path
        allowed = {rule["action"] for rule in rules if rule["effect"] == "allow"}
        assert allowed == expected_actions(source), path
        read_allow = next(
            index
            for index, rule in enumerate(rules)
            if rule == {"action": "read", "resource": "*", "effect": "allow"}
        )
        env_ask = {"action": "read", "resource": "*.env", "effect": "ask"}
        env_ask_glob = {"action": "read", "resource": "*.env.*", "effect": "ask"}
        env_example = {
            "action": "read",
            "resource": "*.env.example",
            "effect": "allow",
        }
        assert read_allow < rules.index(env_ask), path
        assert read_allow < rules.index(env_ask_glob), path
        assert read_allow < rules.index(env_example), path
        assert env_ask in rules, path
        assert env_ask_glob in rules, path
        assert env_example in rules, path

    assert "shell" not in expected_actions(sources["seo-flow"])
    assert "edit" not in expected_actions(sources["seo-flow"])
    assert "shell" not in expected_actions(sources["seo-cluster"])
    assert "websearch" in expected_actions(sources["seo-cluster"])
    assert "webfetch" in expected_actions(sources["seo-cluster"])
    for agent_id in ("seo-schema", "seo-visual"):
        assert "webfetch" not in expected_actions(sources[agent_id])
        assert "websearch" not in expected_actions(sources[agent_id])
    assert "shell" in expected_actions(sources["seo-technical"])
    assert "edit" in expected_actions(sources["seo-technical"])
    assert "webfetch" not in expected_actions(sources["seo-technical"])


def test_wrapper_body_has_no_literal_placeholder_command() -> None:
    sources = source_map()
    for path in sorted(WRAPPERS.glob("seo-*.md")):
        text = path.read_text(encoding="utf-8")
        data = parse_wrapper(path)
        actions = {rule["action"] for rule in data["permissions"] if rule["effect"] == "allow"}
        assert "${CLAUDE_PLUGIN_ROOT}/scripts" not in text, path
        assert str(ROOT) not in text, path
        assert sources[path.stem].source.as_posix() in text, path
        if "shell" in actions:
            assert "./scripts/claude-seo" in text, path
        else:
            assert "no shell access" in text, path
            assert "Run bundled tools as" not in text, path
            assert "./scripts/claude-seo" not in text, path


def test_hub_agents_have_wrappers() -> None:
    names = set()
    hub_text = HUB.read_text(encoding="utf-8")
    for line in hub_text.splitlines():
        if "spawn" in line.lower():
            names.update(re.findall(r"\b(seo-[a-z0-9-]+)\b", line))
    subagents = hub_text.split("## Subagents", 1)[1].split("## ", 1)[0]
    names.update(re.findall(r"^- `(seo-[a-z0-9-]+)`", subagents, re.M))
    audit_text = AUDIT.read_text(encoding="utf-8")
    names.update(re.findall(r"`(seo-[a-z0-9-]+)`", audit_text))
    assert names
    assert "seo-matomo" in names
    missing = names - {p.stem for p in WRAPPERS.glob("*.md")}
    assert not missing, missing


def test_skill_ids_are_discoverable() -> None:
    skill_paths = sorted(SKILLS.glob("*/SKILL.md"))
    assert skill_paths
    assert (SKILLS / "seo" / "SKILL.md").is_file()
    for path in skill_paths:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", path.parent.name), path
        frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        assert re.search(r"^description:\s*\S", frontmatter, re.M), path


def test_placeholder_scan() -> None:
    paths = list(AGENTS.glob("seo-*.md"))
    paths += list(SKILLS.glob("*/SKILL.md"))
    paths += list(SKILLS.glob("*/references/**/*.md"))
    paths += list(EXTENSIONS.glob("*/agents/seo-*.md"))
    paths += list(EXTENSIONS.glob("*/skills/*/SKILL.md"))
    paths += list(EXTENSIONS.glob("*/skills/*/references/**/*.md"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "${CLAUDE_PLUGIN_DATA}" not in text, path
        assert "${CLAUDE_SEO_DATA_DIR}" not in text, path
        assert not re.search(r"\$CLAUDE_PLUGIN_ROOT(?!\{)", text), path


def test_launcher_exists() -> None:
    launcher = ROOT / "scripts" / "claude-seo"
    assert launcher.is_file()
    assert (ROOT / "scripts" / "runtime.py").is_file()
    if os.name != "nt":
        assert os.access(launcher, os.X_OK)


def test_generated_freshness() -> None:
    result = subprocess.run(
        [sys.executable, str(ADAPTER_SCRIPT), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_files_have_no_absolute_paths() -> None:
    runtime = [
        ADAPTER / "opencode.json",
        ADAPTER / "instructions.md",
        ADAPTER / "commands" / "seo.md",
    ]
    runtime += sorted(WRAPPERS.glob("*.md"))
    for path in runtime:
        text = path.read_text(encoding="utf-8")
        assert "/opt/" not in text, path
        assert "/Users/" not in text, path


def test_consistency_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/consistency_check.py", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(
    os.environ.get("OPENCODE_LIVE") != "1",
    reason="set OPENCODE_LIVE=1 to run the live OpenCode check",
)
def test_live_opencode() -> None:
    result = subprocess.run(
        [sys.executable, ".opencode/adapter/live_check.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_write_refuses_empty_source_set(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    module.write_wrappers(root)
    for path in sorted((root / "agents").glob("seo-*.md")):
        path.unlink()
    result = module.write_wrappers(root)
    assert result["errors"]
    assert len(list((root / ".opencode" / "agents").glob("*.md"))) == 3


def test_quoted_description_with_hash_is_not_truncated(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    write_source(
        tmp_path,
        Path("agents", "seo-quoted.md"),
        '---\ndescription: "Ranks #1 for SEO audits."\nmaxTurns: 15\ntools: Read\n---\n\nBody.\n',
    )
    write_source(
        tmp_path,
        Path("agents", "seo-quoted-comment.md"),
        '---\ndescription: "Ranks #1."  # trailing note\nmaxTurns: 15\ntools: Read\n---\n\nBody.\n',
    )
    sources = {agent.id: agent for agent in module.discover_agents(root)}
    assert sources["seo-quoted"].description == "Ranks #1 for SEO audits."
    assert sources["seo-quoted-comment"].description == "Ranks #1."


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs extra privileges on Windows")
def test_write_refuses_directory_symlink(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    target = root / "outside-agents"
    target.mkdir()
    output = root / ".opencode" / "agents"
    output.parent.mkdir(parents=True)
    output.symlink_to(target, target_is_directory=True)
    result = module.write_wrappers(root)
    assert result["errors"]
    assert not list(target.glob("*.md"))


def test_edit_tool_maps_to_edit_action(tmp_path: Path) -> None:
    module = load_generator()
    root = fixture_root(tmp_path)
    write_source(
        tmp_path,
        Path("agents", "seo-edit.md"),
        "---\ndescription: Edit agent.\nmaxTurns: 15\ntools: Read, Edit\n---\n\nBody.\n",
    )
    sources = {agent.id: agent for agent in module.discover_agents(root)}
    assert sources["seo-edit"].tools == ("Read", "Edit")
    text = module.render_wrapper(sources["seo-edit"])
    assert "- { action: edit" in text


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs extra privileges on Windows")
def test_write_accepts_symlinked_root(tmp_path: Path) -> None:
    module = load_generator()
    fixture_root(tmp_path)
    link = tmp_path / "repo-link"
    link.symlink_to(tmp_path, target_is_directory=True)
    result = module.write_wrappers(link)
    assert not result["errors"], result["errors"]
    assert result["written"] == ["seo-alpha", "seo-beta", "seo-gamma"]
    assert (tmp_path / ".opencode" / "agents" / "seo-alpha.md").is_file()
