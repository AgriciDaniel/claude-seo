# Cost Tracking Reference

> Load this on-demand when the user asks about costs or before batch operations.

## Pricing Source

Pricing is not hard-coded. Check current Google pricing before estimating:
https://ai.google.dev/gemini-api/docs/pricing

Store dated pricing in `~/.banana/pricing.json` before using cost commands:

```json
{
  "source": "https://ai.google.dev/gemini-api/docs/pricing",
  "checked_date": "YYYY-MM-DD",
  "models": {
    "MODEL_ID": {
      "1K": null
    }
  }
}
```

Replace `null` with the checked USD cost before running estimates.
Treat all estimates as approximate.

## Free Tier Limits

Verify current limits in Google AI Studio before batch operations.

## Cost Tracker Commands

```bash
# Log a generation
cost_tracker.py log --model "$NANOBANANA_MODEL" --resolution 1K --prompt "coffee shop hero"

# View summary (total + last 7 days)
cost_tracker.py summary

# Today's usage
cost_tracker.py today

# Estimate before batch
cost_tracker.py estimate --model "$NANOBANANA_MODEL" --resolution 1K --count 10

# Reset ledger
cost_tracker.py reset --confirm
```

## Storage

Ledger stored at `~/.banana/costs.json`. Created automatically on first use.
