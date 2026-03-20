/**
 * Capture screenshots and extract mobile SEO signals for studioslow.ru
 * Uses Node.js Playwright (already installed at /opt/node22/lib/node_modules/playwright)
 */

const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const URL = 'https://studioslow.ru';
const OUTPUT_DIR = '/home/user/claude-seo/screenshots/studioslow';

const VIEWPORTS = [
  { name: 'desktop', width: 1920, height: 1080 },
  { name: 'laptop',  width: 1366, height: 768  },
  { name: 'tablet',  width: 768,  height: 1024 },
  { name: 'mobile',  width: 375,  height: 812  },
];

async function safePg(browser, vp) {
  const pg = await browser.newPage({
    viewport: { width: vp.width, height: vp.height },
  });
  await pg.setExtraHTTPHeaders({ 'Accept-Language': 'ru-RU,ru;q=0.9' });
  try {
    await pg.goto(URL, { waitUntil: 'domcontentloaded', timeout: 40000 });
  } catch (e) {
    console.error('goto failed:', e.message);
  }
  // Wait for layout settle without waiting for fonts
  await pg.waitForTimeout(2000);
  return pg;
}

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const browser = await chromium.launch({
    args: ['--no-sandbox', '--disable-web-security'],
  });
  const results = {};

  // ── Signal extraction at desktop width ───────────────────────────────────
  const sigPage = await safePg(browser, { width: 1920, height: 1080 });

  const html = await sigPage.content();

  const viewportMeta = await sigPage.$eval(
    'meta[name="viewport"]',
    el => el.getAttribute('content')
  ).catch(() => null);

  const cssMediaQueries = await sigPage.evaluate(() => {
    const seen = new Set();
    try {
      for (const sheet of document.styleSheets) {
        try {
          for (const rule of sheet.cssRules) {
            if (rule.type === CSSRule.MEDIA_RULE) {
              seen.add(rule.conditionText || rule.media.mediaText);
            }
          }
        } catch (_) {}
      }
    } catch (_) {}
    return [...seen].slice(0, 40);
  });

  const images = await sigPage.evaluate(() =>
    Array.from(document.images).slice(0, 40).map(img => ({
      src: img.src,
      alt: img.alt || null,
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
      displayWidth: img.width,
      displayHeight: img.height,
      loading: img.getAttribute('loading'),
      hasSrcset: !!img.getAttribute('srcset'),
    }))
  );

  const fontSizes = await sigPage.evaluate(() => {
    const tags = ['h1', 'h2', 'h3', 'p', 'a', 'button', 'span', 'li', 'nav'];
    const out = {};
    for (const tag of tags) {
      const el = document.querySelector(tag);
      if (el) {
        const s = window.getComputedStyle(el);
        out[tag] = { fontSize: s.fontSize, lineHeight: s.lineHeight };
      }
    }
    return out;
  });

  const smallTapTargets = await sigPage.evaluate(() =>
    Array.from(document.querySelectorAll('a, button, [role="button"]'))
      .filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (r.width < 48 || r.height < 48);
      })
      .slice(0, 25)
      .map(el => ({
        tag: el.tagName,
        text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 60),
        href: el.href || null,
        width: Math.round(el.getBoundingClientRect().width),
        height: Math.round(el.getBoundingClientRect().height),
      }))
  );

  const interstitials = await sigPage.evaluate(() =>
    Array.from(document.querySelectorAll(
      '[class*="popup"], [class*="modal"], [class*="overlay"], [class*="cookie"],' +
      '[id*="popup"], [id*="modal"], [id*="overlay"], [id*="cookie"]'
    ))
      .filter(el => {
        const s = window.getComputedStyle(el);
        return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) > 0;
      })
      .slice(0, 10)
      .map(el => ({
        tag: el.tagName,
        id: el.id,
        className: el.className.slice(0, 100),
        rect: {
          width: Math.round(el.getBoundingClientRect().width),
          height: Math.round(el.getBoundingClientRect().height),
          top: Math.round(el.getBoundingClientRect().top),
        },
      }))
  );

  const h1AboveFold = await sigPage.evaluate(() => {
    const h1 = document.querySelector('h1');
    if (!h1) return null;
    const r = h1.getBoundingClientRect();
    return { text: h1.innerText.trim().slice(0, 120), top: Math.round(r.top), visibleDesktop: r.top < window.innerHeight };
  });

  const primaryCta = await sigPage.evaluate(() => {
    const sel = 'a[class*="btn"], a[class*="button"], button[type="submit"], .add-to-cart, [class*="cart"]';
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {
      tag: el.tagName,
      text: (el.innerText || '').trim().slice(0, 80),
      width: Math.round(r.width),
      height: Math.round(r.height),
      top: Math.round(r.top),
      visibleDesktop: r.top < window.innerHeight,
    };
  });

  const title = await sigPage.title();
  const metaDesc = await sigPage.$eval(
    'meta[name="description"]', el => el.getAttribute('content')
  ).catch(() => null);

  const canonicalUrl = await sigPage.$eval(
    'link[rel="canonical"]', el => el.getAttribute('href')
  ).catch(() => null);

  const robotsMeta = await sigPage.$eval(
    'meta[name="robots"]', el => el.getAttribute('content')
  ).catch(() => null);

  const ogTags = await sigPage.evaluate(() => {
    const out = {};
    document.querySelectorAll('meta[property^="og:"]').forEach(el => {
      out[el.getAttribute('property')] = el.getAttribute('content');
    });
    return out;
  });

  results.signals = {
    viewport_meta: viewportMeta,
    title,
    meta_description: metaDesc,
    canonical_url: canonicalUrl,
    robots_meta: robotsMeta,
    og_tags: ogTags,
    css_media_queries: cssMediaQueries,
    images_sampled: images,
    font_sizes: fontSizes,
    small_tap_targets: smallTapTargets,
    interstitials,
    h1_above_fold: h1AboveFold,
    primary_cta_above_fold: primaryCta,
    html_head_snippet: html.slice(0, 4000),
  };

  await sigPage.close();

  // ── Screenshot pass across viewports ─────────────────────────────────────
  for (const vp of VIEWPORTS) {
    const pg = await safePg(browser, vp);
    const outPath = path.join(OUTPUT_DIR, `${vp.name}.png`);
    try {
      await pg.screenshot({ path: outPath, fullPage: false, timeout: 60000 });
      console.error(`Saved ${outPath}`);
    } catch (e) {
      console.error(`Screenshot failed for ${vp.name}: ${e.message}`);
    }
    await pg.close();
  }

  // Mobile full-page scroll
  const mobilePg = await safePg(browser, { width: 375, height: 812 });
  try {
    await mobilePg.screenshot({
      path: path.join(OUTPUT_DIR, 'mobile_full.png'),
      fullPage: true,
      timeout: 60000,
    });
    console.error('Saved mobile_full.png');
  } catch (e) {
    console.error(`mobile_full screenshot failed: ${e.message}`);
  }
  await mobilePg.close();

  await browser.close();

  const jsonPath = path.join(OUTPUT_DIR, 'signals.json');
  fs.writeFileSync(jsonPath, JSON.stringify(results, null, 2), 'utf8');
  console.log(JSON.stringify(results, null, 2));
}

main().catch(e => { console.error(e); process.exit(1); });
