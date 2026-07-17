# OpenCode-Native Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform claude-seo from a Claude Code plugin into a fully OpenCode-native tool by rewriting agent frontmatter, promoting skill bodies to commands, centralizing configuration, and removing Claude-specific files.

**Architecture:** Agents get OpenCode frontmatter (`mode: subagent`, `description:`). SKILL.md bodies become OpenCode command files with `$ARGUMENTS` preambles. One `opencode.jsonc` replaces all scattered Claude config. Install scripts target `~/.config/opencode/`. Python scripts stay untouched.

**Tech Stack:** YAML frontmatter, Markdown, JSONC, Bash, Python 3.10+, pytest

**Design doc:** `docs/2026-07-17-opencode-rewrite-design.md`

---

### Task 1: Remove Claude-specific files

**Files:**
- Delete: `.claude-plugin/plugin.json`
- Delete: `.claude-plugin/marketplace.json`
- Delete: `.claude-plugin/` (empty dir)
- Delete: `CLAUDE.md`
- Delete: `hooks/hooks.json`
- Delete: `hooks/run-python-hook.js`
- Delete: `hooks/validate-schema.py`
- Delete: `hooks/` (empty dir)
- Delete: `docs/MCP-INTEGRATION.md`

- [ ] **Step 1: Remove the files**

```bash
git rm -r .claude-plugin/ CLAUDE.md hooks/ docs/MCP-INTEGRATION.md
```

- [ ] **Step 2: Verify removal**

Run: `ls .claude-plugin/ CLAUDE.md hooks/ docs/MCP-INTEGRATION.md 2>&1`
Expected: "No such file or directory" for each

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove Claude Code-specific files (.claude-plugin, CLAUDE.md, hooks, MCP docs)"
```

---

### Task 2: Rewrite agent frontmatter (batch 1 of 3: 6 agents)

**Files:**
- Modify: `agents/seo-technical.md`
- Modify: `agents/seo-content.md`
- Modify: `agents/seo-schema.md`
- Modify: `agents/seo-sitemap.md`
- Modify: `agents/seo-performance.md`
- Modify: `agents/seo-visual.md`

- [ ] **Step 1: Write the agent conversion script**

The script reads each agent, rewrites frontmatter, and writes back. Every agent body stays unchanged.

```bash
mkdir -p /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode
```

```python
# /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/convert_agents_batch1.py
import re
from pathlib import Path

REPO = Path("/Users/fsundquist/Developer/private/claude-seo")
AGENT_DIR = REPO / "agents"

AGENTS = {
    "seo-technical.md": "Technical SEO specialist. Analyzes crawlability, indexability, security, URL structure, mobile optimization, Core Web Vitals, and JavaScript rendering.",
    "seo-content.md": "EEAT content quality analyst. Evaluates experience, expertise, authoritativeness, and trustworthiness signals in page content.",
    "seo-schema.md": "Schema markup expert. Detects, validates, and generates Schema.org structured data in JSON-LD format.",
    "seo-sitemap.md": "XML sitemap analysis and generation specialist. Handles sitemap discovery, validation, IndexNow submission, and structured sitemap generation.",
    "seo-performance.md": "Core Web Vitals and page performance specialist. Analyzes LCP, INP, CLS, TTFB, and FCP using PageSpeed Insights, CrUX API, and Lighthouse.",
    "seo-visual.md": "Visual SEO analyst. Captures and analyzes page screenshots, checks for layout shifts, visual hierarchy, and above-the-fold content.",
}

def convert_agent(path, description):
    text = path.read_text()
    # Match existing frontmatter block
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    if not m:
        print(f"SKIP {path.name}: no frontmatter found")
        return
    body = text[m.end():]
    new_frontmatter = f"---\nmode: subagent\ndescription: {description}\n---\n"
    if path.name == "seo-visual.md":
        new_frontmatter = f"---\nmode: subagent\ndescription: {description}\npermission:\n  external_directory: {{ \"/tmp/*\": \"allow\" }}\n---\n"
    path.write_text(new_frontmatter + body)
    print(f"OK    {path.name}")

for filename, description in AGENTS.items():
    convert_agent(AGENT_DIR / filename, description)

print("Done.")
```

- [ ] **Step 2: Run conversion script**

```bash
python3 /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/convert_agents_batch1.py
```

Expected: `OK agents/seo-technical.md` (x6), `Done.`

- [ ] **Step 3: Verify agent frontmatter has `mode: subagent` and no Claude fields**

```bash
for f in agents/seo-technical.md agents/seo-content.md agents/seo-schema.md agents/seo-sitemap.md agents/seo-performance.md agents/seo-visual.md; do
  echo "=== $f ==="
  head -6 "$f"
done
```

Expected: Each file shows `mode: subagent` and `description:` in YAML frontmatter. No `model:`, `maxTurns:`, `tools:`, or `name:`.

- [ ] **Step 4: Commit**

```bash
git add agents/seo-technical.md agents/seo-content.md agents/seo-schema.md agents/seo-sitemap.md agents/seo-performance.md agents/seo-visual.md
git commit -m "feat: convert agents batch 1/3 to OpenCode frontmatter format"
```

---

### Task 3: Rewrite agent frontmatter (batch 2 of 3: 6 agents)

**Files:**
- Modify: `agents/seo-geo.md`
- Modify: `agents/seo-local.md`
- Modify: `agents/seo-maps.md`
- Modify: `agents/seo-google.md`
- Modify: `agents/seo-backlinks.md`
- Modify: `agents/seo-cluster.md`

- [ ] **Step 1: Write and run batch 2 conversion**

```python
# /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/convert_agents_batch2.py
import re
from pathlib import Path

REPO = Path("/Users/fsundquist/Developer/private/claude-seo")
AGENT_DIR = REPO / "agents"

AGENTS = {
    "seo-geo.md": "Generative Engine Optimization analyst. Optimizes content for AI Overviews, ChatGPT, Perplexity, and other AI-powered search experiences.",
    "seo-local.md": "Local SEO specialist. Analyzes Google Business Profile, local citations, review signals, NAP consistency, and map pack visibility.",
    "seo-maps.md": "Maps intelligence analyst. Handles geo-grid rank tracking, GBP audit, local competitor analysis, and review monitoring.",
    "seo-google.md": "Google SEO APIs specialist. Works with Search Console, PageSpeed Insights, CrUX, Indexing API, and Google Analytics 4.",
    "seo-backlinks.md": "Backlink profile analyst. Evaluates backlink quality, anchor text distribution, referring domains, and toxic link detection using Moz, Bing, and Common Crawl.",
    "seo-cluster.md": "Semantic clustering and content architecture specialist. Performs SERP-based topic clustering, pillar page planning, and content gap analysis.",
}

def convert_agent(path, description):
    text = path.read_text()
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    if not m:
        print(f"SKIP {path.name}: no frontmatter found")
        return
    body = text[m.end():]
    # seo-cluster references skills/seo-cluster/references/ — update path
    if path.name == "seo-cluster.md":
        body = body.replace("skills/seo-cluster/references/", "~/.config/opencode/seo-skills/seo-cluster/references/")
    new_frontmatter = f"---\nmode: subagent\ndescription: {description}\n---\n"
    path.write_text(new_frontmatter + body)
    print(f"OK    {path.name}")

for filename, description in AGENTS.items():
    convert_agent(AGENT_DIR / filename, description)

print("Done.")
```

- [ ] **Step 2: Run conversion**

```bash
python3 /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/convert_agents_batch2.py
```

Expected: `OK agents/seo-geo.md` (x6), `Done.`

- [ ] **Step 3: Verify and commit**

```bash
git add agents/seo-geo.md agents/seo-local.md agents/seo-maps.md agents/seo-google.md agents/seo-backlinks.md agents/seo-cluster.md
git commit -m "feat: convert agents batch 2/3 to OpenCode frontmatter format"
```

---

### Task 4: Rewrite agent frontmatter (batch 3 of 3: 6 agents)

**Files:**
- Modify: `agents/seo-sxo.md`
- Modify: `agents/seo-drift.md`
- Modify: `agents/seo-ecommerce.md`
- Modify: `agents/seo-flow.md`
- Modify: `agents/seo-dataforseo.md`
- Modify: `agents/seo-image-gen.md`

- [ ] **Step 1: Write and run batch 3 conversion**

```python
# /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/convert_agents_batch3.py
import re
from pathlib import Path

REPO = Path("/Users/fsundquist/Developer/private/claude-seo")
AGENT_DIR = REPO / "agents"

AGENTS = {
    "seo-sxo.md": "Search Experience Optimization analyst. Performs SERP backwards analysis to detect page-type mismatches, derives user stories from intent signals, and scores pages from multiple persona perspectives.",
    "seo-drift.md": "SEO drift monitoring specialist. Captures baselines, compares current state, and tracks SEO metric changes over time using the drift SQLite database.",
    "seo-ecommerce.md": "E-commerce SEO specialist. Analyzes product schema, category architecture, faceted navigation, marketplace intelligence, and shopping feed optimization.",
    "seo-flow.md": "FLOW framework specialist. Executes staged Find-Leverage-Optimize-Win prompts with search-and-conversion output for evidence-led SEO strategy.",
    "seo-dataforseo.md": "DataForSEO API specialist. Executes SERP analysis, keyword research, backlink checks, and merchant data queries via the DataForSEO platform.",
    "seo-image-gen.md": "AI image generation specialist for SEO assets. Creates optimized images for blog posts, social sharing, product listings, and schema markup using AI image generation tools.",
}

def convert_agent(path, description):
    text = path.read_text()
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    if not m:
        print(f"SKIP {path.name}: no frontmatter found")
        return
    body = text[m.end():]
    # seo-sxo references skills/seo-sxo/references/ — update path
    if path.name == "seo-sxo.md":
        body = body.replace("skills/seo-sxo/references/", "~/.config/opencode/seo-skills/seo-sxo/references/")
    new_frontmatter = f"---\nmode: subagent\ndescription: {description}\n---\n"
    path.write_text(new_frontmatter + body)
    print(f"OK    {path.name}")

for filename, description in AGENTS.items():
    convert_agent(AGENT_DIR / filename, description)

print("Done.")
```

- [ ] **Step 2: Run conversion**

```bash
python3 /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/convert_agents_batch3.py
```

Expected: `OK agents/seo-sxo.md` (x6), `Done.`

- [ ] **Step 3: Verify and commit**

```bash
git add agents/seo-sxo.md agents/seo-drift.md agents/seo-ecommerce.md agents/seo-flow.md agents/seo-dataforseo.md agents/seo-image-gen.md
git commit -m "feat: convert agents batch 3/3 to OpenCode frontmatter format"
```

---

### Task 5: Create command files (batch 1 of 5: 5 commands)

**Files:**
- Create: `commands/seo-audit.md`
- Create: `commands/seo-page.md`
- Create: `commands/seo-technical.md`
- Create: `commands/seo-content.md`
- Create: `commands/seo-schema.md`

- [ ] **Step 1: Create commands directory and write the command generator script**

```bash
mkdir -p /Users/fsundquist/Developer/private/claude-seo/commands
```

```python
# /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch1.py
import re
from pathlib import Path

REPO = Path("/Users/fsundquist/Developer/private/claude-seo")
SKILLS = REPO / "skills"
CMDS = REPO / "commands"
CMDS.mkdir(exist_ok=True)

# Map skill dir -> command file + description
COMMANDS = {
    "seo-audit": {
        "file": "seo-audit.md",
        "desc": "Full website SEO audit with parallel subagent delegation across technical, content, schema, performance, visual, GEO, and more.",
        "preamble": "The user ran /seo-audit with argument: $ARGUMENTS\n\nRun a comprehensive website audit on the provided URL. Detect the business type (SaaS, e-commerce, local, publisher, agency, other) and dispatch appropriate subagents for parallel analysis.\n\n---\n\n",
    },
    "seo-page": {
        "file": "seo-page.md",
        "desc": "Deep single-page SEO analysis covering on-page elements, content quality, technical meta tags, schema, images, and performance.",
        "preamble": "The user ran /seo-page with argument: $ARGUMENTS\n\nRun a comprehensive single-page SEO analysis on the provided URL.\n\n---\n\n",
    },
    "seo-technical": {
        "file": "seo-technical.md",
        "desc": "Technical SEO audit across 9 categories: crawlability, indexability, security, URL structure, mobile, Core Web Vitals, structured data, JavaScript rendering, and IndexNow protocol.",
        "preamble": "The user ran /seo-technical with argument: $ARGUMENTS\n\nRun a technical SEO audit on the provided URL.\n\n---\n\n",
    },
    "seo-content": {
        "file": "seo-content.md",
        "desc": "EEAT content quality analysis evaluating experience, expertise, authoritativeness, and trustworthiness signals in page content.",
        "preamble": "The user ran /seo-content with argument: $ARGUMENTS\n\nRun an EEAT content quality analysis on the provided URL.\n\n---\n\n",
    },
    "seo-schema": {
        "file": "seo-schema.md",
        "desc": "Detect, validate, and generate Schema.org structured data. JSON-LD format preferred. Covers all Google-supported rich result types and AI-citation schema.",
        "preamble": "The user ran /seo-schema with argument: $ARGUMENTS\n\nRun schema markup detection, validation, and generation on the provided URL.\n\n---\n\n",
    },
}

for skill_name, config in COMMANDS.items():
    skill_md = SKILLS / skill_name / "SKILL.md"
    if not skill_md.exists():
        print(f"SKIP {skill_name}: SKILL.md not found at {skill_md}")
        continue
    text = skill_md.read_text()
    # Extract body after frontmatter
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    if not m:
        print(f"SKIP {skill_name}: no frontmatter found")
        continue
    body = text[m.end():]
    # Update reference paths in body
    body = body.replace("skills/" + skill_name + "/references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("skills/seo/references/", "~/.config/opencode/seo-skills/references/")
    body = body.replace("references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("schema/templates.json", "~/.config/opencode/seo-skills/schema/templates.json")
    # Write command file
    cmd_file = CMDS / config["file"]
    cmd_content = f"---\ndescription: {config['desc']}\nagent: general\n---\n{config['preamble']}{body.lstrip()}"
    cmd_file.write_text(cmd_content)
    print(f"OK    {config['file']}")

print("Done.")
```

- [ ] **Step 2: Run command generator**

```bash
python3 /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch1.py
```

Expected: `OK seo-audit.md` (x5), `Done.`

- [ ] **Step 3: Verify command files have correct frontmatter**

```bash
for f in commands/seo-audit.md commands/seo-page.md commands/seo-technical.md commands/seo-content.md commands/seo-schema.md; do
  echo "=== $f ==="
  head -4 "$f"
done
```

Expected: Each file starts with `---` then `description:` then `agent: general` then `---`.

- [ ] **Step 4: Commit**

```bash
git add commands/seo-audit.md commands/seo-page.md commands/seo-technical.md commands/seo-content.md commands/seo-schema.md
git commit -m "feat: add command files batch 1/5 (audit, page, technical, content, schema)"
```

---

### Task 6: Create command files (batch 2 of 5: 5 commands)

**Files:**
- Create: `commands/seo-sitemap.md`
- Create: `commands/seo-images.md`
- Create: `commands/seo-geo.md`
- Create: `commands/seo-plan.md`
- Create: `commands/seo-programmatic.md`

- [ ] **Step 1: Write and run batch 2 generator**

```python
# /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch2.py
import re
from pathlib import Path

REPO = Path("/Users/fsundquist/Developer/private/claude-seo")
SKILLS = REPO / "skills"
CMDS = REPO / "commands"

COMMANDS = {
    "seo-sitemap": {
        "file": "seo-sitemap.md",
        "desc": "XML sitemap analysis, validation, and generation. Handles sitemap discovery, IndexNow submission, and structured sitemap creation.",
        "preamble": "The user ran /seo-sitemap with argument: $ARGUMENTS\n\nAnalyze or generate XML sitemaps for the provided URL.\n\n---\n\n",
    },
    "seo-images": {
        "file": "seo-images.md",
        "desc": "Image SEO analysis covering alt text, file size, format optimization, lazy loading, dimensions, and SERP image visibility.",
        "preamble": "The user ran /seo-images with argument: $ARGUMENTS\n\nRun image SEO analysis on the provided URL.\n\n---\n\n",
    },
    "seo-geo": {
        "file": "seo-geo.md",
        "desc": "Generative Engine Optimization for AI Overviews, ChatGPT, Perplexity, and AI-powered search. Covers citation optimization, structured data for AI, and content formatting for LLM consumption.",
        "preamble": "The user ran /seo-geo with argument: $ARGUMENTS\n\nRun Generative Engine Optimization analysis on the provided URL.\n\n---\n\n",
    },
    "seo-plan": {
        "file": "seo-plan.md",
        "desc": "Strategic SEO planning for any business type. Covers keyword strategy, content architecture, technical roadmap, and competitive positioning.",
        "preamble": "The user ran /seo-plan with argument: $ARGUMENTS\n\nCreate a strategic SEO plan for the provided business type or URL.\n\n---\n\n",
    },
    "seo-programmatic": {
        "file": "seo-programmatic.md",
        "desc": "Programmatic SEO analysis and planning. Covers template design, data source identification, URL structure, and scaling strategies for programmatic content.",
        "preamble": "The user ran /seo-programmatic with argument: $ARGUMENTS\n\nRun programmatic SEO analysis and planning.\n\n---\n\n",
    },
}

for skill_name, config in COMMANDS.items():
    skill_md = SKILLS / skill_name / "SKILL.md"
    text = skill_md.read_text()
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    body = text[m.end():]
    body = body.replace("skills/" + skill_name + "/references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("skills/seo/references/", "~/.config/opencode/seo-skills/references/")
    body = body.replace("references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("schema/templates.json", "~/.config/opencode/seo-skills/schema/templates.json")
    cmd_file = CMDS / config["file"]
    cmd_file.write_text(f"---\ndescription: {config['desc']}\nagent: general\n---\n{config['preamble']}{body.lstrip()}")
    print(f"OK    {config['file']}")

print("Done.")
```

- [ ] **Step 2: Run and verify**

```bash
python3 /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch2.py
```

Expected: `OK seo-sitemap.md` (x5), `Done.`

- [ ] **Step 3: Commit**

```bash
git add commands/seo-sitemap.md commands/seo-images.md commands/seo-geo.md commands/seo-plan.md commands/seo-programmatic.md
git commit -m "feat: add command files batch 2/5 (sitemap, images, geo, plan, programmatic)"
```

---

### Task 7: Create command files (batch 3 of 5: 5 commands)

**Files:**
- Create: `commands/seo-competitor-pages.md`
- Create: `commands/seo-hreflang.md`
- Create: `commands/seo-local.md`
- Create: `commands/seo-maps.md`
- Create: `commands/seo-google.md`

- [ ] **Step 1: Write and run batch 3 generator**

```python
# /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch3.py
import re
from pathlib import Path

REPO = Path("/Users/fsundquist/Developer/private/claude-seo")
SKILLS = REPO / "skills"
CMDS = REPO / "commands"

COMMANDS = {
    "seo-competitor-pages": {
        "file": "seo-competitor-pages.md",
        "desc": "Competitor comparison page generation. Analyzes competitor content, identifies differentiation opportunities, and generates comparison page structures.",
        "preamble": "The user ran /seo-competitor-pages with argument: $ARGUMENTS\n\nGenerate competitor comparison pages.\n\n---\n\n",
    },
    "seo-hreflang": {
        "file": "seo-hreflang.md",
        "desc": "Hreflang and international SEO audit. Validates language/region targeting, content parity across locales, cultural profile analysis, and hreflang tag generation.",
        "preamble": "The user ran /seo-hreflang with argument: $ARGUMENTS\n\nRun hreflang and international SEO analysis on the provided URL.\n\n---\n\n",
    },
    "seo-local": {
        "file": "seo-local.md",
        "desc": "Local SEO analysis covering Google Business Profile, local citations, NAP consistency, review signals, and map pack visibility.",
        "preamble": "The user ran /seo-local with argument: $ARGUMENTS\n\nRun local SEO analysis on the provided URL.\n\n---\n\n",
    },
    "seo-maps": {
        "file": "seo-maps.md",
        "desc": "Maps intelligence covering geo-grid rank tracking, Google Business Profile audit, local competitor analysis, and review monitoring.",
        "preamble": "The user ran /seo-maps with argument: $ARGUMENTS\n\nRun maps intelligence analysis.\n\n---\n\n",
    },
    "seo-google": {
        "file": "seo-google.md",
        "desc": "Google SEO APIs integration covering Search Console, PageSpeed Insights, CrUX, Indexing API, and Google Analytics 4.",
        "preamble": "The user ran /seo-google with argument: $ARGUMENTS\n\nRun Google SEO API operations.\n\n---\n\n",
    },
}

for skill_name, config in COMMANDS.items():
    skill_md = SKILLS / skill_name / "SKILL.md"
    text = skill_md.read_text()
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    body = text[m.end():]
    body = body.replace("skills/" + skill_name + "/references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("skills/seo/references/", "~/.config/opencode/seo-skills/references/")
    body = body.replace("references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("schema/templates.json", "~/.config/opencode/seo-skills/schema/templates.json")
    cmd_file = CMDS / config["file"]
    cmd_file.write_text(f"---\ndescription: {config['desc']}\nagent: general\n---\n{config['preamble']}{body.lstrip()}")
    print(f"OK    {config['file']}")

print("Done.")
```

- [ ] **Step 2: Run**

```bash
python3 /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch3.py
```

Expected: `OK seo-competitor-pages.md` (x5), `Done.`

- [ ] **Step 3: Commit**

```bash
git add commands/seo-competitor-pages.md commands/seo-hreflang.md commands/seo-local.md commands/seo-maps.md commands/seo-google.md
git commit -m "feat: add command files batch 3/5 (competitor, hreflang, local, maps, google)"
```

---

### Task 8: Create command files (batch 4 of 5: 5 commands)

**Files:**
- Create: `commands/seo-backlinks.md`
- Create: `commands/seo-cluster.md`
- Create: `commands/seo-sxo.md`
- Create: `commands/seo-drift.md`
- Create: `commands/seo-ecommerce.md`

- [ ] **Step 1: Write and run batch 4 generator**

```python
# /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch4.py
import re
from pathlib import Path

REPO = Path("/Users/fsundquist/Developer/private/claude-seo")
SKILLS = REPO / "skills"
CMDS = REPO / "commands"

COMMANDS = {
    "seo-backlinks": {
        "file": "seo-backlinks.md",
        "desc": "Backlink profile analysis covering quality evaluation, anchor text distribution, referring domains, toxic link detection, and competitive link gap analysis.",
        "preamble": "The user ran /seo-backlinks with argument: $ARGUMENTS\n\nRun backlink profile analysis on the provided URL.\n\n---\n\n",
    },
    "seo-cluster": {
        "file": "seo-cluster.md",
        "desc": "SERP-based semantic clustering and content architecture planning. Builds topic clusters, pillar page strategies, and content gap analysis from keyword research.",
        "preamble": "The user ran /seo-cluster with argument: $ARGUMENTS\n\nRun semantic clustering and content architecture analysis.\n\n---\n\n",
    },
    "seo-sxo": {
        "file": "seo-sxo.md",
        "desc": "Search Experience Optimization. Performs SERP backwards analysis to detect page-type mismatches, derives user stories from intent signals, and scores pages from multiple persona perspectives.",
        "preamble": "The user ran /seo-sxo with argument: $ARGUMENTS\n\nRun Search Experience Optimization analysis on the provided URL.\n\n---\n\n",
    },
    "seo-drift": {
        "file": "seo-drift.md",
        "desc": "SEO drift monitoring. Captures baselines, compares current state, and tracks SEO metric changes over time using the drift SQLite database.",
        "preamble": "The user ran /seo-drift with argument: $ARGUMENTS\n\nRun SEO drift monitoring operation.\n\n---\n\n",
    },
    "seo-ecommerce": {
        "file": "seo-ecommerce.md",
        "desc": "E-commerce SEO analysis covering product schema, category architecture, faceted navigation, marketplace intelligence, and shopping feed optimization.",
        "preamble": "The user ran /seo-ecommerce with argument: $ARGUMENTS\n\nRun e-commerce SEO analysis on the provided URL.\n\n---\n\n",
    },
}

for skill_name, config in COMMANDS.items():
    skill_md = SKILLS / skill_name / "SKILL.md"
    text = skill_md.read_text()
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    body = text[m.end():]
    body = body.replace("skills/" + skill_name + "/references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("skills/seo/references/", "~/.config/opencode/seo-skills/references/")
    body = body.replace("references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("schema/templates.json", "~/.config/opencode/seo-skills/schema/templates.json")
    cmd_file = CMDS / config["file"]
    cmd_file.write_text(f"---\ndescription: {config['desc']}\nagent: general\n---\n{config['preamble']}{body.lstrip()}")
    print(f"OK    {config['file']}")

print("Done.")
```

- [ ] **Step 2: Run**

```bash
python3 /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch4.py
```

Expected: `OK seo-backlinks.md` (x5), `Done.`

- [ ] **Step 3: Commit**

```bash
git add commands/seo-backlinks.md commands/seo-cluster.md commands/seo-sxo.md commands/seo-drift.md commands/seo-ecommerce.md
git commit -m "feat: add command files batch 4/5 (backlinks, cluster, sxo, drift, ecommerce)"
```

---

### Task 9: Create command files (batch 5 of 5: 5 commands)

**Files:**
- Create: `commands/seo-flow.md`
- Create: `commands/seo-dataforseo.md`
- Create: `commands/seo-image-gen.md`
- Create: `commands/seo-content-brief.md`
- Create: `commands/seo.md` (orchestrator)

- [ ] **Step 1: Write and run batch 5 generator**

```python
# /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch5.py
import re
from pathlib import Path

REPO = Path("/Users/fsundquist/Developer/private/claude-seo")
SKILLS = REPO / "skills"
CMDS = REPO / "commands"

COMMANDS = {
    "seo-flow": {
        "file": "seo-flow.md",
        "desc": "FLOW framework for evidence-led SEO strategy. Executes staged Find-Leverage-Optimize-Win prompts with search-and-conversion output.",
        "preamble": "The user ran /seo-flow with argument: $ARGUMENTS\n\nExecute the FLOW framework for evidence-led SEO strategy.\n\n---\n\n",
    },
    "seo-dataforseo": {
        "file": "seo-dataforseo.md",
        "desc": "Live SEO data via DataForSEO API. Covers SERP analysis, keyword research, backlink checks, and merchant data queries.",
        "preamble": "The user ran /seo-dataforseo with argument: $ARGUMENTS\n\nExecute DataForSEO API operations.\n\n---\n\n",
    },
    "seo-image-gen": {
        "file": "seo-image-gen.md",
        "desc": "AI image generation for SEO assets. Creates optimized images for blog posts, social sharing, product listings, and schema markup.",
        "preamble": "The user ran /seo-image-gen with argument: $ARGUMENTS\n\nGenerate AI images for SEO assets.\n\n---\n\n",
    },
    "seo-content-brief": {
        "file": "seo-content-brief.md",
        "desc": "Detailed SEO content brief generation covering target keywords, content outline, internal linking strategy, and competitive content analysis.",
        "preamble": "The user ran /seo-content-brief with argument: $ARGUMENTS\n\nGenerate a detailed SEO content brief.\n\n---\n\n",
    },
}

for skill_name, config in COMMANDS.items():
    skill_md = SKILLS / skill_name / "SKILL.md"
    text = skill_md.read_text()
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    body = text[m.end():]
    body = body.replace("skills/" + skill_name + "/references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("skills/seo/references/", "~/.config/opencode/seo-skills/references/")
    body = body.replace("references/", "~/.config/opencode/seo-skills/" + skill_name + "/references/")
    body = body.replace("schema/templates.json", "~/.config/opencode/seo-skills/schema/templates.json")
    cmd_file = CMDS / config["file"]
    cmd_file.write_text(f"---\ndescription: {config['desc']}\nagent: general\n---\n{config['preamble']}{body.lstrip()}")
    print(f"OK    {config['file']}")

# The orchestrator seo.md is a special case — it maps /seo <subcommand> to the right sub-command
seo_text = (SKILLS / "seo" / "SKILL.md").read_text()
m = re.match(r"^---\n.*?\n---\n", seo_text, re.DOTALL)
seo_body = seo_text[m.end():]
seo_body = seo_body.replace("skills/seo/references/", "~/.config/opencode/seo-skills/references/")
seo_body = seo_body.replace("schema/templates.json", "~/.config/opencode/seo-skills/schema/templates.json")
# Update the Quick Reference table to use OpenCode command format
seo_body = seo_body.replace("`/seo ", "`/seo-")
seo_body = re.sub(r"/seo `([a-z-]+)`", r"/seo `\1`", seo_body)

orchestrator_preamble = """The user ran /seo with arguments: $ARGUMENTS

Parse $ARGUMENTS to determine the command ($1) and URL ($2). Then load and execute the appropriate /seo-* command. If $1 matches a known sub-command (audit, page, technical, content, schema, sitemap, images, geo, plan, programmatic, competitor-pages, hreflang, local, maps, google, backlinks, cluster, sxo, drift, ecommerce, flow, dataforseo, image-gen, content-brief, firecrawl), delegate directly. The user will invoke sub-commands directly (e.g. /seo-audit <url>) for most operations.

---

"""
cmd_file = CMDS / "seo.md"
cmd_file.write_text(f"---\ndescription: Comprehensive SEO analysis orchestrator. Routes commands to the 25 sub-commands covering site audits, technical SEO, content quality, schema markup, image optimization, GEO, local SEO, backlinks, and more.\nagent: general\n---\n{orchestrator_preamble}{seo_body.lstrip()}")
print("OK    seo.md")

print("Done.")
```

- [ ] **Step 2: Run**

```bash
python3 /var/folders/8k/scqc50b97_d4f780fjvscdfr0000gp/T/opencode/generate_commands_batch5.py
```

Expected: `OK seo-flow.md` (x4), `OK seo.md`, `Done.`

- [ ] **Step 3: Commit**

```bash
git add commands/seo-flow.md commands/seo-dataforseo.md commands/seo-image-gen.md commands/seo-content-brief.md commands/seo.md
git commit -m "feat: add command files batch 5/5 (flow, dataforseo, image-gen, content-brief, orchestrator)"
```

---

### Task 10: Create opende.jsonc

**Files:**
- Create: `opencode.jsonc`

- [ ] **Step 1: Create the file**

Write `/Users/fsundquist/Developer/private/claude-seo/opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": ["AGENTS.md"],
  "skills": {
    "paths": ["~/.config/opencode/seo-skills"]
  },
  "agent": {
    "seo-technical": { "mode": "subagent", "description": "Technical SEO specialist. Analyzes crawlability, indexability, security, URL structure, mobile optimization, Core Web Vitals, and JavaScript rendering." },
    "seo-content": { "mode": "subagent", "description": "EEAT content quality analyst. Evaluates experience, expertise, authoritativeness, and trustworthiness signals in page content." },
    "seo-schema": { "mode": "subagent", "description": "Schema markup expert. Detects, validates, and generates Schema.org structured data in JSON-LD format." },
    "seo-sitemap": { "mode": "subagent", "description": "XML sitemap analysis and generation specialist. Handles sitemap discovery, validation, IndexNow submission, and structured sitemap generation." },
    "seo-performance": { "mode": "subagent", "description": "Core Web Vitals and page performance specialist. Analyzes LCP, INP, CLS, TTFB, and FCP using PageSpeed Insights, CrUX API, and Lighthouse." },
    "seo-visual": { "mode": "subagent", "description": "Visual SEO analyst. Captures and analyzes page screenshots, checks for layout shifts, visual hierarchy, and above-the-fold content.", "permission": { "external_directory": { "/tmp/*": "allow" } } },
    "seo-geo": { "mode": "subagent", "description": "Generative Engine Optimization analyst. Optimizes content for AI Overviews, ChatGPT, Perplexity, and other AI-powered search experiences." },
    "seo-local": { "mode": "subagent", "description": "Local SEO specialist. Analyzes Google Business Profile, local citations, review signals, NAP consistency, and map pack visibility." },
    "seo-maps": { "mode": "subagent", "description": "Maps intelligence analyst. Handles geo-grid rank tracking, GBP audit, local competitor analysis, and review monitoring." },
    "seo-google": { "mode": "subagent", "description": "Google SEO APIs specialist. Works with Search Console, PageSpeed Insights, CrUX, Indexing API, and Google Analytics 4." },
    "seo-backlinks": { "mode": "subagent", "description": "Backlink profile analyst. Evaluates backlink quality, anchor text distribution, referring domains, and toxic link detection using Moz, Bing, and Common Crawl." },
    "seo-cluster": { "mode": "subagent", "description": "Semantic clustering and content architecture specialist. Performs SERP-based topic clustering, pillar page planning, and content gap analysis." },
    "seo-sxo": { "mode": "subagent", "description": "Search Experience Optimization analyst. Performs SERP backwards analysis to detect page-type mismatches, derives user stories from intent signals, and scores pages from multiple persona perspectives." },
    "seo-drift": { "mode": "subagent", "description": "SEO drift monitoring specialist. Captures baselines, compares current state, and tracks SEO metric changes over time using the drift SQLite database." },
    "seo-ecommerce": { "mode": "subagent", "description": "E-commerce SEO specialist. Analyzes product schema, category architecture, faceted navigation, marketplace intelligence, and shopping feed optimization." },
    "seo-flow": { "mode": "subagent", "description": "FLOW framework specialist. Executes staged Find-Leverage-Optimize-Win prompts with search-and-conversion output for evidence-led SEO strategy." },
    "seo-dataforseo": { "mode": "subagent", "description": "DataForSEO API specialist. Executes SERP analysis, keyword research, backlink checks, and merchant data queries via the DataForSEO platform." },
    "seo-image-gen": { "mode": "subagent", "description": "AI image generation specialist for SEO assets. Creates optimized images for blog posts, social sharing, product listings, and schema markup using AI image generation tools." }
  },
  "mcp": {
    "playwright": {
      "type": "local",
      "command": ["npx", "-y", "@playwright/mcp"],
      "enabled": true,
      "env": { "BROWSER": "chromium" }
    }
  },
  "permission": {
    "bash": { "git *": "allow", "python3 scripts/*": "allow", "*": "ask" },
    "external_directory": { "/tmp/*": "allow" },
    "edit": "ask",
    "webfetch": "allow"
  }
}
```

- [ ] **Step 2: Validate JSON syntax**

```bash
python3 -c "import json; json.load(open('/Users/fsundquist/Developer/private/claude-seo/opencode.jsonc'))" 2>&1
```

If this fails, the JSONC has trailing commas or comments not supported by the stdlib parser. Use:

```bash
python3 -c "
import json, re
text = open('/Users/fsundquist/Developer/private/claude-seo/opencode.jsonc').read()
text = re.sub(r'//.*', '', text)  # strip comments
text = re.sub(r',\s*[\n\r]+\s*(\}|\])', r'\n\1', text)  # trailing commas
json.loads(text)
print('Valid')
"
```

Expected: `Valid`

- [ ] **Step 3: Commit**

```bash
git add opencode.jsonc
git commit -m "feat: add opende.jsonc central configuration"
```

---

### Task 11: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add OpenCode to the harness table**

Replace lines 3-5 (the header comment listing supported harnesses):

Old:
```
> For **Cursor**, **Cursor Cloud Agents**, **Google Antigravity**, **Gemini CLI**,
> **OpenAI Codex CLI**, **Cline**, **Aider**, and any other agent harness that
> reads project-root agent instructions.
```

New:
```
> For **OpenCode**, **Cursor**, **Cursor Cloud Agents**, **Google Antigravity**,
> **Gemini CLI**, **OpenAI Codex CLI**, **Cline**, **Aider**, and any other agent
> harness that reads project-root agent instructions.
```

- [ ] **Step 2: Update the "Working on this repo" test header reference**

Replace `CLAUDE.md` in line 17:
```
`CLAUDE.md` holds the full project rules
```
→ `opencode.jsonc` holds the central project configuration

- [ ] **Step 3: Update manifest consistency section**

Replace lines 37-39:
```
- `.claude-plugin/plugin.json` + `marketplace.json` descriptions (`N sub-skills`, `N sub-agents`)
- the literal phrase `25 sub-skills` (current count) within the first 120 lines of
  `README.md`, `CLAUDE.md`, and this file
```

→ Remove `CLAUDE.md` from the checklist:
```
- the literal phrase `25 sub-skills` (current count) within the first 120 lines of
  `README.md` and this file
```

- [ ] **Step 4: Add OpenCode row to per-harness table**

After line 80 (`| **Aider** | ... |`), add:

```
| **OpenCode** | Install via `bash install.sh` to `~/.config/opencode/`. Commands are invoked as `/seo-audit <url>` etc. Subagents defined via `opencode.jsonc` and `agents/` directory. Skills loaded from `~/.config/opencode/seo-skills/`. |
```

- [ ] **Step 5: Add OpenCode column to tool-name table**

Replace the tool-name table header (line 87):
```
| Claude Code | Codex | Cline | Aider | Cursor / Antigravity |
```
→
```
| Claude Code | OpenCode | Codex | Cline | Aider | Cursor / Antigravity |
```

Add OpenCode column to each row. Rows that already have `Read|Write|Edit|Bash|Glob|Grep|WebFetch` → add `Read|Write|Edit|Bash|Glob|Grep|WebFetch`. Replace the entire table with:

```
| Claude Code | OpenCode | Codex | Cline | Aider | Cursor / Antigravity |
|---|---|---|---|---|---|---|
| Read       | read | read_file        | read_file       | (inline)        | read |
| Write      | write | write_file       | write_file      | /add then edit  | write |
| Edit       | edit | apply_diff       | replace_in_file | /edit           | edit |
| Bash       | bash | bash             | execute_command | /run            | shell |
| Glob       | glob | glob             | search_files    | (inline)        | find |
| Grep       | grep | grep             | search_files    | /grep           | grep |
| WebFetch   | webfetch | fetch / browse   | (browser tool)  | (n/a)           | fetch |
```

- [ ] **Step 6: Update "Using with Google Antigravity" section**

Remove the Antigravity-specific text (lines 163-171) since this is now OpenCode-first. Replace with OpenCode usage section:

```
## Using with OpenCode

OpenCode reads `AGENTS.md` automatically from the project root. Install via:

```bash
bash install.sh
```

Commands are invoked via `/seo-audit <url>`, `/seo-page <url>`, etc. The installer copies commands to `~/.config/opencode/commands/`, agents to `~/.config/opencode/agents/`, and skills to `~/.config/opencode/seo-skills/`.

Python venv path: `~/.config/opencode/seo-skills/.venv/bin/python`
```

- [ ] **Step 7: Update the Architecture section**

Replace `skills/` and `agents/` references (lines 172-205) with the new structure:

```
## Architecture

```
commands/                  # 25 user-invocable /seo-* commands
  seo.md                  # Main orchestrator + routing
  seo-audit.md            # Full site audit
  seo-page.md             # Single-page analysis
  ...
agents/                    # 18 subagents (OpenCode frontmatter)
scripts/                   # 50 Python scripts
skills/                    # Reference content (references/*.md retained)
schema/                    # JSON-LD templates
extensions/                # Optional add-ons (DataForSEO, Firecrawl, Banana)
opencode.jsonc            # Central configuration
```
```

- [ ] **Step 8: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add OpenCode support to AGENTS.md (harness table, tool mapping, architecture)"
```

---

### Task 12: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update title and cover alt text**

```bash
# Edit 1: Cover alt text
```

```
oldString: ![Claude SEO cover: a Claude Code command palette with /seo audit, schema, geo, content, and backlinks commands over a dark CRT panel](assets/cover.svg)
newString: ![OpenCode SEO cover: an OpenCode command palette with /seo-audit, seo-schema, seo-geo, seo-content, and seo-backlinks commands over a dark CRT panel](assets/cover.svg)
```

```bash
# Edit 2: Title
```

```
oldString: # Claude SEO: SEO Skill for Claude Code
newString: # OpenCode SEO: SEO Tool for OpenCode
```

```bash
# Edit 3: Intro paragraph
```

```
oldString: **Claude SEO is an open-source SEO analysis plugin for [Claude Code](https://claude.ai/claude-code).** It runs 25 sub-skills and 18 specialist agents in parallel across technical SEO, content quality (E-E-A-T), Schema.org markup, AI search optimization (GEO), local SEO, e-commerce, and international SEO. Every audit produces a prioritized action plan with testable recommendations grounded in primary-source guidance from Google.
newString: **OpenCode SEO is an open-source SEO analysis tool for [OpenCode](https://opencode.ai).** It runs 25 sub-skills and 18 specialist agents in parallel across technical SEO, content quality (E-E-A-T), Schema.org markup, AI search optimization (GEO), local SEO, e-commerce, and international SEO. Every audit produces a prioritized action plan with testable recommendations grounded in primary-source guidance from Google.
```

- [ ] **Step 2: Replace badges**

```bash
# Edit 4: CI badge (unchanged, but remove Claude-specific badge)
```

```
oldString: [![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://claude.ai/claude-code)
newString: [![OpenCode](https://img.shields.io/badge/OpenCode-Tool-blue)](https://opencode.ai)
```

- [ ] **Step 3: Update "Why Claude SEO" heading and internal references**

```bash
# Edit 5: Section heading
```

```
oldString: ### Why Claude SEO
newString: ### Why OpenCode SEO
```

```bash
# Edit 6: Demo caption
```

```
oldString: ![Claude SEO /seo command demo in Claude Code terminal]
newString: ![OpenCode SEO command demo]
```

```bash
# Edit 7: Demo caption 2
```

```
oldString: ![Claude SEO /seo audit demo: parallel subagents producing a prioritized action plan]
newString: ![OpenCode SEO audit demo: parallel subagents producing a prioritized action plan]
```

```bash
# Edit 8: Install section command examples (will vary by file section — search and replace pattern)
```

```
oldString: /seo audit
newString: /seo-audit
```

Apply replaceAll on `/seo ` → `/seo-` throughout the file. Then manually fix any over-replacements (e.g., `/seo-` appearing twice from original `/seo-audit` patterns).

```bash
# Edit 9: Install instruction (search for "claude" mentions)
```

```
oldString: Start Claude Code:  claude
newString: Start OpenCode:  opencode
```

- [ ] **Step 4: Update "Using Codex" line**

```
oldString: Using Codex instead of Claude Code? Use [Codex SEO]
newString: Using Claude Code instead of OpenCode? The original [Claude SEO](https://github.com/AgriciDaniel/claude-seo/tree/claude-legacy) tool is preserved on the `claude-legacy` branch.
```

- [ ] **Step 5: Verify "25 sub-skills" phrase is still within first 120 lines**

```bash
head -120 README.md | grep "25 sub-skills"
```

Expected: The phrase appears (required for manifest consistency test).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README for OpenCode support"
```

---

### Task 13: Update docs/COMMANDS.md

**Files:**
- Modify: `docs/COMMANDS.md`

- [ ] **Step 1: Update overview line**

```
oldString: All Claude SEO commands start with `/seo` followed by a subcommand.
newString: All OpenCode SEO commands start with `/seo-` followed by the analysis type.
```

- [ ] **Step 2: Update all command headers from `/seo <sub>` to `/seo-<sub>`**

Use `replaceAll` to change `/seo ` to `/seo-` throughout the file. Then manually fix:
- `### /seo-content-brief` → keep as-is (was `/seo content-brief`)
- `### /seo-competitor-pages` → keep as-is (was `/seo competitor-pages`)
- `### /seo-image-gen` → keep as-is (was `/seo image-gen`)
- Backlink sub-commands: `/seo-backlinks setup` → keep; `/seo-backlinks verify` → keep
- Drift sub-commands: `/seo-drift baseline` → keep; `/seo-drift compare` → keep; `/seo-drift history` → keep
- Google sub-commands: `/seo-google` entries → keep as-is
- Maps sub-commands: `/seo-maps` entries → keep as-is
- Flow sub-commands: `/seo-flow` entries → keep as-is

- [ ] **Step 3: Update example blocks**

Run `replaceAll` for these specific patterns:
```
/search for examples like `/seo audit https:// and replace with `/seo-audit https://
```

- [ ] **Step 4: Verify no remaining `/seo ` (single space) patterns exist**

```bash
grep "/seo " /Users/fsundquist/Developer/private/claude-seo/docs/COMMANDS.md | grep -v "/seo-" | grep -v "#seo"
```

Expected: No output (all commands are now `/seo-<name>` format).

- [ ] **Step 2: Commit**

```bash
git add docs/COMMANDS.md
git commit -m "docs: update COMMANDS.md for OpenCode command format"
```

---

### Task 14: Rewrite install and uninstall scripts

**Files:**
- Modify: `install.sh`
- Modify: `install.ps1`
- Modify: `uninstall.sh`
- Modify: `uninstall.ps1`

- [ ] **Step 1: Rewrite install.sh**

Replace all Claude Code paths (`~/.claude/skills/seo`, `~/.claude/agents`) with OpenCode equivalents (`~/.config/opencode/seo-skills`, `~/.config/opencode/agents`). Update the header and usage section.

Key replacements in `install.sh`:
```
SKILL_DIR="${HOME}/.claude/skills/seo"     → SKILL_DIR="${HOME}/.config/opencode/seo-skills"
AGENT_DIR="${HOME}/.claude/agents"          → AGENT_DIR="${HOME}/.config/opencode/agents"
COMMANDS_DIR="${HOME}/.config/opencode/commands"
"Claude SEO - Installer"                    → "OpenCode SEO - Installer"
"Claude Code SEO Skill"                     → "OpenCode SEO Tool"
"Start Claude Code:  claude"                → "Start OpenCode:  opencode"
"/seo audit https://example.com"            → "/seo-audit https://example.com"
```

Add new sections to copy:
- `commands/` → `COMMANDS_DIR`
- Skip hooks section (remove hooks copy block entirely)

- [ ] **Step 2: Verify install.sh paths**

```bash
grep "\.claude" /Users/fsundquist/Developer/private/claude-seo/install.sh
```

Expected: Only `~/.config/claude-seo/` (API credentials path, intentionally kept). No `~/.claude/skills` or `~/.claude/agents`.

- [ ] **Step 3: Rewrite install.ps1**

Same path replacements as install.sh but in PowerShell syntax. Replace `REPO_TAG` variable from `CLAUDE_SEO_TAG` to `OPENCODE_SEO_TAG`.

- [ ] **Step 4: Rewrite uninstall.sh and uninstall.ps1**

Replace removal paths from `~/.claude/skills/seo*` and `~/.claude/agents/seo-*` to OpenCode equivalents:
- `~/.config/opencode/seo-skills`  
- `~/.config/opencode/agents/seo-*.md`
- `~/.config/opencode/commands/seo*.md`

- [ ] **Step 5: Commit**

```bash
git add install.sh install.ps1 uninstall.sh uninstall.ps1
git commit -m "feat: rewrite install/uninstall scripts for OpenCode paths"
```

---

### Task 15: Update test_manifest_consistency.py

**Files:**
- Modify: `tests/test_manifest_consistency.py`

- [ ] **Step 1: Remove Claude-specific test references**

The test file references `plugin.json`, `marketplace.json`, `CLAUDE.md`. Since these files are deleted, the tests that reference them must be updated or removed.

Changes needed:
- Remove `PLUGIN_JSON` and `MARKETPLACE_JSON` constants (lines 18-19)
- Delete tests: `test_plugin_json_skill_count_matches_disk`, `test_plugin_json_description_fits_registry_limit`, `test_plugin_json_subagent_count_matches_disk`, `test_marketplace_json_skill_count_matches_plugin_json`, `test_marketplace_json_subagent_count_matches_plugin_json`, `test_canonical_math_adds_up`, `test_version_triangulation`, `test_pyproject_version_matches_plugin_json`, `test_install_scripts_default_tag_matches_plugin_version`, `test_marketplace_metadata_and_author_parity`, `test_skill_metadata_versions_match_plugin_json`
- Update `test_canonical_phrasing_in_user_visible_docs` (line 109-120) to remove `CLAUDE.md` from the check
- Keep: `test_orchestrator_sub_skills_list_matches_disk`, `test_orchestrator_subagents_list_matches_disk`, `test_reference_files_have_at_least_one_link`
- Add: command count test (verify `commands/` has 25 .md files)
- Add: agent frontmatter format test (verify no `model:`, `maxTurns:`, `tools:` in agent files)
- Add: agent `mode: subagent` test (verify every agent has `mode: subagent`)

- [ ] **Step 2: Write updated test file**

The updated test file should be:

```python
"""
Tests that ensure OpenCode manifest claims match reality on disk.

Updated for OpenCode-native rewrite. plugin.json/marketplace.json/CLAUDE.md
are removed; consistency now checks commands/, agents/, and opencode.jsonc.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _count_skill_dirs() -> int:
    skills_dir = REPO_ROOT / "skills"
    return sum(
        1 for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    )


def _count_agent_files() -> int:
    agents_dir = REPO_ROOT / "agents"
    return sum(
        1 for f in agents_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name.startswith("seo-")
    )


def _count_command_files() -> int:
    commands_dir = REPO_ROOT / "commands"
    if not commands_dir.exists():
        return 0
    return sum(
        1 for f in commands_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name.startswith("seo")
    )


def test_canonical_phrasing_in_user_visible_docs():
    """README and AGENTS.md must reference the canonical sub-skills count."""
    skill_count = _count_skill_dirs()
    target_phrase = f"{skill_count} sub-skills"
    for filename in ["README.md", "AGENTS.md"]:
        path = REPO_ROOT / filename
        head = "\n".join(path.read_text().splitlines()[:120])
        assert target_phrase in head, (
            f"{filename} does not reference '{target_phrase}' in its first "
            f"120 lines."
        )


def test_command_count_matches_skill_count():
    """commands/ count must equal skills/ count (minus orchestrator)."""
    skill_count = _count_skill_dirs()
    command_count = _count_command_files()
    # The orchestrator seo/SKILL.md maps to seo.md command (included)
    assert command_count == skill_count, (
        f"commands/ has {command_count} files but skills/ has "
        f"{skill_count} SKILL.md dirs. Counts must match."
    )


def test_agent_frontmatter_has_no_claude_fields():
    """No agent file should contain model:, maxTurns:, tools:, or name: in frontmatter."""
    agents_dir = REPO_ROOT / "agents"
    errors = []
    for agent_file in agents_dir.glob("seo-*.md"):
        text = agent_file.read_text()
        # Extract frontmatter
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            errors.append(f"{agent_file.name}: no frontmatter")
            continue
        fm = m.group(1)
        for banned in ["model:", "maxTurns:", "tools:", "name:"]:
            if banned in fm:
                errors.append(f"{agent_file.name}: contains '{banned}' in frontmatter")
    assert not errors, "Agent frontmatter contains Claude-specific fields:\n  " + "\n  ".join(errors)


def test_agent_frontmatter_has_mode_subagent():
    """Every agent file must have mode: subagent in frontmatter."""
    agents_dir = REPO_ROOT / "agents"
    errors = []
    for agent_file in agents_dir.glob("seo-*.md"):
        text = agent_file.read_text()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            errors.append(f"{agent_file.name}: no frontmatter")
            continue
        fm = m.group(1)
        if "mode: subagent" not in fm:
            errors.append(f"{agent_file.name}: missing 'mode: subagent'")
    assert not errors, "Agent files missing mode: subagent:\n  " + "\n  ".join(errors)


def test_orchestrator_sub_skills_list_matches_disk():
    """skills/seo/SKILL.md Sub-Skills numbered list must equal set(skills/*) minus orchestrator itself."""
    text = (REPO_ROOT / "skills" / "seo" / "SKILL.md").read_text()
    section = _extract_section(text, "Sub-Skills")
    listed_list = re.findall(r"^\d+\.\s+\*\*(seo-[a-z-]+)\*\*", section, re.MULTILINE)
    assert len(listed_list) == len(set(listed_list)), (
        f"Duplicate entries in Sub-Skills list"
    )
    listed = set(listed_list)
    on_disk = {
        d.name for d in (REPO_ROOT / "skills").iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    }
    expected = on_disk - {"seo"}
    assert listed == expected, (
        f"Sub-Skills list != skills/ dir. "
        f"Missing from list: {sorted(expected - listed)}. "
        f"Extra in list: {sorted(listed - expected)}."
    )


def test_orchestrator_subagents_list_matches_disk():
    """skills/seo/SKILL.md Subagents bullet list must equal set(agents/seo-*.md)."""
    text = (REPO_ROOT / "skills" / "seo" / "SKILL.md").read_text()
    section = _extract_section(text, "Subagents")
    listed_list = re.findall(r"^- `(seo-[a-z-]+)`", section, re.MULTILINE)
    assert len(listed_list) == len(set(listed_list)), (
        f"Duplicate entries in Subagents list"
    )
    listed = set(listed_list)
    on_disk = {
        p.stem for p in (REPO_ROOT / "agents").iterdir()
        if p.is_file() and p.suffix == ".md" and p.name.startswith("seo-")
    }
    assert listed == on_disk, (
        f"Subagents list != agents/ dir. "
        f"Missing from list: {sorted(on_disk - listed)}. "
        f"Extra in list: {sorted(listed - on_disk)}."
    )


def test_reference_files_have_at_least_one_link():
    """Every skills/*/references/*.md file must be cited somewhere in the repo."""
    ref_files = list((REPO_ROOT / "skills").glob("*/references/*.md"))
    if not ref_files:
        return

    search_paths = []
    search_paths += list((REPO_ROOT / "skills").glob("*/SKILL.md"))
    search_paths += list((REPO_ROOT / "agents").glob("*.md"))
    search_paths += list((REPO_ROOT / "commands").glob("*.md"))
    search_paths += list((REPO_ROOT / "docs").glob("*.md"))
    for doc in ("README.md", "CHANGELOG.md", "AGENTS.md", "CONTRIBUTING.md"):
        candidate = REPO_ROOT / doc
        if candidate.exists():
            search_paths.append(candidate)
    search_paths += ref_files

    text_by_path = {p: p.read_text() for p in search_paths}

    orphans = []
    for ref in ref_files:
        slug = ref.stem
        filename = ref.name
        wikilink = f"[[{slug}]]"
        found = False
        for other_path, text in text_by_path.items():
            if other_path == ref:
                continue
            if filename in text or wikilink in text:
                found = True
                break
        if not found:
            orphans.append(str(ref.relative_to(REPO_ROOT)))

    assert not orphans, (
        "Orphan reference files:\n  " + "\n  ".join(orphans)
    )


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\b.*?(?=^## |\Z)"
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return m.group(0) if m else ""
```

- [ ] **Step 3: Run updated tests**

```bash
pytest tests/test_manifest_consistency.py -v
```

Expected: All tests pass. If any fail, fix the specific consistency issue before proceeding.

- [ ] **Step 4: Commit**

```bash
git add tests/test_manifest_consistency.py
git commit -m "test: update manifest consistency tests for OpenCode structure"
```

---

### Task 16: Run full test suite

**Files:** None modified. Verify all existing tests pass.

- [ ] **Step 1: Install test dependencies**

```bash
pip install -r requirements.txt pytest
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass (excluding `test_sync_flow.py` if `gh` not authenticated — that's pre-existing).

- [ ] **Step 3: Run ruff lint**

```bash
ruff check scripts/
```

Expected: No new issues. Any pre-existing warnings are acceptable.

- [ ] **Step 4: Run py_compile check (CI simulation)**

```bash
python3 -c "
from pathlib import Path
import py_compile, sys
errors = []
for f in Path('scripts').glob('*.py'):
    try:
        py_compile.compile(str(f), doraise=True)
    except py_compile.PyCompileError as e:
        errors.append(str(e))
if errors:
    print('PY_COMPILE ERRORS:')
    for e in errors:
        print(e)
    sys.exit(1)
print('All scripts compile cleanly')
"
```

Expected: `All scripts compile cleanly`

- [ ] **Step 5: Verify no remaining Claude Code references**

```bash
rg "\.claude/skills|\.claude/agents|CLAUDE_PLUGIN_ROOT|claude-plugin" --include="*.{sh,md,json,py,ps1}" --exclude-dir=.git --exclude-dir=.venv 2>&1 | grep -v "\.config/claude-seo" || echo "No stale Claude paths found"
```

Expected: Only `~/.config/claude-seo/` (API config path, intentionally kept). No other Claude-specific paths.

- [ ] **Step 6: Commit if any fixes were needed**

```bash
git add -A
git diff --cached --stat
git commit -m "chore: final cleanup after OpenCode rewrite validation"
```

---

### Task 17: Final verification checklist

**No file changes.** Manual verification steps.

- [ ] **Step 1: Verify file counts**

```bash
echo "Skills: $(ls -d skills/seo-*/ | wc -l) + orchestrator"
echo "Agents: $(ls agents/seo-*.md | wc -l)"
echo "Commands: $(ls commands/seo*.md | wc -l)"
echo "Scripts: $(ls scripts/*.py | wc -l)"
```

Expected: 24 skills + orchestrator, 18 agents, 25 commands, 50 scripts.

- [ ] **Step 2: Verify no orphan references**

```bash
python3 scripts/portability_check.py
```

- [ ] **Step 3: Print summary**

```bash
echo "=== OpenCode Rewrite Complete ==="
echo "Removed: .claude-plugin/, CLAUDE.md, hooks/, marketplace.json, docs/MCP-INTEGRATION.md"
echo "Added: commands/ (25 files), opende.jsonc, docs/2026-07-17-opencode-rewrite-design.md"
echo "Modified: agents/ (18 files), AGENTS.md, README.md, docs/COMMANDS.md, install/uninstall scripts, tests/test_manifest_consistency.py"
echo "Untouched: scripts/ (50 files), schema/, data/, extensions/, assets/, tests/ (other)"
echo ""
echo "Install: bash install.sh"
echo "Usage:   /seo-audit <url> in OpenCode"
```
