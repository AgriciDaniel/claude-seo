# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly. Do **not** open a public issue.

1. Open a private [GitHub Security Advisory](https://github.com/AgriciDaniel/claude-seo/security/advisories/new) on this repository (preferred channel).
2. As a fallback, email the maintainer at the address listed in [`CITATION.cff`](CITATION.cff).
3. Encrypt sensitive disclosures if you can. Request the maintainer's PGP key in the advisory or email — the key fingerprint is published in advisory threads on first request and is rotated yearly.

When reporting, please include:

- A short description of the issue and the impact you believe it has.
- A minimal reproducer (URL, command line, payload, or short script).
- Affected versions and platforms.
- Whether you have a suggested fix.

## Coordinated disclosure

claude-seo follows a **90-day coordinated disclosure** policy.

| Day | Event |
|---:|---|
| 0  | Maintainer acknowledges receipt. |
| ≤ 3   | Initial triage: severity classification (CVSS v3.1) and reproducibility confirmation. |
| ≤ 14  | Mitigation or fix candidate proposed. |
| ≤ 30  | Fix released in a patch version or backport; reporter credited in the release notes (opt-out available). |
| ≤ 90  | Public advisory published if not earlier. |

If a fix cannot be shipped within 90 days, the maintainer will request an extension with a clear technical reason. The reporter retains the right to disclose at the 90-day mark.

## Supported versions

| Version line | Status | Notes |
|---|---|---|
| **2.x** | ✅ Fully supported | Active development; security and bug fixes. |
| **1.9.x** | ✅ Patch-only for security | Final 1.x line; only CVSS ≥ High issues backported. |
| < 1.9 | ❌ Unsupported | Please upgrade. |

## Threat model

claude-seo is a research and audit toolkit that runs on a user's workstation. It accepts user-supplied URLs and credentials, and issues HTTP requests against arbitrary internet hosts. The threat model has three primary attacker types:

1. **Malicious audit target.** A site the user points claude-seo at attempts to leak local-network or cloud-metadata data via SSRF chains: private IP literals, decimal/hex/octal IPv4, FQDN trailing dot, 30x redirects to private IPs, DNS rebinding (initial public resolution → later private), IPv4-mapped IPv6, dual-stack hosts with one private record.

   **Mitigation:** `scripts/url_safety.py` is the canonical pre-flight + DNS-pinned fetch layer. Every URL-fetching script in this repository validates through it. See `tests/test_url_safety.py` for the regression suite (91 cases across 31 test functions, covering each bypass class).

2. **Tampered install.** A modified plugin install, GitHub release, or manual install script could deliver altered files. Plugin install is the default path; `curl ... | bash` is the legacy/manual path, so signature verification of release artifacts remains a defence-in-depth concern.

   **Mitigation status:** SHA-256 manifest tooling shipped in v2.0.0; install script verification is tracked for v2.3. Until install scripts verify manifests, users may install by cloning the tag explicitly and inspecting the diff against the previous release.

3. **Local privilege escalation against stored credentials.** The OAuth token at `~/.config/claude-seo/oauth-token.json` is the most sensitive on-disk artifact.

   **Mitigation:** v2 forces `0o600` on every write (`os.open` + `os.fchmod`) and remediates legacy `0o644` files in place on first load. Tokens never contain the OAuth `client_secret` — only the access/refresh pair plus expiry metadata.

## Known residual risks

- **Playwright + Chromium DNS rebinding.** Chromium does its own DNS resolution inside the renderer process. claude-seo's Python-layer DNS pin (`url_safety._pin_dns`) cannot reach it. The Playwright `route()` handler re-validates every subresource host (`make_safe_playwright_route_handler`), which closes the common case, but a true rebinding attacker can still race Chromium's resolver after our pre-flight returns. Mitigation: do not point `/seo` skills at untrusted sites with high-frequency redirects.
- **IPv6-only audit targets.** The strict validator queries `family=AF_INET` for the initial resolution. Hosts with AAAA records only will surface as "DNS resolution failed". This is **fail-closed** by design — we'd rather refuse than connect to an unvalidated IPv6 endpoint. Tracked for a future patch (full dual-stack pinning, similar to the Playwright handler which already uses `AF_UNSPEC`).
- **Windows file permissions.** `os.fchmod(fd, 0o600)` is a no-op on Windows for non-ACL filesystems. Users on Windows should rely on per-user directory ACLs instead of POSIX mode bits.

## Security-relevant code paths

If you are auditing, these are the high-leverage files:

| File | Purpose |
|---|---|
| `scripts/url_safety.py` | SSRF / DNS-rebinding canonical module. |
| `scripts/render_page.py` | Shared headless renderer (Playwright + trafilatura). |
| `scripts/fetch_page.py` | Raw-HTTP fetcher built on `url_safety.safe_requests_session`. |
| `scripts/capture_screenshot.py` | Playwright screenshot capture with safe route handler. |
| `scripts/google_auth.py` | OAuth token lifecycle, `chmod 0o600` writes. |
| `scripts/backlinks_auth.py` | Backlink-API credential loading; SSRF guard via `url_safety`. |
| `tests/test_url_safety.py` | 91-case regression battery covering every bypass class. |

## What this policy does **not** cover

- Bugs that require attacker control of the user's machine (any local attacker is already game over).
- Vulnerabilities in upstream dependencies — please report those to their respective maintainers. We track CVEs in `requirements.txt` and bump pins under the `deps:` Dependabot stream.
- Quality-of-output issues (SEO recommendations, schema errors, etc.) — those are bugs, not security issues.

## Security-relevant practices

- No credentials or API keys are committed to this repository. `.gitignore` blocks every known credential filename pattern.
- Install scripts write only to user-level directories under `~/.claude/` and `~/.config/claude-seo/`.
- Python dependencies install into an isolated virtual environment at `~/.claude/skills/seo/.venv/`.
- Every new fetcher must route through `scripts/url_safety.py` — there is no exception for "trusted" URLs.
