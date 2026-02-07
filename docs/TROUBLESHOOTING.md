# Troubleshooting

## Common Issues

### Skill Not Loading

**Symptom:** `/seo` command not recognized

**Solutions:**

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
```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash
```

---

### Python Dependency Errors

**Symptom:** `ModuleNotFoundError: No module named 'requests'`

**Solution:**
```bash
pip install -r ~/.claude/skills/seo/requirements.txt
```

Or install individually:
```bash
pip install beautifulsoup4 requests lxml playwright Pillow urllib3 validators
```

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
python -m playwright install chromium
```

---

### Permission Denied Errors

**Symptom:** `Permission denied` when running scripts

**Solution:**
```bash
chmod +x ~/.claude/skills/seo/scripts/*.py
chmod +x ~/.claude/skills/seo/hooks/*.py
chmod +x ~/.claude/skills/seo/hooks/*.sh
```

---

### Hook Not Triggering

**Symptom:** Schema validation hook not running

**Check:**

1. Verify hook is in settings:
```bash
cat ~/.claude/settings.json
```

2. Ensure correct path:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/seo/hooks/validate-schema.py \"$FILE_PATH\"",
            "exitCodes": { "2": "block" }
          }
        ]
      }
    ]
  }
}
```

3. Test hook directly:
```bash
python3 ~/.claude/skills/seo/hooks/validate-schema.py test.html
```

---

### Subagent Not Found

**Symptom:** `Agent 'seo-technical' not found`

**Solution:**

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

1. The target site may be slow — try again
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

1. Audit crawls up to 500 pages — large sites take time
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
