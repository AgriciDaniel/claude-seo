# Public + private repo workflow

claude-seo is mirrored across two GitHub remotes. This document is the
canonical reference for how work flows between them.

## Topology

```
                    LOCAL CHECKOUT
                    (single source of truth)
                       │
        ┌──────────────┼──────────────┐
        │                             │
        ▼                             ▼
  origin (public)              aimh (private)
  AgriciDaniel/claude-seo      AI-Marketing-Hub/claude-seo
  - Release destination        - Daily development
  - main = released history    - main = synced with public
  - Tags = release history     - v2 = active development
  - Users discover here        - Dependabot + CI run here
```

Both remotes share git history because they were initialized from the
same local repository. Neither is a GitHub fork of the other.

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

## Promoting a release to public

When `v2` (or whatever branch holds the next release) is ready to go public:

1. **Locally**: merge into main and tag.
   ```bash
   git checkout main
   git merge --ff-only v2          # fast-forward only — no merge commits
   git tag -a v2.0.1 -m "release: v2.0.1"
   ```

2. **Push to private first** (private should never lag public).
   ```bash
   git push aimh main
   git push aimh v2.0.1
   ```

3. **Push to public** in tag-before-merge order (avoids the curl|bash
   outage window where users pull a tag that doesn't yet point at code
   on main).
   ```bash
   git push origin v2.0.1          # tag first
   git push origin main            # then branch
   ```

4. **Create the GitHub release** on the public repo only.
   ```bash
   gh release create v2.0.1 \
     --repo AgriciDaniel/claude-seo \
     --notes-from-tag \
     --verify-tag
   ```

5. **Publish the release blog post**.
   ```
   /release-blog
   ```

## Verification commands

```bash
# Confirm both remotes are wired up
git remote -v

# Confirm both remotes' main heads.
# NOTE: origin/main is aimh/main PLUS one public-branding commit (see below),
# so the SHAs intentionally differ by exactly that commit. Do NOT force-sync them.
git ls-remote --heads aimh main
git ls-remote --heads origin main

# List tags on each (private will lead during pre-release work)
git ls-remote --tags aimh | grep -v '\^{}' | awk '{print $2}'
git ls-remote --tags origin | grep -v '\^{}' | awk '{print $2}'

# Confirm private has a v2 branch ahead of release
git fetch aimh
git log --oneline aimh/main..aimh/v2
```

## Public-branding divergence (the one intentional difference)

Since v2.0.0 the two repos are **not** byte-identical. They differ by exactly
one file on one commit:

| File | `aimh` (private) | `origin` (public) |
|---|---|---|
| `.claude-plugin/marketplace.json` `name` | `ai-marketing-hub-claude-seo` | `agricidaniel-claude-seo` |
| `.claude-plugin/marketplace.json` `owner.name` | `AI Marketing Hub` | `AgriciDaniel` |

Everything else (including `README.md`) is shared and public-first: the
install block defaults to `AgriciDaniel/claude-seo`, with a Pro swap-note that
names the private slug. This keeps the public repo free of `ai-marketing-hub`
slugs while keeping the README a single shared file.

**How the divergence is maintained.** The public-only branding lives as the
tip commit of `origin/main`, carried on a local `public-main` branch:

```bash
# public-main = main + one commit that rebrands marketplace.json
git checkout main && git merge --ff-only v2     # shared canonical
git checkout public-main && git rebase main      # replay branding onto new base
git push origin public-main:main                 # public gets canonical + branding
git push aimh  main                              # private gets canonical only
```

So `origin/main` = `aimh/main` + 1 commit, by design. The release tag points at
each repo's own HEAD (`origin` tag includes branding; `aimh` tag does not).

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
| Pushing a tag to `origin` before its commit reaches `origin/main` | Always tag-before-merge: push tag first, then branch |
| `git push --tags` without specifying remote | Be explicit: `git push aimh --tags` or `git push origin v2.0.1` |
| Force-pushing to either remote | Don't, except with explicit per-operation authorization |
| Letting `aimh/main` lag behind `origin/main` | Always push to `aimh` first, then `origin` on release |
| Confusing `aimh/v2` with `origin/v2` | `origin` should never have an unreleased `v2` branch |

## State for the v2.2.3 public release (2026-07-20)

- v2.2.3 is the **current public release**. Latest tag on both remotes: `v2.2.3`.
- `aimh/main` = shared canonical (public-first README, private marketplace name).
- `origin/main` = `aimh/main` + the public-branding commit (public marketplace name).
- `v2.2.3` tag points at each repo's own HEAD: `origin`'s tag includes the
  branding commit, `aimh`'s does not (see "Public-branding divergence" above).
- `aimh/v2` tracks the shared canonical for ongoing v2.x work.

## Email-privacy caveat (one-time)

Two very old tags (`v1.2.0`, `v1.4.0`) could not be pushed to the
private repo because the underlying commits use a private email address
that GitHub now blocks. These tags remain available on `origin` only.
Not a regression — those releases shipped on public and are reachable
there.
