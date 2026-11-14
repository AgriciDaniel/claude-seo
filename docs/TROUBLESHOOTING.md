# Troubleshooting

## Common Issues

### Skill Not Loading

**Symptom:** `/seo` command not recognized

**Solutions:**

For plugin installs, verify and reinstall through Claude Code:
```bash
/plugin list
/plugin marketplace add AgriciDaniel/claude-seo
/plugin install claude-seo@agricidaniel-claude-seo
```

For manual installs:

1. Verify installation:
```bash
ls ~/.claude/skills/seo/SKILL.md
```

2. Check SKILL.md has proper frontmatter:
```bash
head -5 ~/.claude/skills/seo/SKILL.md
```
Should start with `---` followed by YAML.

3. Restart Claude Code:
```bash
claude
```

4. Re-run installer:

Caution: Prefer downloading, inspecting, then running remote scripts; the pipe-to-shell form below is the less-safe convenience option.

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash
```

---

### Python Dependency Errors

**Symptom:** `ModuleNotFoundError: No module named 'requests'`

**Solution:**

Dependencies belong in the managed runtime. For a plugin install, run:

```bash
/seo doctor
/seo setup
```

For a manual install, run:
```bash
~/.claude/skills/seo/scripts/claude-seo doctor
~/.claude/skills/seo/scripts/claude-seo setup
```

Do not install individual packages, use `pip --user`, or create a PATH shim.

### requirements.txt Not Found

**Symptom:** `No such file: requirements.txt` after install

**Solution:** For plugin installs, reinstall the plugin first:

```bash
/plugin install claude-seo@agricidaniel-claude-seo
```

For manual installs, requirements.txt is copied to the skill directory:

```bash
ls ~/.claude/skills/seo/requirements.txt
```

If missing, download it directly:
```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/requirements.txt \
  -o ~/.claude/skills/seo/requirements.txt
```

### Windows Python Detection Issues

**Symptom:** `python is not recognized` or `pip points to wrong Python`

**Solution (v1.2.0+):** The Windows installer now tries both `python` and `py -3`. If both fail:

1. Install Python from [python.org](https://python.org) and check "Add to PATH"
2. Rerun `install.ps1`. It uses `CLAUDE_SEO_PYTHON` when set, otherwise the first of `py -3`, `python3` and `python` that is Python 3.11 to 3.14, otherwise the newest of `py -3.14` down to `py -3.11`
3. If `py -3` is a newer Python that Claude SEO does not support yet (such as 3.15), install 3.14 alongside it, or set `CLAUDE_SEO_PYTHON` to a supported `python.exe`
4. Run `/seo doctor` after installation

---

### Playwright Screenshot Errors

**Symptom:** `playwright._impl._errors.Error: Executable doesn't exist`

**Solution:** rerun managed setup so the browser is installed through the same
interpreter and persistent browser directory:
```bash
/seo setup
/seo doctor
```

---

### Chromium Sandbox Warning

**Symptom:** rendering, screenshots or visual analysis work, but stderr shows
`claude-seo warning: Chromium's sandbox is unavailable on this system, so the
page is rendered without it` (or `running as root`, or `disabled by
CLAUDE_SEO_CHROMIUM_NO_SANDBOX`), and the JSON result has `"sandbox": false`.

**Cause:** Claude SEO starts Chromium with its sandbox wherever the system can
start it. Some systems cannot:

- **Ubuntu 23.10 and later** (and GitHub's Ubuntu runners): AppArmor blocks
  unprivileged user namespaces by default, which the sandbox needs.
- **Docker and other containers:** the default seccomp profile blocks user
  namespaces, and most images run as root.
- **root:** Chromium does not run sandboxed as root.

There the browser is launched once more without the sandbox, behind the same
egress guard. The audit still works, but a browser exploit served by an audited
page is not contained (as root, it runs as root).

**Solution:** to get the sandbox back:

- Ubuntu: follow Chromium's guide on AppArmor user namespace restrictions:
  <https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md>
- Containers: run as a non-root user and allow user namespaces (Playwright's
  Docker guide ships a seccomp profile for this).
- root: run Claude SEO as a regular user.

Two environment variables change the policy:

| Variable | Effect |
|----------|--------|
| `CLAUDE_SEO_CHROMIUM_REQUIRE_SANDBOX=1` | Strict mode: never render without the sandbox; fail instead |
| `CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1` | Skip the sandbox attempt (the warning still appears) |

Accepted values are `1`, `true`, `yes` and `on`.

---

### Chromium Sandbox Required but Unavailable

**Symptom:** the result's `error` says `Chromium's sandbox could not start on
this system` (or `cannot start as root`) `and CLAUDE_SEO_CHROMIUM_REQUIRE_SANDBOX
is set, so nothing was rendered`, or that both variables are set and contradict
each other.

**Cause:** strict mode is on and the sandbox cannot start (see the entry above
for why). With both variables set, strict mode wins and the launch is refused.

**Solution:** enable the sandbox as described above, or unset
`CLAUDE_SEO_CHROMIUM_REQUIRE_SANDBOX` to allow the automatic fallback with a
warning. For the conflict, unset one of the two variables.

---

### Permission Denied Errors

**Symptom:** `Permission denied` when running scripts

**Solution:**
```bash
chmod +x ~/.claude/skills/seo/scripts/*.py
```

---

---

### Subagent Not Found

**Symptom:** `Agent 'seo-technical' not found`

**Solution:**

For plugin installs, check `/plugin list` and reinstall `claude-seo@agricidaniel-claude-seo`; subagents load from the plugin, not `~/.claude/agents/`.

For manual installs:

1. Verify agent files exist:
```bash
ls ~/.claude/agents/seo-*.md
```

2. Check agent frontmatter:
```bash
head -5 ~/.claude/agents/seo-technical.md
```

3. Re-install agents:
```bash
cp /path/to/claude-seo/agents/*.md ~/.claude/agents/
```

---

### Timeout Errors

**Symptom:** `Request timed out after 30 seconds`

**Solutions:**

1. The target site may be slow: try again
2. Increase timeout in script calls
3. Check your network connection
4. Some sites block automated requests

---

### Schema Validation False Positives

**Symptom:** Hook blocks valid schema

**Check:**

1. Ensure placeholders are replaced
2. Verify @context is `https://schema.org`
3. Check for deprecated/retired types: HowTo and SpecialAnnouncement, plus the June 2025 retirements (ClaimReview, VehicleListing, EstimatedSalary, LearningVideo, and the CourseInfo carousel)
4. FAQPage rich results were retired for all sites on 2026-05-07. The hook does not block it because it remains a valid Schema.org type, but no AI or ranking benefit is confirmed.
5. Validate at [Google's Rich Results Test](https://search.google.com/test/rich-results)

---

### Slow Audit Performance

**Symptom:** Full audit takes too long

**Solutions:**

1. Audit crawls up to 500 pages: large sites take time
2. Subagents run in parallel to speed up analysis
3. For faster checks, use `/seo page` on specific URLs
4. Check if site has slow response times

---

## Getting Help

1. **Check the docs:** Review [COMMANDS.md](COMMANDS.md) and [ARCHITECTURE.md](ARCHITECTURE.md)

2. **GitHub Issues:** Report bugs at the repository

3. **Logs:** Check Claude Code's output for error details

## Debug Mode

To see detailed output, check Claude Code's internal logs or run scripts directly:

```bash
# Test fetch
python3 ~/.claude/skills/seo/scripts/fetch_page.py https://example.com

# Test parse
python3 ~/.claude/skills/seo/scripts/parse_html.py page.html --json

# Test screenshot
python3 ~/.claude/skills/seo/scripts/capture_screenshot.py https://example.com
```
