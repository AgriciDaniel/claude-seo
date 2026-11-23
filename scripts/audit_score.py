#!/usr/bin/env python3
"""SEO Health Score from measured category scores.

The audit skills publish seven category weights that sum to 100. This script
is the only place those weights are applied. The model records each category
score; it does not multiply, rescale, or round the total.

Formula, for the categories that were actually measured::

    health_score = sum(score * weight) / sum(weight)

A null score is left out. The remaining weights are rescaled by that
division, which is the same as redistributing the missing weight in
proportion to the weights that remain. A missing category is never treated
as 0: a zero would punish the site for a check that did not run.

The numeric score is returned whenever at least one category was measured.
``coverage_percent`` is always reported, and ``status`` is ``partial`` when
any weight is missing, so a partial score is not presented as a full audit.
One missing category is still a usable score (a rate-limited PageSpeed run
is the Performance category, 10% of the weight). There is no second cutoff
below 100%. When nothing was measured, ``health_score`` is null and
``status`` is ``insufficient``.

Usage:
    python audit_score.py --data {domain}-audit/audit-data.json --write --json

``--data`` is an audit envelope with a ``categories`` list of
``{"name", "score"}`` objects. ``--write`` stores the result on ``summary``
for ``google_report.py`` and leaves every other field alone. ``--json`` is
accepted for compatibility; the script always prints one JSON object.

Output (JSON on stdout)::

    {
      "status": "complete" | "partial" | "insufficient",
      "health_score": 78,
      "health_score_exact": "78.1111",
      "coverage_percent": 90,
      "measured_weight": 90,
      "total_weight": 100,
      "omitted": [{"name": "Performance (CWV)", "weight": 10,
                   "reason": "not measured"}],
      "categories": [ ... all seven, measured or not ... ],
      "presentation": "Score 78/100 covers 90% of the category weight. ..."
    }

``health_score`` is the display integer (half up). ``health_score_exact``
is the unrounded quotient to 4 decimal places. Category ``score`` values in
the breakdown are decimal strings, not binary floats.

Exit codes:
    0  the score was computed, including partial and insufficient results
    1  the file could not be read or written
    2  the envelope or a category score is invalid
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal, DecimalException
from pathlib import Path

# Published in skills/seo/SKILL.md and skills/seo-audit/SKILL.md.
# A test fails if either table drifts from this tuple.
WEIGHTS: tuple[tuple[str, int], ...] = (
    ("Technical SEO", 22),
    ("Content Quality", 23),
    ("On-Page SEO", 20),
    ("Schema / Structured Data", 10),
    ("Performance (CWV)", 10),
    ("AI Search Readiness", 10),
    ("Images", 5),
)

TOTAL_WEIGHT = sum(weight for _, weight in WEIGHTS)
if TOTAL_WEIGHT != 100:
    raise RuntimeError(f"category weights sum to {TOTAL_WEIGHT}, not 100")

_CANONICAL = {name: weight for name, weight in WEIGHTS}

# Extra names seen in audit drafts. Canonical names are added below.
_ALIASES = {
    "technical": "Technical SEO",
    "content": "Content Quality",
    "on page": "On-Page SEO",
    "onpage": "On-Page SEO",
    "onpage seo": "On-Page SEO",
    "schema": "Schema / Structured Data",
    "structured data": "Schema / Structured Data",
    "schema and structured data": "Schema / Structured Data",
    "performance": "Performance (CWV)",
    "cwv": "Performance (CWV)",
    "core web vitals": "Performance (CWV)",
    "ai search": "AI Search Readiness",
    "ai readiness": "AI Search Readiness",
    "image seo": "Images",
    "image optimization": "Images",
}

_UNMEASURED_TEXT = {
    "",
    "null",
    "none",
    "n/a",
    "na",
    "not assessed",
    "not measured",
    "insufficient",
    "insufficient data",
}

_EXACT = Decimal("0.0001")
_NAME_LIMIT = 80
# Plain decimals only. Scientific notation is rejected so a token like
# "1e999999" cannot expand into a million-character message.
_PLAIN_SCORE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


def _normalize(name: str) -> str:
    text = name.strip().lower().replace("&", " and ")
    text = re.sub(r"[/()_,.:;+-]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _alias_map() -> dict[str, str]:
    mapping = dict(_ALIASES)
    for name in _CANONICAL:
        mapping[_normalize(name)] = name
    return mapping


_ALIAS_MAP = _alias_map()


def _shown(value: object) -> str:
    text = value if isinstance(value, str) else repr(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > _NAME_LIMIT:
        return text[: _NAME_LIMIT - 3] + "..."
    return text or "(empty)"


def _problem(code: str, message: str, **extra: object) -> dict:
    problem = {"code": code, "message": message}
    problem.update(extra)
    return problem


def _error(problems: list[dict]) -> dict:
    return {
        "status": "error",
        "error": problems[0]["message"],
        "problems": problems,
    }


def _number_string(value: Decimal) -> str:
    try:
        text = format(value.normalize(), "f")
    except DecimalException:
        text = f"{value:.4f}"
    if text in {"-0", "-0.0"}:
        return "0"
    if len(text) > 32:
        return f"{value.quantize(_EXACT):.4f}"
    return text


def _parse_score(value: object) -> tuple[str, Decimal | None, str | None]:
    """Return ('omit'|'ok'|'bad', score, message)."""
    if value is None:
        return "omit", None, None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return "bad", None, f"score must be a number from 0 to 100 or null, got {_shown(value)}"
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in _UNMEASURED_TEXT:
            return "omit", None, None
        if len(text) > 32 or _PLAIN_SCORE.fullmatch(text) is None:
            return "bad", None, f"score {_shown(text)} is not a number from 0 to 100"
        try:
            score = Decimal(text)
        except DecimalException:
            return "bad", None, f"score {_shown(text)} is not a number from 0 to 100"
        shown = text
    else:
        if value != value or value in (float("inf"), float("-inf")):
            return "bad", None, "score must be a finite number from 0 to 100"
        score = Decimal(str(value))
        shown = _shown(value)
    try:
        in_range = score.is_finite() and Decimal(0) <= score <= Decimal(100)
        if in_range and score == 0:
            score = Decimal(0)
    except DecimalException:
        return "bad", None, f"score {_shown(shown)} is not a number from 0 to 100"
    if not in_range:
        return "bad", None, f"score {_shown(shown)} is outside 0 to 100"
    return "ok", score, None


def _canonical_names() -> str:
    return ", ".join(name for name, _weight in WEIGHTS)


def score_audit(document: object) -> dict:
    """Score an audit envelope. Does not read or write summary.health_score."""
    if not isinstance(document, dict):
        return _error([_problem("invalid_envelope", "audit data must be a JSON object")])

    if "categories" not in document or document.get("categories") is None:
        categories: object = []
    else:
        categories = document["categories"]
    if not isinstance(categories, list):
        return _error([
            _problem(
                "invalid_envelope",
                "categories must be a list of {name, score} objects",
            )
        ])

    problems: list[dict] = []
    measured: dict[str, tuple[Decimal, str]] = {}
    present_unmeasured: dict[str, str] = {}
    seen: set[str] = set()

    for index, item in enumerate(categories):
        where = f"categories[{index}]"
        if not isinstance(item, dict):
            problems.append(_problem(
                "invalid_category",
                f"{where} must be an object with name and score",
                index=index,
            ))
            continue
        raw_name = item.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            problems.append(_problem(
                "invalid_category",
                f"{where} needs a category name",
                index=index,
            ))
            continue
        canonical = _ALIAS_MAP.get(_normalize(raw_name))
        if canonical is None:
            problems.append(_problem(
                "unknown_category",
                (
                    f"Unknown category {_shown(raw_name)}. "
                    f"Expected one of: {_canonical_names()}"
                ),
                index=index,
                name=_shown(raw_name),
            ))
            continue
        if canonical in seen:
            problems.append(_problem(
                "duplicate_category",
                f"{canonical} appears more than once",
                index=index,
                name=canonical,
            ))
            continue
        seen.add(canonical)
        state, score, message = _parse_score(item.get("score"))
        if state == "bad":
            problems.append(_problem(
                "invalid_score",
                f"{canonical}: {message}",
                index=index,
                name=canonical,
            ))
            continue
        if state == "omit" or score is None:
            present_unmeasured[canonical] = raw_name.strip()
        else:
            measured[canonical] = (score, raw_name.strip())

    if problems:
        return _error(problems)

    breakdown: list[dict] = []
    omitted: list[dict] = []
    numerator = Decimal(0)
    denominator = 0

    for name, weight in WEIGHTS:
        if name in measured:
            score, raw_name = measured[name]
            numerator += score * weight
            denominator += weight
            entry = {
                "name": name,
                "weight": weight,
                "measured": True,
                "score": _number_string(score),
            }
            if raw_name != name:
                entry["input_name"] = raw_name
            breakdown.append(entry)
            continue
        if name in present_unmeasured:
            reason = "not measured"
            raw_name = present_unmeasured[name]
        else:
            reason = "not in the audit"
            raw_name = ""
        entry = {
            "name": name,
            "weight": weight,
            "measured": False,
            "score": None,
            "reason": reason,
        }
        if raw_name and raw_name != name:
            entry["input_name"] = raw_name
        breakdown.append(entry)
        omitted.append({"name": name, "weight": weight, "reason": reason})

    measured_weight = denominator
    if measured_weight == 0:
        return {
            "status": "insufficient",
            "health_score": None,
            "health_score_exact": None,
            "coverage_percent": 0,
            "measured_weight": 0,
            "total_weight": TOTAL_WEIGHT,
            "numerator": "0",
            "denominator": 0,
            "omitted": omitted,
            "categories": breakdown,
            "presentation": (
                "No category was measured. Do not print a numeric SEO Health Score."
            ),
        }

    exact = (numerator / Decimal(denominator)).quantize(_EXACT, rounding=ROUND_HALF_UP)
    display = int(
        (numerator / Decimal(denominator)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    coverage = measured_weight * 100 // TOTAL_WEIGHT
    status = "complete" if not omitted else "partial"
    if status == "complete":
        presentation = f"Score {display}/100 covers 100% of the category weight."
    else:
        names = ", ".join(item["name"] for item in omitted)
        presentation = (
            f"Score {display}/100 covers {coverage}% of the category weight. "
            f"Omitted: {names}. Do not present it as a full-audit score."
        )
    return {
        "status": status,
        "health_score": display,
        "health_score_exact": f"{exact:.4f}",
        "coverage_percent": coverage,
        "measured_weight": measured_weight,
        "total_weight": TOTAL_WEIGHT,
        "numerator": _number_string(numerator),
        "denominator": measured_weight,
        "omitted": omitted,
        "categories": breakdown,
        "presentation": presentation,
    }


def apply_score(document: dict, result: dict) -> None:
    """Copy a successful result onto summary. Raises ValueError otherwise."""
    if result.get("status") not in {"complete", "partial", "insufficient"}:
        raise ValueError("refusing to write a result that is not a score")
    summary = document.get("summary")
    if summary is None:
        summary = {}
        document["summary"] = summary
    if not isinstance(summary, dict):
        raise ValueError("summary must be a JSON object")
    summary["health_score"] = result["health_score"]
    summary["health_score_status"] = result["status"]
    summary["health_score_coverage"] = result["coverage_percent"]
    summary["health_score_omitted"] = [item["name"] for item in result["omitted"]]


def _emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _read_document(path: Path) -> tuple[dict | None, dict | None, int]:
    if path.is_dir():
        return None, _error([_problem("io_error", f"not a file: {path}")]), 1
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None, _error([_problem("io_error", f"file not found: {path}")]), 1
    except OSError as exc:
        return None, _error([_problem("io_error", f"could not read {path}: {exc.strerror}")]), 1
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, _error([_problem("invalid_json", f"invalid JSON: {exc.msg}")]), 2
    return document, None, 0


def _atomic_write(path: Path, document: dict) -> None:
    directory = path.parent if str(path.parent) else Path(".")
    fd, tmp_name = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute the SEO Health Score from measured category scores.",
    )
    parser.add_argument("--data", help="Path to audit-data.json")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Store the score on summary in the audit file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for compatibility. Output is always JSON.",
    )
    args = parser.parse_args(argv)

    if not args.data:
        _emit(_error([_problem("invalid_arguments", "--data is required")]))
        return 2

    path = Path(args.data)
    document, failure, code = _read_document(path)
    if failure is not None:
        _emit(failure)
        return code
    assert document is not None

    result = score_audit(document)
    if result.get("status") == "error":
        _emit(result)
        return 2

    if args.write:
        try:
            apply_score(document, result)
            _atomic_write(path, document)
        except ValueError as exc:
            _emit(_error([_problem("invalid_envelope", str(exc))]))
            return 2
        except OSError as exc:
            message = exc.strerror or str(exc)
            _emit(_error([_problem("io_error", f"could not write {path}: {message}")]))
            return 1
        result["wrote"] = str(path)

    _emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
