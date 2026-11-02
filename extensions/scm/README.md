# SEO Content Machine Extension for Claude SEO

Writes a whole `/seo cluster` plan, or any page list, as researched and reviewed drafts with [SEO Content Machine](https://seocontentmachine.com/?utm_source=claude-seo&utm_medium=extension&utm_campaign=claude-seo&utm_content=readme) (SCM), a desktop SEO app. Claude SEO plans the cluster; SCM writes every page in it, with resume, so a cluster of 50 pages does not fill Claude's context.

## How SCM writes each page

Each page gets its own page agent inside SCM, run on the AI service the user set up there (a Claude Code or Codex subscription, an API key for OpenAI, Claude, Gemini, DeepSeek, OpenRouter and others, or a local model in LM Studio). The agent follows a page skill for the page type and works through three sub-agents:

1. **Research.** Builds a SERP model of the page's search: every first-page result in rank order, then what they cover and miss. It reads each fact at the source that owns it, and lists the facts no source publishes as gaps.
2. **Writing.** Writes the page from the SERP model and the facts, in the form the page skill gives.
3. **Review.** Opens the pages behind each claim and link, marks each fail as blocking or minor, and scores the page out of 10 on Help, Specifics, Honest, Expertise and Focus. The writer fixes and the reviewer rescores, for up to 4 rounds, until no blocking fail is left and every score is 8 or more.

Facts about the business come only from the brief and the page's notes, which the extension fills from the cluster plan. When a fix needs a fact only the business knows, the agent leaves the question in the page's notes instead of guessing.

Drafts land in an SEO Workspace in the app, with the cluster as its site plan: the pillar at the top and every spoke under it. The user reviews and publishes them there.

## Prerequisites

- [Claude SEO](https://github.com/AgriciDaniel/claude-seo) installed
- Node.js 18+
- SEO Content Machine running on the same machine (Windows, Mac or Linux). It is a paid app with a [14-day free trial](https://seocontentmachine.com/members/signup/trial?utm_source=claude-seo&utm_medium=extension&utm_campaign=claude-seo&utm_content=readme_trial), no card needed.

## Installation

### macOS / Linux

```bash
./extensions/scm/install.sh
```

### Windows (PowerShell)

```powershell
.\extensions\scm\install.ps1
```

No API key is asked for. The installer adds the `seo-scm` skill and the `scm` MCP server. If an `scm` server is already set up, from the SCM Claude Code plugin or `claude mcp add`, it is kept.

## Commands

| Command | Purpose |
|---------|---------|
| `/seo scm execute` | Write every post in `cluster-plan.json` as an SCM draft |
| `/seo scm pages <file or list>` | Write a plain list of page topics, one per line |
| `/seo scm status` | Show the run's progress and export finished drafts |

## Integration with Claude SEO

- **`/seo cluster plan`**: plan the cluster, then run `/seo scm execute` to write all of it. Cluster templates map to SCM page types (how-to to Topic How To, comparison to Topic Comparison and so on), and the plan's spoke-to-spoke links go into the site plan.
- **`/seo cluster` scorecard**: `/seo scm status` exports each finished draft to `scm-drafts/` and marks the post `written` in `cluster-plan.json`.
- **`/seo programmatic`**: `/seo scm pages` writes a page list in batches of 50 to 100, as the programmatic quality gates advise.

## Cost

The extension is free. SCM is a paid desktop app with a 14-day free trial. Pages are written on the user's own AI service in SCM, and a page can take several hundred thousand tokens: a test page on Claude Opus at medium effort used about 540k, plus cached reads. The skill says so before a batch starts.

## What it runs and sends

The MCP server is SCM's stdio bridge, the npm package [seo-content-machine-mcp](https://www.npmjs.com/package/seo-content-machine-mcp), pinned to a version. It relays Claude Code's messages to SCM's API on the same machine, `http://localhost:8008/mcp` by default, and sends nothing anywhere else. The research and writing run inside SCM on the user's machine.

## Troubleshooting

**No SCM tools in Claude Code?**
- Open SEO Content Machine. The tools appear within a few seconds of SCM starting.
- Check: `cat ~/.claude.json | python3 -m json.tool | grep -A3 '"scm"'`
- Manual config: See [SCM-SETUP.md](docs/SCM-SETUP.md)

**"Cannot reach SCM"?**
- SCM is closed, or its API is on another port. Set `SCM_API_URL` in the server's `env`.

## Uninstall

```bash
./extensions/scm/uninstall.sh      # macOS/Linux
.\extensions\scm\uninstall.ps1     # Windows
```

## Links

- [SEO Content Machine](https://seocontentmachine.com/?utm_source=claude-seo&utm_medium=extension&utm_campaign=claude-seo&utm_content=readme_links)
- [SCM MCP server on npm](https://www.npmjs.com/package/seo-content-machine-mcp)
- [Claude SEO](https://github.com/AgriciDaniel/claude-seo)
