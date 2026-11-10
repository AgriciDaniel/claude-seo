"""Fail-closed resolution of Google properties for a specific audited site."""

from __future__ import annotations

from urllib.parse import urlsplit


def normalize_site_domain(value: str) -> str:
    """Return the exact hostname represented by a host or URL."""
    text = value.strip()
    parsed = urlsplit(text if "://" in text else f"//{text}")
    if not parsed.hostname:
        raise ValueError(f"Invalid site domain or URL: {value!r}")
    return parsed.hostname.rstrip(".").lower()


def _property_domain(value: str) -> str:
    if value.startswith("sc-domain:"):
        return normalize_site_domain(value[len("sc-domain:"):])
    return normalize_site_domain(value)


def _without_www(host: str) -> str:
    return host[len("www."):] if host.startswith("www.") else host


def _covered_domain(values: object) -> str | None:
    """Return D when a sites entry's ``gsc_property`` is ``sc-domain:D``."""
    prop = values.get("gsc_property") if isinstance(values, dict) else None
    if not isinstance(prop, str) or not prop.startswith("sc-domain:"):
        return None
    try:
        return _property_domain(prop)
    except ValueError:
        return None


def _match_site_entry(sites: dict, host: str) -> list:
    """Return the one sites entry for ``host`` in a list, or an empty list.

    Order: exact host, then the same host with or without ``www.``, then an
    entry whose domain property covers ``host`` as a subdomain. Cover is a
    dot-suffix match, so ``notexample.com`` never matches ``example.com``.
    The most specific covering domain wins, and among entries sharing it the
    one keyed by that domain.
    """
    entries = [(normalize_site_domain(key), values) for key, values in sites.items()]
    matches = [values for key, values in entries if key == host]
    if not matches:
        matches = [
            values for key, values in entries if _without_www(key) == _without_www(host)
        ]
    if len(matches) > 1:
        raise ValueError(f"Multiple sites entries normalize to {host!r}")
    if matches:
        return matches

    covering = [
        (covered, key, values)
        for covered, key, values in (
            (_covered_domain(values), key, values) for key, values in entries
        )
        if covered and host.endswith("." + covered)
    ]
    if not covering:
        return []
    domain = max((covered for covered, _, _ in covering), key=len)
    best = [(key, values) for covered, key, values in covering if covered == domain]
    if len(best) > 1:
        best = [(key, values) for key, values in best if _without_www(key) == domain]
    if len(best) != 1:
        raise ValueError(
            f"Multiple sites entries cover {host!r}; add an entry for that exact host"
        )
    return [best[0][1]]


def resolve_site_property(config: dict, service: str, domain: str) -> str:
    """Resolve a site's GSC or GA4 property without crossing sites.

    ``sites`` maps hostnames to ``gsc_property`` and/or
    ``ga4_property_id``. A key matches its own host with or without a leading
    ``www.``, and an entry whose ``gsc_property`` is ``sc-domain:D`` also
    covers subdomains of D. The legacy single-site fields are used only when
    the requested domain matches the domain of ``default_property``.
    """
    fields = {"gsc": "gsc_property", "ga4": "ga4_property_id"}
    if service not in fields:
        raise ValueError(f"Unsupported Google property service: {service}")
    host = normalize_site_domain(domain)
    sites = config.get("sites") or {}
    if not isinstance(sites, dict):
        raise ValueError("sites must be an object keyed by site domain")

    matches = _match_site_entry(sites, host)
    if matches:
        values = matches[0]
        if not isinstance(values, dict) or not values.get(fields[service]):
            raise ValueError(f"No {fields[service]} configured for site {host!r}")
        return str(values[fields[service]])

    default_property = config.get("default_property")
    if default_property:
        try:
            default_text = str(default_property)
            default_host = _property_domain(default_text)
            is_domain_property = default_text.startswith("sc-domain:")
            matches_default = _without_www(host) == _without_www(default_host) or (
                is_domain_property and host.endswith("." + default_host)
            )
            if matches_default:
                prop = default_property if service == "gsc" else config.get("ga4_property_id")
                if prop:
                    return str(prop)
        except ValueError:
            pass
    raise ValueError(
        f"No site-specific {service.upper()} property configured for {host!r}; "
        "refusing to use a different site's default. Add a matching sites entry."
    )
