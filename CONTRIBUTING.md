# Contributing to claude-seo

Thanks for your interest in contributing! Here's how to get involved.

## Reporting Bugs

Open a [GitHub Issue](https://github.com/AgriciDaniel/claude-seo/issues) with:

- Your OS and Python version
- The full error output (copy from terminal)
- The command or step that failed
- The URL you were analyzing (if applicable)

## Suggesting Features

Use [GitHub Discussions](https://github.com/AgriciDaniel/claude-seo/discussions) for feature ideas and questions.

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Test with a sample URL before submitting
5. Submit a PR with a clear description of what changed and why

### Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/claude-seo.git
cd claude-seo
bash install.sh
```

### Guidelines

- All Python scripts should output JSON for Claude Code to parse
- Shell scripts should use `set -euo pipefail` for safety
- SKILL.md files must stay under 500 lines
- Reference files should be focused and under 200 lines
- Follow kebab-case naming for all directories and files
- Keep dependencies minimal

### Code Style

- Python: Follow PEP 8 conventions. Use `ruff check` or `flake8` for linting before submitting
- Shell: Use `set -euo pipefail` and quote all variables
- Markdown: Keep lines under 120 characters where practical
