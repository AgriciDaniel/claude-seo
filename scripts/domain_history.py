#!/usr/bin/env python3
"""
Expired-domain heritage check.

Compares a domain's registration age against the topical fingerprint
of its current content. A site that was registered 18 years ago for
veterinary services and now reads as a high-volume crypto signal hub
is the canonical "expired-domain abuse" pattern under current QRG
§4.6.7.

Approach
========
1. WHOIS lookup via the system ``whois`` binary (no extra Python dep).
   Falls back to a ``socket``-based query against IANA referral chain
   if ``whois`` is unavailable.
2. Parse the creation date from the WHOIS response.
3. Compute heritage signals:
     - ``years_registered``
     - ``last_significant_renewal`` (best-effort: last "updated:" date)
4. Optional ``--topic`` flag accepts the current detected topic. If
   the topic differs from what was registered for (heuristic — see
   notes), flag as a potential expired-domain abuse risk.

This script does NOT make the topical comparison itself — that requires
fetching the current site, classifying it, and comparing against the
Wayback Machine's earliest snapshot. The expensive cross-reference is
delegated to the ``seo-content`` skill which orchestrates it.

CLI::

    python scripts/domain_history.py example.com
    python scripts/domain_history.py example.com --json
    python scripts/domain_history.py example.com --topic crypto-signals --baseline-topic veterinary

Output (JSON)::

    {
      "domain": "example.com",
      "whois_source": "whois-binary|fallback",
      "created":           "ISO-8601 date or null",
      "updated":           "ISO-8601 date or null",
      "expires":           "ISO-8601 date or null",
      "registrar":         "string or null",
      "years_registered":  float or null,
      "topical_shift":     true|false|null,
      "current_topic":     "string or null",
      "baseline_topic":    "string or null",
      "risk":              "low|medium|high|unknown",
      "notes":             ["…"]
    }
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional


_DATE_LABELS = {
    "created": (
        "creation date", "created on", "registered on", "registered",
        "domain registration date", "registry creation date",
    ),
    "updated": (
        "updated date", "last updated", "last modified",
        "domain last updated", "registry updated",
    ),
    "expires": (
        "expiration date", "registry expiry date", "expires on",
        "registrar registration expiration date",
    ),
}

_REGISTRAR_LABELS = ("registrar", "registrant organization")


def _shell_whois(domain: str) -> Optional[str]:
    """Run the system whois binary if available. Returns raw output or None."""
    binary = shutil.which("whois")
    if not binary:
        return None
    try:
        result = subprocess.run(
            [binary, domain],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except subprocess.TimeoutExpired:
        return None
    return None


def _socket_whois(domain: str) -> Optional[str]:
    """Fallback: ask IANA for the authoritative whois server, then ask that
    server for the domain record. Pure stdlib, no extra dependency."""
    try:
        with socket.create_connection(("whois.iana.org", 43), timeout=10) as sock:
            sock.sendall(f"{domain}\r\n".encode("ascii"))
            iana_resp = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                iana_resp += chunk
    except OSError:
        return None

    iana_text = iana_resp.decode("utf-8", errors="replace")
    m = re.search(r"^\s*refer:\s*(\S+)\s*$", iana_text, re.MULTILINE | re.IGNORECASE)
    if not m:
        # IANA returned a direct answer (.arpa, etc.)
        return iana_text

    referral = m.group(1).strip()
    try:
        with socket.create_connection((referral, 43), timeout=10) as sock:
            sock.sendall(f"{domain}\r\n".encode("ascii"))
            buf = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
    except OSError:
        return None
    return buf.decode("utf-8", errors="replace")


def _parse_date(value: str) -> Optional[str]:
    """Best-effort ISO-8601 normalisation."""
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _extract(field_labels: tuple[str, ...], text: str) -> Optional[str]:
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip().lower() in field_labels:
            value = value.strip()
            if value:
                return value
    return None


def lookup(domain: str) -> dict:
    raw = _shell_whois(domain)
    source = "whois-binary"
    if raw is None:
        raw = _socket_whois(domain)
        source = "fallback"
    if raw is None:
        return {
            "domain": domain,
            "whois_source": None,
            "created": None,
            "updated": None,
            "expires": None,
            "registrar": None,
            "years_registered": None,
            "notes": ["whois unavailable — install the 'whois' system package "
                      "or check egress on TCP/43"],
        }

    created_raw = _extract(_DATE_LABELS["created"], raw)
    updated_raw = _extract(_DATE_LABELS["updated"], raw)
    expires_raw = _extract(_DATE_LABELS["expires"], raw)
    created = _parse_date(created_raw) if created_raw else None
    updated = _parse_date(updated_raw) if updated_raw else None
    expires = _parse_date(expires_raw) if expires_raw else None
    registrar = _extract(_REGISTRAR_LABELS, raw)

    years = None
    if created:
        delta = datetime.now(timezone.utc).date() - datetime.fromisoformat(created).date()
        years = round(delta.days / 365.25, 2)

    return {
        "domain": domain,
        "whois_source": source,
        "created": created,
        "updated": updated,
        "expires": expires,
        "registrar": registrar,
        "years_registered": years,
        "notes": [],
    }


def assess_risk(
    record: dict,
    current_topic: Optional[str] = None,
    baseline_topic: Optional[str] = None,
) -> dict:
    """Combine WHOIS heritage with optional topical signals to produce a
    high/medium/low/unknown risk label aligned to QRG §4.6.7."""
    result = dict(record)
    result["current_topic"] = current_topic
    result["baseline_topic"] = baseline_topic
    result["topical_shift"] = None
    result["risk"] = "unknown"

    notes = list(record.get("notes") or [])

    if current_topic and baseline_topic:
        same = current_topic.strip().lower() == baseline_topic.strip().lower()
        result["topical_shift"] = not same

    years = record.get("years_registered")
    shift = result["topical_shift"]

    if years is None:
        result["risk"] = "unknown"
        notes.append("no creation date in whois response")
    elif years < 2 and shift is True:
        result["risk"] = "high"
        notes.append("fresh registration with declared topical shift")
    elif years >= 5 and shift is True:
        result["risk"] = "high"
        notes.append("old registration + topical drift = classic expired-domain abuse pattern")
    elif shift is True:
        result["risk"] = "medium"
        notes.append("topical drift detected at moderate registration age")
    elif years >= 1 and shift is False:
        result["risk"] = "low"
    elif years is not None and shift is None:
        result["risk"] = "unknown"
        notes.append("supply --baseline-topic to enable shift detection")

    result["notes"] = notes
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Expired-domain heritage check (current QRG §4.6.7)."
    )
    parser.add_argument("domain")
    parser.add_argument("--topic", help="Current detected topic (free text).")
    parser.add_argument("--baseline-topic",
                        help="Topic at first archive (free text).")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    record = lookup(args.domain)
    result = assess_risk(record, args.topic, args.baseline_topic)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Domain:           {result['domain']}")
        print(f"WHOIS source:     {result['whois_source']}")
        print(f"Created:          {result['created']}")
        print(f"Updated:          {result['updated']}")
        print(f"Expires:          {result['expires']}")
        print(f"Registrar:        {result['registrar']}")
        print(f"Years registered: {result['years_registered']}")
        print(f"Topic now:        {result['current_topic']}")
        print(f"Topic baseline:   {result['baseline_topic']}")
        print(f"Topical shift:    {result['topical_shift']}")
        print(f"Risk:             {result['risk']}")
        if result["notes"]:
            print("Notes:")
            for note in result["notes"]:
                print(f"  - {note}")

    return 0 if result["risk"] in ("low", "unknown") else 1


if __name__ == "__main__":
    sys.exit(main())
