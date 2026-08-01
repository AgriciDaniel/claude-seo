#!/usr/bin/env python3
"""Claude Banana - Cost Tracker

Track image generation costs, view summaries, and estimate batch costs.

Usage:
    cost_tracker.py log --model MODEL --resolution RES --prompt "summary"
    cost_tracker.py summary
    cost_tracker.py today
    cost_tracker.py estimate --model MODEL --resolution RES --count N
    cost_tracker.py reset --confirm
"""

import argparse
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

# BANANA_HOME lets tests (and anyone running an isolated budget) point the
# ledger and pricing config somewhere other than the real ones. Resolved at
# import.
BANANA_DIR = Path(os.environ.get("BANANA_HOME") or Path.home() / ".banana")
LEDGER_PATH = BANANA_DIR / "costs.json"
LOCK_PATH = BANANA_DIR / "costs.lock"
PRICING_PATH = BANANA_DIR / "pricing.json"
PRICING_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"


def _empty_ledger():
    return {"total_cost": 0.0, "total_images": 0, "entries": [], "daily": {}}


# Batch API gets 50% discount
BATCH_DISCOUNT = 0.5


class LedgerError(RuntimeError):
    """The cost ledger could not be read or written safely."""


def _lock(handle, exclusive):
    """Take an advisory lock on an open handle, blocking until acquired.

    Never degrades to running unlocked: a cost ledger that silently drops
    entries is worse than one that refuses to run.
    """
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    elif msvcrt is not None:
        # msvcrt has no shared mode, so readers take an exclusive lock too.
        # LK_LOCK retries 10 times at 1s intervals, then raises OSError.
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        raise LedgerError(
            "No file-locking primitive available (neither fcntl nor msvcrt). "
            "Refusing to touch the cost ledger unlocked."
        )


def _unlock(handle):
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_UN)
    elif msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _read_ledger():
    """Read the ledger. Caller must hold the lock."""
    if not LEDGER_PATH.exists():
        return _empty_ledger()
    try:
        with open(LEDGER_PATH, "r") as f:
            ledger = json.load(f)
    except json.JSONDecodeError as exc:
        raise LedgerError(
            f"Cost ledger {LEDGER_PATH} is not valid JSON ({exc}). Refusing to "
            "continue from a zero balance, which would under-report spend. "
            "Inspect the file, then repair or remove it."
        ) from exc
    if not isinstance(ledger, dict) or not isinstance(ledger.get("entries"), list):
        raise LedgerError(
            f"Cost ledger {LEDGER_PATH} has an unexpected shape (no 'entries' "
            "list). Inspect the file, then repair or remove it."
        )
    # Tolerate ledgers written before a field existed.
    ledger.setdefault("total_cost", 0.0)
    ledger.setdefault("total_images", 0)
    ledger.setdefault("daily", {})
    return ledger


def _write_ledger(ledger):
    """Write the ledger atomically. Caller must hold the exclusive lock.

    tempfile + os.replace so a crash mid-write can never leave a truncated,
    unparseable ledger behind.
    """
    BANANA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(BANANA_DIR), prefix=".costs.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(ledger, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, LEDGER_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


@contextmanager
def _locked_ledger(write=False):
    """Yield the ledger under ONE lock held across the whole read-modify-write.

    Reading under one lock, dropping it, then re-taking it to write loses
    entries: two concurrent `log` calls both read the same ledger and the
    second overwrites the first. This ledger also carries running aggregates
    (total_cost, total_images, daily), so a lost write drops the entry and its
    aggregate increment together and the file still looks self-consistent.

    The lock lives in a separate .lock file on purpose. The atomic write
    replaces the ledger's inode, so a lock held on the ledger itself would not
    protect the replacement.
    """
    BANANA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+") as lock_handle:
        _lock(lock_handle, exclusive=write)
        try:
            ledger = _read_ledger()
            yield ledger
            if write:
                _write_ledger(ledger)
        finally:
            _unlock(lock_handle)


def _ledger_snapshot():
    """Read the ledger under a shared lock. For read-only commands."""
    with _locked_ledger() as ledger:
        return ledger


def _load_pricing_config():
    """Load dated pricing config from disk."""
    if not PRICING_PATH.exists():
        print(f"Error: Missing pricing config at {PRICING_PATH}.", file=sys.stderr)
        print(f"Check current pricing at {PRICING_SOURCE}, then create a dated pricing.json.", file=sys.stderr)
        sys.exit(1)
    with open(PRICING_PATH, "r") as f:
        data = json.load(f)
    models = data.get("models", {})
    checked_date = data.get("checked_date")
    if not models or not checked_date:
        print("Error: pricing.json must include checked_date and models.", file=sys.stderr)
        sys.exit(1)
    return models, checked_date


def _lookup_cost(model, resolution, batch=False):
    """Look up cost for a model+resolution combination."""
    pricing, checked_date = _load_pricing_config()
    model_pricing = pricing.get(model)
    if not model_pricing:
        # Try partial match
        for key in pricing:
            if key in model or model in key:
                model_pricing = pricing[key]
                break
    if not model_pricing:
        print(f"Error: No pricing for model '{model}' in {PRICING_PATH}.", file=sys.stderr)
        print(f"Check current pricing at {PRICING_SOURCE} and update pricing.json.", file=sys.stderr)
        sys.exit(1)

    valid_resolutions = {"512", "1K", "2K", "4K"}
    if resolution not in valid_resolutions:
        print(f"Warning: Unknown resolution '{resolution}', using 1K pricing", file=sys.stderr)
    cost = model_pricing.get(resolution, model_pricing.get("1K"))
    if cost is None:
        print(f"Error: No pricing for resolution '{resolution}' in {PRICING_PATH}.", file=sys.stderr)
        sys.exit(1)
    if batch:
        cost *= BATCH_DISCOUNT
    return cost, checked_date


def cmd_log(args):
    """Log a generation to the ledger."""
    cost, checked_date = _lookup_cost(args.model, args.resolution, getattr(args, "batch", False))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    entry = {
        "ts": now,
        "model": args.model,
        "res": args.resolution,
        "cost": cost,
        "pricing_checked_date": checked_date,
        "approximate": True,
        "prompt": args.prompt[:100],
    }

    # Read and write inside one lock, so a concurrent log cannot overwrite this
    # entry (and its aggregate increments) with a ledger it read beforehand.
    with _locked_ledger(write=True) as ledger:
        ledger["entries"].append(entry)
        ledger["total_cost"] = round(ledger["total_cost"] + cost, 4)
        ledger["total_images"] += 1

        if today not in ledger["daily"]:
            ledger["daily"][today] = {"count": 0, "cost": 0.0}
        ledger["daily"][today]["count"] += 1
        ledger["daily"][today]["cost"] = round(ledger["daily"][today]["cost"] + cost, 4)

        total_cost = ledger["total_cost"]
        total_images = ledger["total_images"]

    print(json.dumps({"logged": True, "cost": cost, "total_cost": total_cost,
                       "total_images": total_images, "approximate": True,
                       "pricing_checked_date": checked_date}))


def cmd_summary(args):
    """Show cost summary."""
    ledger = _ledger_snapshot()
    print(f"Total images: {ledger['total_images']}")
    print(f"Total cost:   approx ${ledger['total_cost']:.3f}")
    print()

    daily = ledger.get("daily", {})
    if daily:
        # Show last 7 days
        sorted_days = sorted(daily.keys(), reverse=True)[:7]
        print("Last 7 days:")
        for day in sorted_days:
            d = daily[day]
            print(f"  {day}: {d['count']} images, approx ${d['cost']:.3f}")
    else:
        print("No usage recorded yet.")


def cmd_today(args):
    """Show today's usage."""
    ledger = _ledger_snapshot()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = ledger.get("daily", {}).get(today, {"count": 0, "cost": 0.0})
    print(f"Today ({today}): {daily['count']} images, approx ${daily['cost']:.3f}")


def cmd_estimate(args):
    """Estimate cost for a batch."""
    cost_per, checked_date = _lookup_cost(args.model, args.resolution, getattr(args, "batch", False))
    total = round(cost_per * args.count, 3)
    print(f"Model:      {args.model}")
    print(f"Resolution: {args.resolution}")
    print(f"Count:      {args.count}")
    print(f"Pricing checked: {checked_date}")
    print(f"Approx cost/image: ${cost_per:.3f}")
    print(f"Approx total est:  ${total:.3f}")
    if not getattr(args, "batch", False):
        batch_total = round(cost_per * BATCH_DISCOUNT * args.count, 3)
        print(f"Approx batch est:  ${batch_total:.3f} (50% discount)")


def cmd_reset(args):
    """Reset the ledger."""
    if not args.confirm:
        print("Error: Pass --confirm to reset the cost ledger.", file=sys.stderr)
        sys.exit(1)
    # Takes the same exclusive lock as `log`, but deliberately does NOT read
    # first: reset is the recovery path for a corrupt ledger, so it must not
    # depend on the existing file parsing.
    BANANA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+") as lock_handle:
        _lock(lock_handle, exclusive=True)
        try:
            _write_ledger(_empty_ledger())
        finally:
            _unlock(lock_handle)
    print("Cost ledger reset.")


def main():
    parser = argparse.ArgumentParser(description="Claude Banana Cost Tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    p_log = sub.add_parser("log", help="Log a generation")
    p_log.add_argument("--model", required=True, help="Model ID")
    p_log.add_argument("--resolution", required=True, help="Resolution (512, 1K, 2K, 4K)")
    p_log.add_argument("--prompt", required=True, help="Brief prompt description")
    p_log.add_argument("--batch", action="store_true", help="Batch API (50%% discount)")

    # summary
    sub.add_parser("summary", help="Show cost summary")

    # today
    sub.add_parser("today", help="Show today's usage")

    # estimate
    p_est = sub.add_parser("estimate", help="Estimate batch cost")
    p_est.add_argument("--model", required=True, help="Model ID")
    p_est.add_argument("--resolution", required=True, help="Resolution (512, 1K, 2K, 4K)")
    p_est.add_argument("--count", required=True, type=int, help="Number of images")
    p_est.add_argument("--batch", action="store_true", help="Use batch pricing (50%% discount)")

    # reset
    p_reset = sub.add_parser("reset", help="Reset cost ledger")
    p_reset.add_argument("--confirm", action="store_true", help="Confirm reset")

    args = parser.parse_args()
    cmds = {"log": cmd_log, "summary": cmd_summary, "today": cmd_today,
            "estimate": cmd_estimate, "reset": cmd_reset}
    try:
        cmds[args.command](args)
    except LedgerError as exc:
        # Fail closed and loudly rather than under-reporting spend.
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
