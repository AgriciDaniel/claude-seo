# Codex Plugin Manifest

## Summary

This improvement adds a Codex-compatible plugin manifest at:

```text
.codex-plugin/plugin.json
```

The goal is to make the existing `claude-seo` repository directly recognizable as a Codex plugin without changing the current Claude Code packaging, skill layout, or execution model.

## Why this was added

The repository already contains the core assets needed for Codex consumption:

- a stable project identity
- a large `skills/` surface
- cross-harness instructions in `AGENTS.md`
- portable `SKILL.md` files

What was missing was the Codex-specific manifest expected at `.codex-plugin/plugin.json`.

Adding that manifest provides a Codex-facing entrypoint while preserving the existing Claude Code structure under `.claude-plugin/`.

## Scope of the change

This contribution intentionally does only one thing:

- adds a valid Codex manifest

It does not:

- move or rename skills
- change existing Claude Code install flows
- add or remove MCP servers
- add Codex marketplace metadata
- change runtime behavior of the SEO skills themselves

## Files involved

### Added

- `.codex-plugin/plugin.json`

### Reused as source of truth

- `.claude-plugin/plugin.json`
- `skills/`
- `assets/growth-3-months.png`
- `AGENTS.md`

## Manifest design

The Codex manifest mirrors the existing plugin identity rather than introducing a second product identity.

### Chosen values

- `name`: `claude-seo`
- `version`: `2.2.0`
- `skills`: `./skills/`
- `displayName`: `Claude SEO`
- `developerName`: `AgriciDaniel`

The manifest also includes:

- repository and homepage metadata
- a minimal keyword set for discovery
- a short Codex-oriented UI description
- three default prompts
- one existing screenshot asset

## Relationship with existing packaging

The repository now exposes two parallel manifest surfaces:

| Surface | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | Claude Code / existing project packaging |
| `.codex-plugin/plugin.json` | Codex plugin discovery and validation |

This is a compatibility addition, not a migration.

The current repository remains Claude-first in its documentation and installation flow. The new Codex manifest simply makes that same skill pack legible to Codex tooling.

## Validation performed

The manifest was validated with the Codex plugin validator:

```bash
python C:\Users\x-v-i\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py H:\AgriciDaniel-claude-seo\claude-seo-main
```

Validation result:

```text
Plugin validation passed: H:\AgriciDaniel-claude-seo\claude-seo-main
```

## Current limitations

This improvement is intentionally minimal. A few things are still outside scope:

### No Codex marketplace entry

The repo now contains a valid local Codex manifest, but it does not yet define a Codex marketplace installation path or marketplace JSON entry.

### No Codex-specific apps or MCP manifest

The new manifest references the existing `skills/` directory only. It does not currently add:

- `.app.json`
- `.mcp.json`
- Codex-specific hook wiring

### UI metadata is conservative

The `interface` block is valid and usable, but intentionally lightweight. It is suitable for technical compatibility and local validation, not yet for polished marketplace presentation.

## Why the manifest was kept minimal

A minimal manifest reduces review risk:

- less duplicated metadata to maintain
- lower chance of drift versus `.claude-plugin/plugin.json`
- no speculative Codex-only capabilities
- easier future extension into marketplace packaging

This makes the contribution easier to review as an additive compatibility improvement.

## Recommended next steps

If the maintainer wants to take Codex support further, the next logical steps are:

1. document Codex installation and usage explicitly in `README.md`
2. add a Codex marketplace entry for local or distributable installation
3. decide whether this repo should remain Claude-first or become dual-first
4. enrich the `interface` block with final product copy, branding, and screenshots
5. add Codex-specific MCP or app manifests only where there is a real runtime need

## Contribution workflow for this change

This improvement should be submitted using the repository's normal contribution flow:

1. fork the repository
2. create a feature branch
3. make and validate the change locally
4. test with a representative sample target when relevant
5. open a PR that explains what changed and why

If the maintainer asks for a bug-style reproduction or follow-up evidence, the repository's
`CONTRIBUTING.md` requests:

- OS and Python version
- full terminal error output
- the command or step that failed
- the analyzed URL, when applicable

That information is especially useful here if review feedback touches validation behavior,
packaging compatibility, or Codex manifest ingestion.

### Contribution rules to follow

Any follow-up work on this Codex compatibility layer should stay aligned with the repository's
contribution rules:

- Python scripts should output JSON so the host agent can parse results reliably
- shell scripts should use `set -euo pipefail`
- `SKILL.md` files should stay under 500 lines
- reference files should stay focused and under 200 lines
- directories and files should use kebab-case naming
- dependencies should be kept minimal
- Python code should follow PEP 8 and be checked with `ruff check` or `flake8` before submission

For this specific improvement, those rules support a narrow implementation strategy:

- keep the Codex manifest additive rather than restructuring the repo
- avoid introducing new runtime dependencies unless Codex support genuinely requires them
- keep any future Codex-specific reference or setup documents small and targeted
- preserve the existing skill layout instead of renaming folders without a strong compatibility need

## Reviewer notes

This change was designed to be:

- additive
- low-risk
- backward-compatible
- easy to validate mechanically

It should be reviewable as a packaging compatibility enhancement rather than as an architectural change.
