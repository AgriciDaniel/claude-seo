---
description: Run a claude-seo command such as audit, page, technical, schema, or local
---

Load the skill with ID `seo` using the skill tool, then follow its invocation
instructions for: $ARGUMENTS

Before running any bundled script, replace `${CLAUDE_PLUGIN_ROOT}` in the
command with the repository root. Never export it. If the `seo` skill is not
available, stop and tell the user to restart OpenCode from the repository root
(the directory containing `scripts/claude-seo`).
