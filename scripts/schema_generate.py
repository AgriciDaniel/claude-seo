#!/usr/bin/env python3
"""
JSON-LD generators for the four high-leverage v2 Schema.org types:

  - Reservation       (FoodEstablishmentReservation, etc.)
  - OrderAction       (an "Order this" potentialAction)
  - DiscussionForumPosting  (community/forum content — promoted to
                              first-class rich result in 2024)
  - ProfilePage       (author/entity pages with sameAs + knowsAbout
                       for AI citation entity graphs)

Per the v2 gap analysis (May 2026):
  - Internal hypothesis: Reservation + potentialAction markup may help
    machine readability for restaurant booking flows. This is not confirmed
    Google guidance for AI Mode.
  - The "Discussions and forums" SERP feature is live; sites that mark
    up community content with DiscussionForumPosting are eligible.
  - ProfilePage with sameAs / knowsAbout is the cheapest entity-graph
    builder for AI citation correlation.

Usage::

    python scripts/schema_generate.py reservation \\
        --provider "Marea NYC" --start 2026-06-04T19:30:00-04:00 \\
        --party-size 4 --reservation-id RX-12345

    python scripts/schema_generate.py order \\
        --merchant "Acme Pizza" --order-url https://acme.example/order

    python scripts/schema_generate.py discussion \\
        --headline "How do you score INP correctly?" \\
        --author "Sara Park" \\
        --url https://forum.example.com/t/123 \\
        --date 2026-05-12T14:00:00Z

    python scripts/schema_generate.py profile \\
        --name "Daniel Agrici" \\
        --url https://agricidaniel.com/about \\
        --same-as https://github.com/AgriciDaniel \\
                  https://twitter.com/agricidaniel \\
        --knows-about "SEO" "Schema markup" "Core Web Vitals"

All generators emit JSON-LD with ``@context: https://schema.org`` and
absolute URLs, the same conventions Google's Rich Results Test enforces.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def reservation(
    provider: str,
    start: str,
    *,
    end: Optional[str] = None,
    party_size: Optional[int] = None,
    reservation_id: Optional[str] = None,
    reservation_for_name: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    kind: str = "FoodEstablishmentReservation",
) -> dict:
    """Build a Reservation JSON-LD block. Defaults to FoodEstablishment."""
    payload: dict = {
        "@context": "https://schema.org",
        "@type": kind,
        "reservationStatus": "https://schema.org/ReservationConfirmed",
        "provider": {"@type": "Organization", "name": provider},
        "reservationFor": {
            "@type": "FoodEstablishment" if kind == "FoodEstablishmentReservation"
                     else "Place",
            "name": reservation_for_name or provider,
        },
        "startTime": start,
    }
    if end:
        payload["endTime"] = end
    if party_size is not None:
        payload["partySize"] = int(party_size)
    if reservation_id:
        payload["reservationId"] = reservation_id
    if customer_name or customer_email:
        person: dict = {"@type": "Person"}
        if customer_name:
            person["name"] = customer_name
        if customer_email:
            person["email"] = customer_email
        payload["underName"] = person
    return payload


def order_action(
    merchant: str,
    *,
    order_url: str,
    name: str = "Order online",
    accepted_payment_method: Optional[list[str]] = None,
    delivery_method: Optional[list[str]] = None,
) -> dict:
    """Build an OrderAction potentialAction block.

    Attach the result to a Product or Service via:

        {"@type": "Product", "potentialAction": <this dict>}
    """
    payload: dict = {
        "@context": "https://schema.org",
        "@type": "OrderAction",
        "name": name,
        "target": {
            "@type": "EntryPoint",
            "urlTemplate": order_url,
            "inLanguage": "en-US",
            "actionPlatform": [
                "https://schema.org/DesktopWebPlatform",
                "https://schema.org/MobileWebPlatform",
            ],
        },
        "deliveryMethod": delivery_method or [
            "https://schema.org/OnSitePickup",
            "https://schema.org/ParcelService",
        ],
        "priceSpecification": {
            "@type": "PriceSpecification",
            "eligibleTransactionVolume": {
                "@type": "PriceSpecification",
                "minPrice": 0,
                "priceCurrency": "USD",
            },
        },
        "merchant": {"@type": "Organization", "name": merchant},
    }
    if accepted_payment_method:
        payload["acceptedPaymentMethod"] = [
            {"@type": "PaymentMethod", "name": m}
            for m in accepted_payment_method
        ]
    return payload


def discussion(
    headline: str,
    author: str,
    *,
    url: str,
    date_published: str,
    text: Optional[str] = None,
    date_modified: Optional[str] = None,
    interaction_count: Optional[dict] = None,
    comment_count: Optional[int] = None,
) -> dict:
    """Build a DiscussionForumPosting JSON-LD block."""
    payload: dict = {
        "@context": "https://schema.org",
        "@type": "DiscussionForumPosting",
        "headline": headline,
        "author": {"@type": "Person", "name": author},
        "datePublished": date_published,
        "url": url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }
    if text:
        payload["text"] = text
    if date_modified:
        payload["dateModified"] = date_modified
    if comment_count is not None:
        payload["commentCount"] = int(comment_count)
    if interaction_count:
        payload["interactionStatistic"] = [
            {
                "@type": "InteractionCounter",
                "interactionType": f"https://schema.org/{k}",
                "userInteractionCount": int(v),
            }
            for k, v in interaction_count.items()
        ]
    return payload


def profile(
    name: str,
    *,
    url: str,
    description: Optional[str] = None,
    same_as: Optional[list[str]] = None,
    knows_about: Optional[list[str]] = None,
    works_for: Optional[str] = None,
    image: Optional[str] = None,
    job_title: Optional[str] = None,
) -> dict:
    """Build a ProfilePage JSON-LD block.

    sameAs + knowsAbout is the entity-graph helper recommended by the
    v2 gap analysis for AI citation correlation. Wikipedia, GitHub,
    LinkedIn, and ORCID URLs in sameAs disambiguate the person across
    knowledge graphs.
    """
    person: dict = {"@type": "Person", "name": name, "url": url}
    if description:
        person["description"] = description
    if same_as:
        person["sameAs"] = list(same_as)
    if knows_about:
        person["knowsAbout"] = list(knows_about)
    if works_for:
        person["worksFor"] = {"@type": "Organization", "name": works_for}
    if image:
        person["image"] = image
    if job_title:
        person["jobTitle"] = job_title

    return {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "mainEntity": person,
        "url": url,
    }


def _strip_nones(payload: dict) -> dict:
    """Recursively remove keys with value None — keeps the JSON-LD output
    tight without us writing manual ``if x is not None`` guards above."""
    if isinstance(payload, dict):
        return {k: _strip_nones(v) for k, v in payload.items() if v is not None}
    if isinstance(payload, list):
        return [_strip_nones(v) for v in payload]
    return payload


def _print(payload: dict, args) -> int:
    cleaned = _strip_nones(payload)
    output = json.dumps(cleaned, indent=args.indent, ensure_ascii=False)
    if args.script_tag:
        print('<script type="application/ld+json">')
        print(output)
        print("</script>")
    else:
        print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Schema.org JSON-LD generators for v2 high-leverage types."
    )
    parser.add_argument(
        "--indent", type=int, default=2,
        help="JSON indentation (default 2).",
    )
    parser.add_argument(
        "--script-tag", action="store_true",
        help="Wrap output in <script type=application/ld+json> for pasting.",
    )
    sub = parser.add_subparsers(dest="kind", required=True)

    res = sub.add_parser("reservation",
                         help="FoodEstablishmentReservation et al.")
    res.add_argument("--provider", required=True)
    res.add_argument("--start", required=True, help="ISO 8601 startTime.")
    res.add_argument("--end")
    res.add_argument("--party-size", type=int)
    res.add_argument("--reservation-id")
    res.add_argument("--reservation-for-name")
    res.add_argument("--customer-name")
    res.add_argument("--customer-email")
    res.add_argument(
        "--reservation-kind", dest="reservation_kind",
        default="FoodEstablishmentReservation",
        choices=(
            "FoodEstablishmentReservation", "LodgingReservation",
            "RentalCarReservation", "TaxiReservation", "EventReservation",
            "TrainReservation", "FlightReservation",
        ),
    )

    ord_p = sub.add_parser("order", help="OrderAction (potentialAction).")
    ord_p.add_argument("--merchant", required=True)
    ord_p.add_argument("--order-url", required=True)
    ord_p.add_argument("--name", default="Order online")
    ord_p.add_argument("--accepted-payment-method", nargs="*", default=None)
    ord_p.add_argument("--delivery-method", nargs="*", default=None)

    disc = sub.add_parser("discussion", help="DiscussionForumPosting.")
    disc.add_argument("--headline", required=True)
    disc.add_argument("--author", required=True)
    disc.add_argument("--url", required=True)
    disc.add_argument("--date", dest="date_published", required=True)
    disc.add_argument("--text")
    disc.add_argument("--date-modified")
    disc.add_argument("--comment-count", type=int)
    disc.add_argument(
        "--likes", type=int, dest="likes", default=None,
        help="LikeAction count (interactionStatistic).",
    )

    prof = sub.add_parser("profile", help="ProfilePage with sameAs / knowsAbout.")
    prof.add_argument("--name", required=True)
    prof.add_argument("--url", required=True)
    prof.add_argument("--description")
    prof.add_argument("--same-as", nargs="*", default=None)
    prof.add_argument("--knows-about", nargs="*", default=None)
    prof.add_argument("--works-for")
    prof.add_argument("--image")
    prof.add_argument("--job-title")

    args = parser.parse_args()

    if args.kind == "reservation":
        payload = reservation(
            args.provider, args.start, end=args.end, party_size=args.party_size,
            reservation_id=args.reservation_id,
            reservation_for_name=args.reservation_for_name,
            customer_name=args.customer_name, customer_email=args.customer_email,
            kind=args.reservation_kind,
        )
    elif args.kind == "order":
        payload = order_action(
            args.merchant, order_url=args.order_url, name=args.name,
            accepted_payment_method=args.accepted_payment_method,
            delivery_method=args.delivery_method,
        )
    elif args.kind == "discussion":
        ic: dict | None = {"LikeAction": args.likes} if args.likes else None
        payload = discussion(
            args.headline, args.author, url=args.url,
            date_published=args.date_published,
            text=args.text, date_modified=args.date_modified,
            interaction_count=ic, comment_count=args.comment_count,
        )
    elif args.kind == "profile":
        payload = profile(
            args.name, url=args.url, description=args.description,
            same_as=args.same_as, knows_about=args.knows_about,
            works_for=args.works_for, image=args.image,
            job_title=args.job_title,
        )
    else:  # pragma: no cover — argparse rejects unknown sub-commands
        parser.error(f"Unknown kind {args.kind!r}")
        return 2

    return _print(payload, args)


if __name__ == "__main__":
    sys.exit(main())
