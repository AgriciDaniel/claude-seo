# Troubleshooting

## Common Issues

### Skill Not Loading

**Symptom:** `/seo-audit` command not recognized

**Solutions:**

1. Verify installation:
```bash
ls ~/.config/opencode/seo-skills/SKILL.md
```

2. Check SKILL.md has proper frontmatter:
```bash
head -5 ~/.config/opencode/seo-skills/SKILL.md
```
Should start with `---` followed by YAML.

3. Restart Claude Code:
```bash
opencode
```

4. Re-run installer:

Caution: Prefer downloading, inspecting, then running remote scripts; the pipe-to-shell form below is the less-safe convenience option.

```bash
curl -fsSL https://raw.githubusercontent.com/DevShaded/opencode-seo/main/install.sh | bash
```

---

### Python Dependency Errors

**Symptom:** `ModuleNotFoundError: No module named 'requests'`

**Solution:**

As of v1.2.0, dependencies are installed in a venv. Try:

```bash
# Use the venv pip
~/.config/opencode/seo-skills/.venv/bin/pip install -r ~/.config/opencode/seo-skills/requirements.txt
```

If the venv doesn't exist, install with `--user`:
```bash
pip install --user -r ~/.config/opencode/seo-skills/requirements.txt
```

Or install individually:
```bash
pip install --user beautifulsoup4 requests lxml playwright Pillow urllib3 validators
```

### requirements.txt Not Found

**Symptom:** `No such file: requirements.txt` after install

**Solution:** As of v1.2.0, requirements.txt is copied to the skill directory:

```bash
ls ~/.config/opencode/seo-skills/requirements.txt
```

If missing, download it directly:
```bash
curl -fsSL https://raw.githubusercontent.com/DevShaded/opencode-seo/main/requirements.txt \
  -o ~/.config/opencode/seo-skills/requirements.txt
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
chmod +x ~/.config/opencode/seo-skills/scripts/*.py
```

---

---

### Subagent Not Found

**Symptom:** `Agent 'seo-technical' not found`

**Solution:**

1. Verify agent files exist:
```bash
ls ~/.config/opencode/agents/seo-*.md
```

2. Check agent frontmatter:
```bash
head -5 ~/.config/opencode/agents/seo-technical.md
```

3. Re-install agents:
```bash
cp /path/to/opencode-seo/agents/*.md ~/.opencode/agents/
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
3. Check for deprecated types (HowTo, SpecialAnnouncement)
4. Validate at [Google's Rich Results Test](https://search.google.com/test/rich-results)

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
python3 ~/.config/opencode/seo-skills/scripts/fetch_page.py https://example.com

# Test parse
python3 ~/.config/opencode/seo-skills/scripts/parse_html.py page.html --json

# Test screenshot
python3 ~/.config/opencode/seo-skills/scripts/capture_screenshot.py https://example.com
```
