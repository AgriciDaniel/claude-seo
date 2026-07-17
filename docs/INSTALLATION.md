# Installation Guide

## Prerequisites

- **Python 3.10+** with pip
- **Git** for cloning the repository
- **OpenCode CLI** installed and configured

Optional:
- **Playwright** for screenshot capabilities

## Quick Install

### Bash Installer (Recommended)

The recommended path. Inside OpenCode:

```bash
git clone --depth 1 https://github.com/DevShaded/claude-seo.git
bash claude-seo/install.sh
```

### Manual Install (Unix, macOS, Linux)

```bash
git clone --depth 1 https://github.com/DevShaded/claude-seo.git
bash opencode-seo/install.sh
```

Review-then-run alternative:

```bash
curl -fsSL https://raw.githubusercontent.com/DevShaded/opencode-seo/main/install.sh > install.sh
cat install.sh        # review
bash install.sh       # run when satisfied
rm install.sh
```

### Manual Install (Windows, PowerShell)

```powershell
git clone --depth 1 https://github.com/DevShaded/claude-seo.git
powershell -ExecutionPolicy Bypass -File claude-seo\install.ps1
```

The Windows path uses `git clone` rather than `irm | iex` because OpenCode's own security guardrails flag piped remote-script execution. Inspect `install.ps1` before running.

## Manual Installation

1. **Clone the repository**

```bash
git clone https://github.com/DevShaded/claude-seo.git
cd opencode-seo
```

2. **Run the installer**

```bash
./install.sh
```

3. **Install Python dependencies** (if not done automatically)

The installer creates a venv at `~/.config/opencode/seo-skills/.venv/`. If that fails, install manually:

```bash
# Option A: Use the venv
~/.config/opencode/seo-skills/.venv/bin/pip install -r ~/.config/opencode/seo-skills/requirements.txt

# Option B: User-level install
pip install --user -r ~/.config/opencode/seo-skills/requirements.txt
```

4. **Install Playwright browsers** (optional, for visual analysis)

```bash
pip install playwright
playwright install chromium
```

Playwright is optional. Without it, visual analysis uses WebFetch as a fallback.

## Installation Paths

The installer copies files to:

| Component | Path |
|---|---|
| Skills | `~/.config/opencode/seo-skills/` |
| Commands | `~/.config/opencode/commands/` |
| Agents | `~/.config/opencode/agents/seo-*.md` |

## Verify Installation

1. Start OpenCode:

```bash
opencode
```

2. Check that the skill is loaded:

```
/seo-audit https://example.com
```

You should see a help message or prompt for a URL.

## Uninstallation

Run the uninstaller from a fresh clone:

```bash
git clone --depth 1 https://github.com/DevShaded/claude-seo.git
bash opencode-seo/uninstall.sh
```

`uninstall.sh` removes all installed sub-skills, sub-agents, and the plugin's MCP entries from `~/.opencode/settings.json`. Do not maintain a hand-coded `rm` list. The shipped uninstaller is the canonical source.

## Upgrading

To upgrade to the latest version:

Caution: Prefer downloading, inspecting, then running remote scripts; the pipe-to-shell form below is the less-safe convenience option.

```bash
# Uninstall current version
curl -fsSL https://raw.githubusercontent.com/DevShaded/opencode-seo/main/uninstall.sh | bash

# Install new version
curl -fsSL https://raw.githubusercontent.com/DevShaded/opencode-seo/main/install.sh | bash
```

## Troubleshooting

### "Skill not found" error

Ensure the skill is installed in the correct location:

```bash
ls ~/.config/opencode/seo-skills/SKILL.md
```

If the file doesn't exist, re-run the installer.

### Python dependency errors

Install dependencies manually:

```bash
pip install beautifulsoup4 requests lxml playwright Pillow urllib3 validators
```

### Playwright screenshot errors

Install Chromium browser:

```bash
playwright install chromium
```

### Permission errors on Unix

Make sure scripts are executable:

```bash
chmod +x ~/.config/opencode/seo-skills/scripts/*.py
```
