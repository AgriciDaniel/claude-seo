# Profound extension setup

Profound (https://tryprofound.com) tracks brand mentions across LLMs as
a time-series: the complement to SE Ranking's on-demand sampling.

## Install

```bash
./extensions/profound/install.sh        # Linux / macOS
.\extensions\profound\install.ps1       # Windows
```

Stores `PROFOUND_API_KEY` in `~/.claude/settings.json` env block, mode 0o600.

## Verify

```
/seo profound citations "Claude SEO"
```

## Uninstall

```bash
./extensions/profound/uninstall.sh
```

## When to use Profound vs. SE Ranking

| Use Profound | Use SE Ranking |
|---|---|
| Trend analysis (week-over-week brand mention drift) | Single-shot SoV measurement |
| ChatGPT + Perplexity deep coverage | All 5 platforms in one call |
| Alerts on citation rate change | Competitor-keyword gap analysis |

The two are complementary, not redundant. Install both for full AI
visibility coverage; install one if budget-constrained.
