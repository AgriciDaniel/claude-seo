# Cost Tracking Reference

> Load this on-demand when the user asks about costs or before batch operations.

## Pricing Table

| Model | Resolution | Cost/Image | Notes |
|-------|-----------|-----------|-------|
| Installed MCP model | Any | Verify before use | Check https://ai.google.dev/gemini-api/docs/pricing and installed MCP config |
| Batch API | Any | Verify before use | Confirm availability and discount before quoting |

Do not quote fixed package prices unless they have been verified at https://ai.google.dev/gemini-api/docs/pricing.

## Free Tier Limits

- ~10 requests per minute (RPM)
- ~500 requests per day (RPD)
- Per Google Cloud project, resets midnight Pacific

## Cost Tracker Commands

```bash
# Log a generation
cost_tracker.py log --model gemini-3.1-flash-image-preview --resolution 1K --prompt "coffee shop hero"

# View summary (total + last 7 days)
cost_tracker.py summary

# Today's usage
cost_tracker.py today

# Estimate before batch
cost_tracker.py estimate --model gemini-3.1-flash-image-preview --resolution 1K --count 10

# Reset ledger
cost_tracker.py reset --confirm
```

## Storage

Ledger stored at `~/.banana/costs.json`. Created automatically on first use.
