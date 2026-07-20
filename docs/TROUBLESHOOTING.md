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

As of v1.2.0, dependencies are installed in a venv. Try:

```bash
# Use the venv pip
~/.claude/skills/seo/.venv/bin/pip install -r ~/.claude/skills/seo/requirements.txt
```

If the venv doesn't exist, install with `--user`:
```bash
pip install --user -r ~/.claude/skills/seo/requirements.txt
```

Do not install individual packages; use the shipped requirements file:
```bash
pip install --user -r ~/.claude/skills/seo/requirements.txt
```

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
2. Or use the Windows launcher: `py -3 -m pip install -r requirements.txt`
3. Use `python3 -m pip` instead of bare `pip`

---

### Playwright Screenshot Errors

**Symptom:** `playwright._impl._errors.Error: Executable doesn't exist`

**Solution:**
```bash
playwright install chromium
```

If that fails:
```bash
pip install playwright
python3 -m playwright install chromium
```

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
4. FAQPage rich results were retired for all sites on 2026-05-07: FAQPage no longer yields rich results, but the hook should NOT block it (still a valid AI/entity signal)
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
