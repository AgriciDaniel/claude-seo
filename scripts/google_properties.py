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


def resolve_site_property(config: dict, service: str, domain: str) -> str:
    """Resolve an exact site's GSC or GA4 property without crossing sites.

    ``sites`` maps hostnames to ``gsc_property`` and/or
    ``ga4_property_id``. The legacy single-site fields are used only when the
    requested domain matches the domain of ``default_property``.
    """
    fields = {"gsc": "gsc_property", "ga4": "ga4_property_id"}
    if service not in fields:
        raise ValueError(f"Unsupported Google property service: {service}")
    host = normalize_site_domain(domain)
    sites = config.get("sites") or {}
    if not isinstance(sites, dict):
        raise ValueError("sites must be an object keyed by site domain")

    matches = []
    for configured_domain, values in sites.items():
        if normalize_site_domain(configured_domain) == host:
            matches.append(values)
    if len(matches) > 1:
        raise ValueError(f"Multiple sites entries normalize to {host!r}")
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
            matches_default = host == default_host or (
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
