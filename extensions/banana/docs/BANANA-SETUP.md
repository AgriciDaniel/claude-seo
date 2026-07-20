# Banana Extension Setup Guide

## Google AI API Key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click "Create API key"
4. Copy the key. You'll need it during installation

**Free tier limits:**
- Check current limits in Google AI Studio before batch work

## MCP Server Configuration

The installer configures this automatically. If you need to set it up manually,
add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "nanobanana-mcp": {
      "command": "npx",
      "args": ["-y", "@ycse/nanobanana-mcp@1.1.1"],
      "env": {
        "GOOGLE_AI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

Scripted setup helper:
```bash
python3 extensions/banana/scripts/setup_mcp.py --key YOUR_KEY
```

## Verifying Installation

Run the validation script:
```bash
python3 ~/.claude/skills/seo-image-gen/scripts/validate_setup.py
```

Or check manually:
1. `ls ~/.claude/skills/seo-image-gen/SKILL.md`:skill file exists
2. `ls ~/.claude/agents/seo-image-gen.md`:agent file exists
3. `grep nanobanana ~/.claude/settings.json`:MCP configured

## Common Issues

### "MCP tools not available"
- Restart Claude Code after installing the extension
- Verify your API key is valid at [aistudio.google.com](https://aistudio.google.com)
- Check `~/.claude/settings.json` has the nanobanana-mcp entry

### "Rate limited (429)"
- Check current free-tier limits in Google AI Studio
- Wait 60 seconds and retry
- For batch operations, add delays between requests

### "IMAGE_SAFETY" error
- The safety filter flagged your prompt (often a false positive)
- Claude will suggest rephrased alternatives automatically
- Common triggers: certain color descriptions, implied scenarios
- See `references/prompt-engineering.md` Safety Rephrase section

### "Node.js version too old"
- Requires Node.js 20+
- Update via nvm: `nvm install 20 && nvm use 20`
- Or download from [nodejs.org](https://nodejs.org/)

### Generated images not appearing
- Default output directory: `~/Documents/nanobanana_generated/`
- Check the path returned by Claude after generation
- Verify disk space is available

## ImageMagick (Optional)

For post-processing (WebP conversion, cropping, background removal):

```bash
# Ubuntu/Pop!_OS
sudo apt install imagemagick

# Verify
magick --version
```

If `magick` (v7) is not available, the scripts fall back to `convert` (v6).
