# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue**
2. Open a [GitHub Security Advisory](https://github.com/AgriciDaniel/claude-seo/security/advisories/new) on this repo
3. Or contact the maintainer directly

## Response Timeline

- **Acknowledgment**: Within 72 hours of report
- **Status update**: Within 7 days with initial assessment
- **Resolution**: We aim to release a fix within 30 days for confirmed vulnerabilities

## Supported Versions

Only the latest version receives security updates.

## Security Practices

- No credentials or API keys are stored in this repository
- Install scripts write only to user-level directories (`~/.claude/`)
- Python scripts use PEP 723 inline metadata; dependencies are resolved per-script by `uv run`
