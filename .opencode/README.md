# OpenCode adapter for claude-seo

This directory makes the claude-seo skills, the `/seo` command, and the agent
delegation work from OpenCode V2, project-local, with no global install.

Run OpenCode from the repository root:

```bash
cd /path/to/claude-seo
opencode
/seo audit https://example.com
```

## What this covers

- All 26 core skills under `skills/`, discovered through `skills: ["./skills"]`
  in `.opencode/opencode.json`.
- The `/seo` command in `.opencode/commands/seo.md`, which loads the `seo` hub
  skill and passes the arguments.
- 20 subagent wrappers in `.opencode/agents/`, generated from `agents/` and
  `extensions/*/agents/`. Each wrapper is a pointer to the canonical prompt and
  carries least-privilege permissions derived from the upstream `tools:` list.

## What this does not cover

- The 9 extension sub-skills under `extensions/*/skills/`. Version 1 registers
  the 26 core skills only, so `/seo matomo`, `/seo firecrawl`, `/seo ahrefs`,
  and similar extension routes need the extension skill source added
  separately.
- Extension MCP servers. The `seo-dataforseo` agent is generated, but its
  `mcp__dataforseo__*` grant is not mapped. MCP tools use `<server>_<tool>`
  permission names and need an explicit `mcp.servers` entry.
- The Claude Code `PostToolUse` schema-validation hook. OpenCode has no
  declarative equivalent; a plugin port is future work.
- Model pinning. Subagents inherit the session model.

## Requirements

- OpenCode 2.x. The adapter is verified against 2.2.7.
- Python 3.11 to 3.14.
- A development environment outside the repository for the test and lint
  tools. Do not install the runtime `requirements.txt` globally: `setup`
  manages the project-local `.venv`.

```bash
python3 -m venv "${TMPDIR:-/tmp}/claude-seo-dev"
"${TMPDIR:-/tmp}/claude-seo-dev/bin/pip" install pytest ruff==0.17.1
```

Alternatively use `uv run --no-project --with pytest --with ruff==0.17.1 ...`.

## Fork setup

`origin` is your fork and `upstream` is `AgriciDaniel/claude-seo`:

```bash
git remote -v
git fetch upstream --tags
```

## First run

Preflight the environment so the runtime stays project-local:

```bash
env | grep -E '^CLAUDE_(PLUGIN_ROOT|PLUGIN_DATA|SEO_DATA_DIR)='
```

If that prints anything, unset the variables before continuing. Then:

```bash
./scripts/claude-seo setup
./scripts/claude-seo doctor --json
python3 .opencode/adapter/live_check.py
```

`doctor --json` must report `"mode": "manual"`. `.venv`, `ms-playwright`,
`runtime-state.json`, and the transient `.setup.lock` belong under the
repository root.

## Daily use

1. `cd` to the repository root.
2. Run `opencode`.
3. Run `/seo <command> <url>` from the Build agent. Plan mode restricts shell
   and edit tools, which most SEO commands need.
4. Use a strong model for long audits. Subagents inherit the session model.

## Generated agents

Never edit `.opencode/agents/*.md` by hand. Edit the canonical prompt in
`agents/` or `extensions/*/agents/`, then regenerate:

```bash
python3 .opencode/adapter/build_agents.py --write
python3 .opencode/adapter/build_agents.py --check
```

`--check` exits 1 when a wrapper is missing, stale, or changed. `--json` emits
a machine-readable summary with `written`, `changed`, `pruned`, `missing`,
`stale`, `errors`, and `sources`.

## Live harness

```bash
python3 .opencode/adapter/live_check.py
OPENCODE_LIVE=1 python3 -m pytest tests/test_opencode_adapter.py -q
```

The harness checks the installed OpenCode version, the skill registry, the 20
subagents with `mode: subagent` and their `steps`, and the `seo` command. Run
it after every OpenCode upgrade.

## Keeping a fork in sync

After an upstream release:

```bash
git fetch upstream --tags
git switch main
git merge upstream/main

python3 .opencode/adapter/build_agents.py --write
python3 .opencode/adapter/build_agents.py --check
python3 scripts/consistency_check.py --json
python3 -m pytest tests/test_opencode_adapter.py -q
uv run --no-project --with-requirements requirements.txt --with pytest pytest tests/ -q
ruff check .

git diff --stat
git add .opencode tests/test_opencode_adapter.py
git commit -m "chore(opencode): sync adapter with upstream"
git push origin main
```

Do not use `--ff-only`: adapter commits on `main` make a fast-forward merge
impossible. A normal upstream release changes only wrapper descriptions,
`steps`, or permissions. Anything else means upstream changed a contract;
read the failing test before resolving.

## Troubleshooting

- `/seo` exists but the `seo` skill is missing: OpenCode was launched from a
  subdirectory. Restart it at the repository root.
- A command fails with `/scripts/claude-seo`: the model expanded the
  placeholder without substituting the repository root. Rerun with
  `./scripts/claude-seo`.
- `doctor --json` reports a mode other than `manual`: unset
  `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, and `CLAUDE_SEO_DATA_DIR`, then
  restart OpenCode.
- Long commands (crawls, Lighthouse, screenshots, reports): call the shell tool
  with `timeout` of at least 600000 ms, or use `background: true` and poll.
- After an OpenCode upgrade: run the live harness before trusting the adapter.

## Permission model

Each wrapper starts with a broad deny, then allows only the actions mapped from
the upstream `tools:` list plus `skill` for `seo*`. The three `.env` rules are
appended after the broad `read` allow so OpenCode's built-in environment-file
prompt is preserved.

OpenCode appends agent rules after global rules and the last matching rule
wins. A wrapper allow can override a global deny for that subagent. Use
OpenCode policies when you need a hard deny.
