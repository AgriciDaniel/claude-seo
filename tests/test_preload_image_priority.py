"""Image preloads can prioritize CSS backgrounds and video poster LCP images."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preload_check import analyse  # noqa: E402


@pytest.mark.parametrize("html", [
    '<link rel="preload" as="image" href="/hero.webp" fetchpriority="high">',
    '<link REL="alternate PRELOAD" AS="IMAGE" href="/hero.webp" FETCHPRIORITY="HIGH">',
    '<link rel=preload as=image imagesrcset="small.webp 400w, large.webp 1200w" imagesizes=100vw fetchpriority=high>',
    '<link rel=preload as=image href=/poster.jpg fetchpriority=high><video poster=/poster.jpg></video>',
])
def test_prioritized_image_preloads_receive_lcp_hint_credit(html):
    result = analyse(html)

    assert result["lcp_resource_hints"] == {"preload_lcp_candidate": True, "fetchpriority_high": 1}
    assert result["score"] == analyse("")["score"] + 25
    assert not any("LCP" in advice for advice in result["recommendations"])


@pytest.mark.parametrize("html, count, candidate", [
    ('<img src=/hero.webp fetchpriority=high>', 1, True),
    ('<script src=/app.js fetchpriority=high></script>', 1, False),
    ('<link rel=preload as=font href=/font.woff2 fetchpriority=high>', 1, False),
    ('<link rel=preload as=script href=/app.js fetchpriority=high>', 1, False),
    ('<link rel=prefetch as=image href=/hero.webp fetchpriority=high>', 1, False),
    ('<link rel=stylesheet as=image href=/hero.webp fetchpriority=high>', 1, False),
    ('<link rel=preload as=image fetchpriority=high>', 1, False),
    ('<link rel=preload as=image href=" " imagesrcset=" " fetchpriority=high>', 1, False),
    ('<link rel=preload as=image href=/hero.webp fetchpriority=" high ">', 0, False),
    ('<video poster=/poster.jpg fetchpriority=high></video>', 0, False),
    ('<picture><source srcset=/hero.webp fetchpriority=high><img src=/hero.jpg></picture>', 0, False),
    ('<div fetchpriority=high>Headline</div>', 0, False),
])
def test_only_supported_resource_hints_count(html, count, candidate):
    result = analyse(html)

    assert result["lcp_resource_hints"] == {"preload_lcp_candidate": candidate, "fetchpriority_high": count}
    assert result["score"] == analyse("")["score"] + (25 if candidate else 0)


def test_background_image_preload_can_complete_an_optimized_page():
    result = analyse('''
        <script type=speculationrules>{"prefetch": [{"urls": ["/next"]}]}</script>
        <link rel=preload as=image href=/background.webp fetchpriority=high>
        <style>.hero { background-image: url(/background.webp); }</style>
        <main class=hero>Welcome</main>
    ''')

    assert result["score"] == 100
    assert result["recommendations"] == []


def test_priority_count_excludes_unsupported_elements_in_a_mixed_page():
    result = analyse('''
        <img src=/hero.webp fetchpriority=high>
        <link rel=preload as=image href=/hero.webp fetchpriority=high>
        <script src=/app.js fetchpriority=high></script>
        <video poster=/poster.jpg fetchpriority=high></video>
        <source srcset=/other.webp fetchpriority=high>
        <div fetchpriority=high>Heading</div>
    ''')

    assert result["lcp_resource_hints"]["fetchpriority_high"] == 3
