"""
Capture screenshots and HTML for studioslow.ru across multiple viewports.
Extracts mobile SEO signals: viewport meta, responsive CSS, tap targets, images, fonts.
"""

import json
import sys
from playwright.sync_api import sync_playwright

URL = "https://studioslow.ru"
OUTPUT_DIR = "/home/user/claude-seo/screenshots/studioslow"

VIEWPORTS = [
    {"name": "desktop", "width": 1920, "height": 1080},
    {"name": "laptop",  "width": 1366, "height": 768},
    {"name": "tablet",  "width": 768,  "height": 1024},
    {"name": "mobile",  "width": 375,  "height": 812},
]

def capture_all():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])

        # ── HTML + signals pass (desktop, full page source) ──────────────────
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.set_extra_http_headers({"Accept-Language": "ru-RU,ru;q=0.9"})
        try:
            page.goto(URL, wait_until="networkidle", timeout=30000)
        except Exception:
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)

        html = page.content()

        # Meta viewport
        viewport_meta = page.eval_on_selector(
            'meta[name="viewport"]',
            "el => el.getAttribute('content')"
        ) if page.query_selector('meta[name="viewport"]') else None

        # Responsive CSS signals
        css_signals = page.evaluate("""() => {
            const sheets = Array.from(document.styleSheets);
            let mediaQueries = [];
            try {
                for (const s of sheets) {
                    try {
                        const rules = Array.from(s.cssRules || []);
                        for (const r of rules) {
                            if (r.type === CSSRule.MEDIA_RULE) {
                                mediaQueries.push(r.conditionText || r.media.mediaText);
                            }
                        }
                    } catch(e) {}
                }
            } catch(e) {}
            return [...new Set(mediaQueries)].slice(0, 30);
        }""")

        # Images: src, alt, width, height, loading
        images = page.evaluate("""() => {
            return Array.from(document.images).slice(0, 40).map(img => ({
                src: img.src,
                alt: img.alt,
                naturalWidth: img.naturalWidth,
                naturalHeight: img.naturalHeight,
                displayWidth: img.width,
                displayHeight: img.height,
                loading: img.getAttribute('loading'),
                srcset: img.getAttribute('srcset') ? true : false,
            }));
        }""")

        # Font sizes of key text elements
        font_sizes = page.evaluate("""() => {
            const tags = ['h1','h2','p','a','button','span','li'];
            const results = {};
            for (const tag of tags) {
                const el = document.querySelector(tag);
                if (el) {
                    const style = window.getComputedStyle(el);
                    results[tag] = {
                        fontSize: style.fontSize,
                        lineHeight: style.lineHeight,
                    };
                }
            }
            return results;
        }""")

        # Tap target check: links/buttons smaller than 48x48
        small_targets = page.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('a, button, [role="button"]'));
            return els.filter(el => {
                const r = el.getBoundingClientRect();
                return (r.width > 0 && r.height > 0) && (r.width < 48 || r.height < 48);
            }).slice(0, 20).map(el => ({
                tag: el.tagName,
                text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0,60),
                width: Math.round(el.getBoundingClientRect().width),
                height: Math.round(el.getBoundingClientRect().height),
            }));
        }""")

        # Interstitials / overlays
        interstitials = page.evaluate("""() => {
            const suspects = Array.from(document.querySelectorAll(
                '[class*="popup"], [class*="modal"], [class*="overlay"], [class*="cookie"], ' +
                '[id*="popup"], [id*="modal"], [id*="overlay"], [id*="cookie"]'
            ));
            return suspects.filter(el => {
                const s = window.getComputedStyle(el);
                return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) > 0;
            }).slice(0, 10).map(el => ({
                tag: el.tagName,
                id: el.id,
                className: el.className.slice(0, 80),
                width: Math.round(el.getBoundingClientRect().width),
                height: Math.round(el.getBoundingClientRect().height),
            }));
        }""")

        # H1 above-the-fold check
        h1_atf = page.evaluate("""() => {
            const h1 = document.querySelector('h1');
            if (!h1) return null;
            const rect = h1.getBoundingClientRect();
            return {
                text: h1.innerText.trim().slice(0, 120),
                top: Math.round(rect.top),
                visible: rect.top < window.innerHeight,
            };
        }""")

        # Primary CTA above the fold
        cta_atf = page.evaluate("""() => {
            const cta = document.querySelector(
                'a[class*="btn"], a[class*="button"], button, a[class*="cta"], .add-to-cart'
            );
            if (!cta) return null;
            const rect = cta.getBoundingClientRect();
            return {
                text: (cta.innerText || '').trim().slice(0, 80),
                top: Math.round(rect.top),
                visible: rect.top < window.innerHeight,
                width: Math.round(rect.width),
                height: Math.round(rect.height),
            };
        }""")

        # Title & meta description
        title = page.title()
        meta_desc = page.eval_on_selector(
            'meta[name="description"]',
            "el => el.getAttribute('content')"
        ) if page.query_selector('meta[name="description"]') else None

        results["signals"] = {
            "viewport_meta": viewport_meta,
            "title": title,
            "meta_description": meta_desc,
            "css_media_queries": css_signals,
            "images_sampled": images,
            "font_sizes": font_sizes,
            "small_tap_targets": small_targets,
            "interstitials": interstitials,
            "h1_above_fold": h1_atf,
            "primary_cta_above_fold": cta_atf,
            "html_snippet": html[:3000],
        }
        page.close()

        # ── Screenshot pass: all viewports ───────────────────────────────────
        for vp in VIEWPORTS:
            pg = browser.new_page(viewport={"width": vp["width"], "height": vp["height"]})
            pg.set_extra_http_headers({"Accept-Language": "ru-RU,ru;q=0.9"})
            try:
                pg.goto(URL, wait_until="networkidle", timeout=30000)
            except Exception:
                pg.goto(URL, wait_until="domcontentloaded", timeout=30000)
            out = f"{OUTPUT_DIR}/{vp['name']}.png"
            pg.screenshot(path=out, full_page=False)
            print(f"Saved {out}", file=sys.stderr)
            pg.close()

        browser.close()

    # Save JSON results
    out_json = f"{OUTPUT_DIR}/signals.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results

if __name__ == "__main__":
    capture_all()
