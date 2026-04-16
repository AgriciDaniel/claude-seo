# Video Script: Claude SEO v1.7.2 — What's New

**Duration:** ~5 minutes
**Tone:** Natural, conversational, like talking to a friend who knows Claude Code
**Format:** Screen recording with face cam overlay

---

## INTRO (0:00 - 0:30)

Hey everyone. So about a month ago I showed you Claude SEO — the universal SEO skill for Claude Code. Since then, the project has gone from around 2,000 stars to over 3,500, which is insane. Thank you.

But I haven't just been watching the numbers grow — I've been shipping. We went from v1.5 to v1.7.2, and in this video I'm going to walk you through the biggest updates: Google API integration, AI image generation with Banana, the extension system, and marketplace compliance.

Let's get into it.

---

## SECTION 1: Google SEO APIs (0:30 - 2:15)

*[Screen: Show terminal with Claude Code open]*

The biggest addition is direct Google API integration. Claude SEO can now pull live data from Google's own APIs — Search Console, PageSpeed Insights, CrUX, GA4, and even the Indexing API.

*[Type: `/seo google psi https://example.com`]*

So here I'm running a PageSpeed check. This isn't just lab data — it pulls real Chrome User Experience data, the actual Core Web Vitals that Google uses for ranking.

The cool part is the credential system. There are four tiers. Tier 0 — just a free API key — gives you PageSpeed and CrUX. Tier 1 adds OAuth for Search Console and the Indexing API. Tier 2 adds GA4 organic traffic data. And Tier 3 unlocks the Keyword Planner if you have a Google Ads account.

You can start with just Tier 0. One API key, completely free, and you already get live Core Web Vitals and Lighthouse scores.

*[Type: `/seo google report full`]*

And all of this data feeds into professional PDF reports. A4 format, charts, color-coded scores, table of contents — something you can actually send to a client.

*[Show generated PDF briefly]*

Now in v1.7.2, you can also export to Excel.

*[Type: `/seo google report full --format xlsx`]*

Same data, but in a spreadsheet. Queries, pages, indexation status — all in separate sheets with filters and frozen headers. Clients love spreadsheets. You can even do `--format all` and get PDF, HTML, and Excel at once.

---

## SECTION 2: Banana — AI Image Generation (2:15 - 3:15)

*[Screen: Terminal]*

The second feature I want to show is the Banana extension — AI image generation for SEO assets. This uses Google Gemini to generate images directly from Claude Code.

*[Type: `/seo image-gen og "AI-powered SEO audit tool"`]*

So I just asked it to generate an Open Graph image. Claude acts as a creative director — it builds a detailed prompt, picks the right model, generates the image, and saves it. About two cents per image.

*[Show generated image]*

You can generate OG images, blog hero graphics, product shots, infographics — six use cases out of the box.

*[Type: `/seo image-gen hero "technical SEO audit checklist"`]*

The skill also does SEO image audits — it checks your existing images for missing alt text, wrong formats, oversized files, missing schema — and then creates a generation plan for the ones you need.

This is the extension pattern in action. Claude SEO's core is free and local. Extensions like Banana, DataForSEO, and Firecrawl plug in via MCP servers when you need them. Each one has its own installer, its own uninstaller, completely self-contained.

---

## SECTION 3: The Extension System (3:15 - 4:00)

*[Screen: Show the extensions/ folder structure in editor or terminal]*

So let me quickly explain how the extension system works because this is key to how Claude SEO grows.

The core skill — 17 sub-skills, 12 subagents — works with zero API keys. You install it, you run `/seo audit`, and it does a full analysis using Claude's own intelligence.

But when you want live data — SERP rankings, backlink profiles, keyword volume — you add an extension. Right now there are three:

*[Show list]*

DataForSEO gives you 22 commands across 9 API modules — SERP analysis, keyword research, backlinks, content analysis. Firecrawl gives you full-site crawling with JavaScript rendering. And Banana gives you AI image generation via Gemini.

Each extension is one install script. It copies the skill files, configures the MCP server, and you're done. And if you don't want it anymore — one uninstall script, clean removal.

The audit orchestrator detects which extensions are installed and automatically spawns the right subagents. So the more extensions you add, the deeper your audits get.

---

## SECTION 4: Marketplace & Community (4:00 - 4:45)

*[Screen: GitHub repo]*

A few more things worth mentioning. We cleaned up the entire codebase following Anthropic's official best practices. Every skill now has its own LICENSE file. We added a privacy policy. We stripped out unsupported frontmatter fields. And we're now validated for the official Claude Code plugin marketplace.

*[Show: `claude plugin validate .` passing]*

We also got listed on the awesome-claude-skills repo — that's the one with 49,000 stars — and we cross-linked with AI Marketing Claude as a companion tool for the post-audit workflow.

The project is now at 19 sub-skills, 12 subagents, 3 extensions, and 3,500 stars. Community PRs keep coming in — we've reviewed and responded to every single one.

---

## OUTRO (4:50 - 5:10)

If you're using Claude Code for anything SEO-related, give Claude SEO a try. Install is one command — link in the description. Star the repo if you find it useful, and drop a comment if there's a feature you want to see next.

I'm thinking v1.8 might be the content strategy skill — turning audit findings into actual content plans. Let me know what you think.

See you in the next one.

---

## VIDEO DESCRIPTION (for YouTube)

```
Claude SEO v1.7.2 — Universal SEO Skill for Claude Code

What's new:
- Google SEO APIs (Search Console, PageSpeed, CrUX, GA4, Indexing API)
- PDF & Excel reports (A4 with charts, multi-sheet .xlsx)
- Banana extension (AI image generation via Gemini for OG, hero, product images)
- Extension system (DataForSEO, Firecrawl, Banana — plug in what you need)
- Official marketplace compliance (passes claude plugin validate)

Install:
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash

GitHub: https://github.com/AgriciDaniel/claude-seo
Skool: https://www.skool.com/ai-marketing-hub-pro

19 sub-skills | 12 subagents | 3 extensions | 3,500+ stars

#ClaudeCode #SEO #AI #ClaudeSEO
```

---

## THUMBNAIL TEXT IDEAS

- "Claude SEO v1.7.2"
- "Google APIs + AI Images"
- "19 Skills | 3 Extensions"
