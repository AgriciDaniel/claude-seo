# SEO Drift Comparison Rules

17 rules across 3 severity levels. Each rule compares a specific SEO element
between the stored baseline and the current page state.

---

## CRITICAL (Immediate Action Required)

These changes typically cause measurable traffic loss within days.

### Rule 1: Schema/JSON-LD Completely Removed
- **Compare**: Baseline `schema` array has items, current is empty
- **Threshold**: Any schema present before, none now
- **Action**: Restore structured data immediately. Rich results will be lost within hours.
- **Cross-ref**: `/seo schema <url>`

### Rule 2: Canonical URL Changed
- **Compare**: Baseline `canonical` vs current `canonical`
- **Threshold**: Different non-null values (after normalization)
- **Action**: Verify the new canonical is intentional. Incorrect canonicals redirect ranking signals to wrong page.
- **Cross-ref**: `/seo technical <url>`

### Rule 3: Canonical URL Removed
- **Compare**: Baseline `canonical` was set, current is `null`
- **Threshold**: Had value, now missing
- **Action**: Restore canonical tag. Google will guess, often incorrectly for pages with query parameters.
- **Cross-ref**: `/seo technical <url>`

### Rule 4: Noindex Directive Added
- **Compare**: Baseline `meta_robots` did not contain "noindex", current does
- **Threshold**: "noindex" substring now present (case-insensitive)
- **Action**: If unintentional, remove immediately. Page will be dropped from index within days.
- **Cross-ref**: `/seo technical <url>`

### Rule 5: H1 Tag Removed Entirely
- **Compare**: Baseline `h1` had entries, current is empty
- **Threshold**: One or more H1s before, zero now
- **Action**: Restore H1 heading. Primary page topic signal for search engines.
- **Cross-ref**: `/seo content <url>`

### Rule 6: H1 Text Changed Significantly
- **Compare**: First H1 in baseline vs first H1 in current, SequenceMatcher ratio
- **Threshold**: Similarity ratio < 0.5 (>50% different)
- **Action**: Verify the H1 change aligns with target keyword strategy.
- **Cross-ref**: `/seo content <url>`

### Rule 7: Title Tag Removed Entirely
- **Compare**: Baseline `title` was set, current is `null` or empty
- **Threshold**: Had value, now missing
- **Action**: Restore title tag immediately. Google will auto-generate one, often poorly.
- **Cross-ref**: `/seo page <url>`

### Rule 8: HTTP Status Code Changed to Error
- **Compare**: Baseline `status_code` was 2xx, current is 4xx or 5xx
- **Threshold**: Status code class changed from success to client/server error
- **Action**: Investigate server error or missing page. Rankings will drop within days.
- **Cross-ref**: `/seo technical <url>`

---

## WARNING (Investigate Within 1 Week)

These changes may impact rankings or CTR but are sometimes intentional.

### Rule 9: Title Text Changed
- **Compare**: Baseline `title` vs current `title` (trimmed)
- **Threshold**: Strings differ (case-sensitive, whitespace-normalized)
- **Action**: Verify new title includes target keywords. Monitor CTR in GSC over 2 weeks.
- **Cross-ref**: `/seo page <url>`

### Rule 10: Meta Description Changed
- **Compare**: Baseline `meta_description` vs current `meta_description`
- **Threshold**: Strings differ (trimmed)
- **Action**: Verify new description includes call-to-action and target keywords. Monitor CTR.
- **Cross-ref**: `/seo page <url>`

### Rule 11: Core Web Vitals Metric Regressed >20%
- **Compare**: Each CWV metric p75 value (LCP, INP, CLS) baseline vs current
- **Threshold**: Current value is >20% worse than baseline (higher for LCP/INP, higher for CLS)
- **Action**: Investigate performance regression. Check recent code changes or third-party scripts.
- **Cross-ref**: `/seo technical <url>`

### Rule 12: CWV Performance Score Dropped 10+ Points
- **Compare**: Lighthouse performance score baseline vs current
- **Threshold**: Drop of 10 or more points (e.g., 85 to 74)
- **Action**: Run full PageSpeed analysis to identify new bottlenecks.
- **Cross-ref**: `/seo google psi <url>`

### Rule 13: OG Tags Removed
- **Compare**: Baseline `open_graph` had entries, current is empty
- **Threshold**: One or more OG tags before, none now
- **Action**: Restore OG tags. Social sharing will show generic/missing previews.
- **Cross-ref**: `/seo page <url>`

### Rule 14: Schema/JSON-LD Content Modified
- **Compare**: Baseline `schema_hash` vs current `schema_hash`
- **Threshold**: Hash differs AND schema still exists (removal is Rule 1)
- **Action**: Validate modified schema. Check for type changes, removed properties, or new validation errors.
- **Cross-ref**: `/seo schema <url>`

---

## INFO (Awareness Only)

These are tracked for completeness. Often positive or neutral changes.

### Rule 15: New Schema/JSON-LD Added
- **Compare**: Baseline `schema` was empty, current has items
- **Threshold**: No schema before, schema now present
- **Action**: Positive change. Validate the new schema with `/seo schema <url>`.
- **Cross-ref**: `/seo schema <url>`

### Rule 16: H2 Structure Changed
- **Compare**: Baseline `h2` array vs current `h2` array
- **Threshold**: Different number of H2s, or different H2 text values
- **Action**: Review heading hierarchy. Ensure content sections still align with target topics.
- **Cross-ref**: `/seo content <url>`

### Rule 17: Content Hash Changed
- **Compare**: Baseline `html_hash` vs current `html_hash`
- **Threshold**: Hash differs (catch-all for any body content change)
- **Action**: General content change detected. Review if no other rules triggered to understand what changed.
- **Cross-ref**: `/seo page <url>`
