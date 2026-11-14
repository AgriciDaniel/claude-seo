# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly. Do **not** open a public issue.

1. Open a private [GitHub Security Advisory](https://github.com/AgriciDaniel/claude-seo/security/advisories/new) on this repository. Private vulnerability reporting is enabled, so the "Report a vulnerability" button on the Security tab opens the same form.
2. If the advisory form is unavailable to you, open a public issue titled "Security contact request" with no technical detail. The maintainer will reply with a private channel.
3. Encrypt sensitive disclosures if you can. Request the maintainer's PGP key in the advisory thread; the fingerprint is shared there on first request and rotated yearly.

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

   **Mitigation:** `scripts/url_safety.py` is the canonical pre-flight + DNS-pinned fetch layer. Every script that fetches a user-supplied or page-derived URL validates through it. Calls to fixed vendor API hosts (Google, Bing, Moz, Common Crawl, GitHub, DataForSEO) go to those hosts directly. See `tests/test_url_safety.py` for the regression suite covering each bypass class.

   Browser fetches (`render_page.py`, `capture_screenshot.py`, `analyze_visual.py`) launch Chromium only through `browser_proxy.guarded_chromium`. Every Chromium connection, including each redirect hop, subresource, WebSocket and loopback address, is forced through a local proxy that validates the destination with the same policy and connects only to an address that passed it (when a host has several, each validated address is tried in turn, without resolving again). The proxy requires a random per-run credential that only that browser is given. QUIC and non-proxied WebRTC UDP are disabled. A render that ends on a blank page, a browser error page or a non-public address is reported as an error, never as the audited page. `unlighthouse_run.py` gives Chrome the same proxy and preloads `unlighthouse_http_proxy.cjs` so the Unlighthouse CLI's own Node requests (site check, robots.txt, sitemaps) go through it too. See `tests/test_browser_proxy.py`.

   Chromium is launched with its sandbox wherever the host can start it, so a renderer exploit in a hostile page is contained by the browser sandbox there. Where the sandbox cannot start (Ubuntu 23.10 and later, whose AppArmor policy blocks unprivileged user namespaces; GitHub's Ubuntu runners; most Docker images; root) the browser is launched once more without it, behind the same egress guard. That decision is made once, on the launch error, before any page is loaded; nothing a page does later can trigger it. Every unsandboxed run prints a warning on stderr with the reason, and the JSON results of the three scripts carry `sandbox: false`. `CLAUDE_SEO_CHROMIUM_REQUIRE_SANDBOX=1` is strict mode: no fallback, the launch fails with an error instead. `CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1` skips the sandbox attempt; with both set, strict mode wins and the launch fails.

2. **Tampered install.** A modified plugin install, GitHub release, or manual install script could deliver altered files. Plugin install is the default path; `curl ... | bash` is the legacy/manual path, so signature verification of release artifacts remains a defence-in-depth concern.

   **Mitigation status:** SHA-256 manifest tooling (`scripts/release_sign.py`, `scripts/verify_release.py`) shipped in v2.0.0, but the install scripts do not verify a manifest yet and releases do not attach one. Installer verification is planned for a later release; it is not in v2.6.0. Until then, install by cloning the release tag explicitly (`git clone --branch vX.Y.Z`), check the tag signature, and inspect the diff against the previous release. Release tags are SSH-signed. To verify one locally, put the maintainer's signing key from `https://api.github.com/users/AgriciDaniel/ssh_signing_keys` in an allowed-signers file as `223140489+AgriciDaniel@users.noreply.github.com namespaces="git" <key>`, then run `git -c gpg.ssh.allowedSignersFile=<file> tag -v vX.Y.Z` and look for `Good "git" signature`.

3. **Local privilege escalation against stored credentials.** The OAuth token at `~/.config/claude-seo/oauth-token.json` is the most sensitive on-disk artifact.

   **Mitigation:** v2 forces `0o600` on every write (`os.open` + `os.fchmod`) and remediates legacy `0o644` files in place on first load. Tokens never contain the OAuth `client_secret`, only the access/refresh pair plus expiry metadata.

## Known residual risks

- **Limits of the browser egress guard.** The guard covers everything Chromium sends through its proxy settings: HTTP, HTTPS and WebSocket connections, with redirects checked at connect time. It relies on Chromium honouring `--proxy-server` and `--proxy-bypass-list=<-loopback>`; the Playwright `route()` handler (`make_safe_playwright_route_handler`) and the blocked service workers and WebSockets stay in place as a second layer. The Unlighthouse preload covers Node's `http` and `https` modules only; Unlighthouse's version check uses `fetch` and goes to GitHub directly. The guard listens on a random loopback port for the length of one run and forwards to public addresses only. For the Playwright scripts it requires a random per-run credential (handed to Chromium through Playwright, never on a command line) and answers anything else with 407. The Unlighthouse guard has no credential, because Chrome started with `--proxy-server` cannot authenticate to a proxy: while an Unlighthouse run lasts, any local process can use that guard to reach public hosts, and behind an authenticated operator proxy its requests carry the operator's proxy credential. Do not run Unlighthouse on a shared machine you do not trust. A plain-HTTP response is relayed with the origin's own framing and the browser connection is reset if the origin fails mid-response; a response head over 256 KiB or 1,000 header lines is answered with a 502.
- **HTTP proxies weaken DNS pinning.** Behind a configured HTTP proxy (`HTTPS_PROXY` and friends) the proxy resolves each host itself, so the pin degrades to validation: `validate_url_strict` for the first URL, and the same strict check on every redirect hop before it is sent through the proxy (a refused hop raises an error that is both `URLSafetyError` and a `requests` `ConnectionError`). A host that resolves differently for the proxy than for this machine is outside what that check can see. The proxy host itself is exempted from the pinned scope only after passing the same hostname blocklist and `is_safe_ip` policy as an audit target, so a proxy on loopback, RFC 1918, RFC 6598, link-local, or a metadata address is refused rather than exempted. The browser guard chains to the same proxy under the same rules; it supports `http://` proxies only, and a `socks` or `https://` proxy URL, or a refused proxy, fails the browser run with an error instead of connecting direct.
- **Running without the Chromium sandbox.** On a host that cannot start the sandbox (Ubuntu 23.10 and later by default, most containers, root) the browser runs without it by default, with a warning, and so it does with `CLAUDE_SEO_CHROMIUM_NO_SANDBOX=1`. A browser exploit served by an audited page then runs with the user's privileges (as root when claude-seo runs as root). The egress guard does not help against that. To rule it out, enable the sandbox on the host (see `docs/TROUBLESHOOTING.md`) or set `CLAUDE_SEO_CHROMIUM_REQUIRE_SANDBOX=1`, which fails the launch instead of rendering unsandboxed.
- **IPv6 audit targets.** The strict validator resolves both address families and refuses a host if any A or AAAA record is non-public. On the raw-HTTP path the pin is IPv4 when the host has an A record and IPv6 otherwise, with no fallback between families. The browser egress guard tries every validated address of the host, IPv4 first, under one 10 second connect budget. NAT64 (64:ff9b::/96, 64:ff9b:1::/48), 6to4, Teredo, site-local, documentation, ORCHID and zone-scoped addresses are refused. One exception: on a DNS64 network, a synthesized AAAA record under 64:ff9b::/96 is ignored when the host also has an A record, because the pin is then IPv4 and that address is never dialled (the browser guard does not fall back to it either, so an IPv4-only site stays unreachable for the browser on an IPv6-only DNS64 network). A host with no A record gets no such pass, and redirect targets and browser subresources still refuse the prefix.
- **Windows file permissions.** `os.fchmod(fd, 0o600)` is a no-op on Windows for non-ACL filesystems. Users on Windows should rely on per-user directory ACLs instead of POSIX mode bits. `scripts/backlinks_auth.py` additionally makes a best-effort `icacls <path> /inheritance:r /grant:r "%USERNAME%:F"` call after every write to (and load-time remediation of) `~/.config/claude-seo/backlinks-api.json`, restricting it to the current user on NTFS. This is best-effort only: a failure (missing `icacls`, a non-NTFS volume, a restricted shell) is logged as a warning and does not block the credential read or write, so on a failure the file's effective protection on Windows falls back to whatever the containing directory's ACLs already provide.

- **RFC 6598 (100.64.0.0/10) is refused by default.** Cloud providers serve instance metadata in this range, so `url_safety` treats it like RFC 1918. Tailscale also allocates from it, so a staging site reached over Tailscale is refused under the default policy. The escape hatch is `CLAUDE_SEO_LOCAL_TARGETS`, a comma-separated allowlist of `host` or `host:port` entries (for example `localhost:3000,127.0.0.1:8080,100.101.102.103`, the last being a Tailscale address). Its scope is deliberately narrow:
  - It is consulted **only** for the first, top-level URL passed to `validate_url` / `validate_url_strict`. Redirect targets, embedded subresources, and every request the browser egress guard or the Playwright route handler sees stay fail-closed, so a page served from an allowlisted dev server still cannot pull anything else off the local network. A `host:port` entry holds for the whole request: a redirect to another port on that same host is followed only when the allowlist also names that port. Rendering an allowlisted host through Playwright is therefore not supported; the raw-HTTP path is.
  - A host must be named exactly. There is no range, wildcard, or "allow private" mode, `host:port` matches that port only, and a bare `host` matches any port on that host.
  - Cloud metadata endpoints are refused even when listed, by name (`metadata.google.internal` and its siblings) and by address (169.254.169.254, `fd00:ec2::254`, and Alibaba's 100.100.100.200, which sits inside the Tailscale range). Link-local, multicast, unspecified, and reserved addresses are never allowlistable.
  - `is_safe_ip` is unchanged and reads no environment, so every fail-closed path downstream of the first connection is unaffected.
  - Unset, claude-seo behaves exactly as it did before the flag existed.

## Security-relevant code paths

If you are auditing, these are the high-leverage files:

| File | Purpose |
|---|---|
| `scripts/url_safety.py` | SSRF / DNS-rebinding canonical module. |
| `scripts/browser_proxy.py` | Browser egress guard (local validating proxy) and the one sandboxed Chromium launch. |
| `scripts/unlighthouse_http_proxy.cjs` | Node preload that sends the Unlighthouse CLI's requests through the egress guard. |
| `scripts/render_page.py` | Shared headless renderer (Playwright + trafilatura). |
| `scripts/fetch_page.py` | Raw-HTTP fetcher built on `url_safety.safe_requests_session`. |
| `scripts/capture_screenshot.py` | Playwright screenshot capture behind the egress guard. |
| `scripts/google_auth.py` | OAuth token lifecycle, `chmod 0o600` writes. |
| `scripts/backlinks_auth.py` | Backlink-API credential loading; SSRF guard via `url_safety`. |
| `tests/test_url_safety.py` | Regression battery covering every bypass class. |
| `tests/test_browser_proxy.py` | Egress guard, sandbox launch and page-check regressions. |

## What this policy does **not** cover

- Bugs that require attacker control of the user's machine (any local attacker is already game over).
- Vulnerabilities in upstream dependencies. Please report those to their respective maintainers. We track CVEs in `requirements.txt` and bump pins under the `deps:` Dependabot stream.
- Quality-of-output issues (SEO recommendations, schema errors, etc.). Those are bugs, not security issues.

## Security-relevant practices

- No credentials or API keys are committed to this repository. `.gitignore` blocks every known credential filename pattern.
- Install scripts write only to user-level directories under `~/.claude/` and `~/.config/claude-seo/`.
- Python dependencies install into an isolated virtual environment. Plugin installs use persistent `CLAUDE_PLUGIN_DATA`; manual installs use `~/.claude/skills/seo/.venv/`. The runtime never falls back to global or user package installation.
- Every new fetcher of a user-supplied or page-derived URL must route through `scripts/url_safety.py`. There is no exception for "trusted" URLs.
