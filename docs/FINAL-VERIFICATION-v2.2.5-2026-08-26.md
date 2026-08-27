# Claude SEO v2.2.5 final verification

Date: 2026-08-26

## Verdict

The public release, reviewed private sync, and production website are functional
and verified. The authorized v2.2.5 cleanup and post-release maintenance set is
complete. The score remains below 10/10 because private hosted CI is blocked by
organization billing, the Windows installer proof used Python 3.14.7 rather
than the minimum supported Python 3.10, and one public post-release commit
retains malformed body metadata.

## Scorecard

| Area | Score | Evidence-led status |
|---|---:|---|
| Public v2.2.5 behavior | 9.7/10 | 439 tests and post-merge CI passed |
| Public current main | 9.8/10 | 441 tests, Ruff clean, cross-platform and installer CI green |
| Public release governance | 9.8/10 | Release metadata is corrected and the tag signature is verified |
| Private mirror | 9.7/10 | Reviewed maintenance sync is merged; private-only content is preserved |
| Private hosted CI | 4.0/10 | Jobs cannot start until organization billing is repaired |
| Live website | 9.8/10 | Production content and deterministic gates passed |
| Website source durability | 10/10 | Exact deployed source snapshot is committed and pushed |
| Authorized closure set | 10/10 | All 10 fixed issues and 5 superseded PRs are closed |
| Overall | **9.1/10** | Simple mean of the eight scored areas above |

## Verified facts

### Public repository

- The annotated `v2.2.5` tag and GitHub Release remain frozen at
  `2384fdd9429696021d143006a722c7cf1aa76d43`.
- Public `main` includes reviewed post-release maintenance through
  `3344796aafe09b061685c3ec50364704fe6f9cad`.
- Exact-tag rerun: 439 tests passed.
- Portability: 33 skills, 0 errors, 0 warnings.
- Consistency: 380 files, 0 errors, 0 warnings.
- The exact release tree retains 126 historical Ruff findings. Current public
  `main` is repo-wide Ruff clean without moving or rewriting the release tag.
- `pip-audit`, strict plugin validation, Bash syntax, secret scan, and diff
  checks passed.
- Native Windows and macOS portability jobs passed on Python 3.10.
- A Windows Server 2025 PowerShell 7 run installed the public v2.2.5 tag,
  verified runtime health and bundled Google update data, uninstalled it, and
  verified complete cleanup. The installer selected Python 3.14.7 through
  `py -3`, so this is not minimum-Python installer proof.
- The Windows smoke exposed an inaccurate uninstaller summary counter. The
  reporting-only defect was fixed and verified for full, partial, and empty
  install states; removal targets and deletion behavior were unchanged.
- GitHub verifies the annotated tag SSH signature as valid. The tag API records
  `verified: true` with verification time 2026-08-26T11:44:38Z.

### Private repository

- The annotated private `v2.2.5` tag remains frozen at
  `d76a8ddf56eda305e0281db795fedeba5e534232`.
- Private `main` and `v2` include reviewed post-release maintenance through
  `9f5dd208895362b4bec3a7b06d34d707d617b6a5`.
- The original private checkout remains at `01ca5c5` with all 12 user-modified
  skill files preserved.
- Private marketplace identity, AI Marketing Hub ownership, Pro documentation,
  and six private research reports remain intact.
- PR #20 is merged.
- PR #21 is merged under the explicit maintainer waiver after 441 tests passed,
  all four patch IDs matched the reviewed public source commits, and an
  independent review confirmed that private-only content was unchanged.
- GitHub jobs executed zero steps because organization billing or spending
  limits prevented startup. This is not a test failure, but hosted verification
  is unavailable.
- Actions are enabled, workflows are active, and all actions are allowed. The
  organization has a $5 hard-stop Actions budget with only $0.218 net August
  usage. GitHub does not expose payment-card status through the available API,
  so the exact payment-versus-limit condition requires interactive inspection.

### Production website

- The website presents v2.2.5 consistently.
- 28 website tests passed.
- Site quality: 56 pages, 0 hard failures, 0 review items.
- 208 JSON-LD blocks parsed.
- Sitemap: 55 unique URLs matching 55 canonical URLs.
- Network-aware publishing validation passed.
- Independent audit matched 61 of 61 production pages, crawler files, and assets
  byte-for-byte before the final count correction.
- Security headers include CSP, HSTS, frame denial, MIME protection, referrer
  policy, and permissions policy.
- The dated site snapshot of 15,113 stars and 2,215 forks was truthful when
  deployed, and its 15.1K display was correct at that time.
- Final star refresh: GitHub reported 15,232 stars and 2,240 forks. Production
  now displays v2.2.5 and the correct one-decimal 15.2K value.
- The current deployed source is committed to the private website repository at
  `f77dc34a96237afe8699edb48f3c03c259f5d82e`.

## Refuted or corrected claims

- The consistency count is 380 files, not 379. The website release article,
  generated crawler corpus, and public GitHub Release now agree.
- Public and private release commits are not separated by one branding commit.
  They are separately reviewed histories with documented content differences.
- The website repository does have a private origin:
  `AgriciDaniel/claude-seo-website`.
- Repository-wide Ruff did not pass on the frozen release tag. It passes on
  current public `main` after a separately reviewed mechanical cleanup.
- Production deployment and source-control durability are complete.

## Fixes completed in this verification pass

- Fast-forwarded the public checkout to public v2.2.5 while preserving all
  untracked audit artifacts.
- Corrected public/private workflow documentation for reviewed divergent SHAs,
  repository-specific tags, atomic or tag-first release ordering, and no
  force-sync rule.
- Corrected website governance docs to name the private origin and record the
  uncommitted production-source risk.
- Corrected website verification copy and FAQ parity from 379 to 380 files.
- Regenerated `llms-full.txt` and reran website and public documentation gates.
- Committed and pushed all 77 production website source paths to the private
  website repository after a zero-finding candidate secret scan.
- Corrected the published v2.2.5 GitHub Release count from 379 to 380.
- Closed 10 issues verified fixed by #261 and v2.2.5: #256, #250, #246, #210,
  #208, #205, #188, #187, #186, and #180.
- Closed five PRs superseded by #261 and v2.2.5: #257, #248, #242, #241, and
  #240.
- The closure set was intentionally narrow. Seven issues and 34 other public
  PRs remain open after this documentation PR is excluded; they were not
  represented as resolved by the v2.2.5 work.
- Merged PR #185 after native Windows and macOS portability checks passed.
- Merged PR #264 after 126 Ruff findings were reduced to zero, 439 tests passed,
  and an adversarial review caught and corrected stale-base and commit-message
  defects before merge.
- Merged PR #265 after the v2.2.5 PowerShell installer, runtime, bundled data,
  uninstall, and filesystem cleanup all passed on hosted Windows.
- Merged PR #266 after 441 tests and seven exact-head checks passed. Its first
  Windows attempt correctly failed in the new test expression before product
  code executed; the assertion was repaired and the exact rerun passed.
- Merged private PR #21 and advanced private `v2` by fast-forward after exact
  patch comparison, 441 private tests, and preservation checks passed. The
  private v2.2.5 tag was not moved.
- Updated the live website from 15.1K to 15.2K after the repository crossed the
  one-decimal threshold. Six production surfaces matched local bytes after
  deployment, and the private website source commit is `f77dc34`.

## Remaining execution gaps

1. Inspect AI Marketing Hub Billing and plans interactively. Repair the payment
   state or applicable Actions spending limit, then rerun private CI and the v2
   audit. The available API does not prove which condition is blocking startup.
2. If minimum-version installer proof is required, run the Windows installer
   with only Python 3.10 discoverable. Existing proof covers native Windows on
   Python 3.14.7 plus cross-platform unit tests on Python 3.10.
3. Public post-release commit `2651be0` contains literal backslash-n sequences
   in its body from the squash merge command. Its code and hosted checks are
   valid. The private cherry-pick message was repaired, but public history was
   not rewritten to fix metadata.

No history was rewritten and no user changes were discarded. All external
closures were limited to the exact authorized and independently verified set.
