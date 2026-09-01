# Public + private repo workflow

claude-seo is mirrored across two GitHub remotes. This document is the
canonical reference for how work flows between them.

Release evidence: [v2.2.5 final verification](FINAL-VERIFICATION-v2.2.5-2026-08-26.md).

## Topology

```
                 REVIEWED RELEASE WORK
                (isolated clean worktree)
                       │
        ┌──────────────┼──────────────┐
        │                             │
        ▼                             ▼
  origin (public)              aimh (private)
  AgriciDaniel/claude-seo      AI-Marketing-Hub/claude-seo
  - Release destination        - Daily development
  - main = released history    - main = reviewed private release history
  - Tags = release history     - v2 = active development
  - Users discover here        - Dependabot + CI run here
```

Both remotes share historical ancestry because they were initialized from the
same local repository. Reviewed back-ports, private-only research, and public
branding mean their current release commits can have different SHAs. Neither
repository is a GitHub fork of the other.

## Day-to-day development

```bash
# Work on the active development branch
git checkout v2

# ...make changes, run tests...
git add <files>
git commit -m "feat: ..."

# Push to the PRIVATE remote (default for in-progress work)
git push aimh v2
```

The private repo runs Dependabot, GitHub Actions CI, and any pre-release
test gates. No need to touch the public remote for routine work.

## Promoting reviewed release changes

1. Start from an isolated clean worktree for the target repository.
2. Fast-forward only when ancestry proves it is safe. When release lines have
   diverged, cherry-pick the exact reviewed commits with `-x`.
3. Resolve only documented repository-specific differences, then run the full
   test, portability, consistency, security, and plugin-validation gates.
4. Compare the final private/public trees and explain every remaining path.
5. Create an annotated tag on each repository's reviewed release commit.
6. Push private changes first. Push each tag before moving its repository's
   `main`, or push the tag and branch atomically, so pinned installers resolve.
7. Create the GitHub release on the public repository only.
   ```bash
   gh release create v2.0.1 \
     --repo AgriciDaniel/claude-seo \
     --notes-from-tag \
     --verify-tag
   ```

8. Publish the release blog post.
   ```
   /release-blog
   ```

## Verification commands

Run these from a maintainer checkout with authenticated access to the private
repository. Add the private remote once if it is absent:

```bash
git remote get-url aimh >/dev/null 2>&1 || \
  git remote add aimh https://github.com/AI-Marketing-Hub/claude-seo.git
```

```bash
# Confirm both remotes are wired up
git remote -v

# Confirm both remotes' main heads, then compare their documented divergence.
# Equal SHAs are not expected after repository-specific back-ports.
git ls-remote --heads aimh main
git ls-remote --heads origin main

# List tags on each (private will lead during pre-release work)
git ls-remote --tags aimh | grep -v '\^{}' | awk '{print $2}'
git ls-remote --tags origin | grep -v '\^{}' | awk '{print $2}'

# Confirm private has a v2 branch ahead of release
git fetch aimh
git log --oneline aimh/main..aimh/v2
```

## Reviewed public/private divergence

The repositories are intentionally not byte-identical:

| File | `aimh` (private) | `origin` (public) |
|---|---|---|
| `.claude-plugin/marketplace.json` `name` | `ai-marketing-hub-claude-seo` | `agricidaniel-claude-seo` |
| `.claude-plugin/marketplace.json` `owner.name` | `AI Marketing Hub` | `AgriciDaniel` |

The private repository can also retain private-only `research/` reports, Pro
documentation, and links to those materials. Workflow state is repository
specific. Any other difference must be reviewed and explained before release.
Never force-sync the repositories to make their SHAs or trees identical.

## Why two repos?

- The **public** repo is the user-facing artifact. Everything visible
  there is releasable, documented, and supported.
- The **private** repo is the workshop. Work-in-progress branches,
  experimental phases (J, K, future phases), pre-release security audits,
  and unfinished thoughts live here. Dependabot churn and CI noise stay
  off the public timeline.

Public is for users. Private is for the work that becomes users' next
upgrade.

## Common pitfalls

| Pitfall | Avoid by |
|---|---|
| Moving `origin/main` before the release tag exists | Push the tag first, then `main`, or push both atomically |
| `git push --tags` without specifying remote | Be explicit: `git push aimh --tags` or `git push origin v2.0.1` |
| Force-pushing to either remote | Don't, except with explicit per-operation authorization |
| Assuming `aimh/main` and `origin/main` should have equal SHAs | Compare and explain the reviewed tree differences; never force-sync |
| Confusing `aimh/v2` with `origin/v2` | `origin` should never have an unreleased `v2` branch |

## State after v2.2.5 maintenance (2026-08-26)

- The public v2.2.5 tag is `2384fdd`; reviewed post-release maintenance runs
  through `3344796` before the documentation update that records this state.
- The private v2.2.5 tag is `d76a8dd`; reviewed post-release maintenance runs
  through `9f5dd20` before any matching documentation update.
- Each repository has a repository-specific annotated `v2.2.5` tag.
- Private `main` and `v2` include reviewed maintenance through `9f5dd20`.
- Public `main` includes reviewed maintenance through `3344796` and has no
  public `v2` branch.
- The private sync preserves private-only research and the
  `ai-marketing-hub-claude-seo` marketplace identity.

## Email-privacy caveat (one-time)

Two very old tags (`v1.2.0`, `v1.4.0`) could not be pushed to the
private repo because the underlying commits use a private email address
that GitHub now blocks. These tags remain available on `origin` only.
Not a regression — those releases shipped on public and are reachable
there.
