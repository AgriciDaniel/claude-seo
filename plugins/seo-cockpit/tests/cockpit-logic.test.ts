import { describe, expect, test } from 'claude-code/testing'

import { barRow, htmlPage, rankColor, resample, scoreColor, sparkRow, svgOf, vitalColor, COLORS } from '../hooks/lib/charts'
import { auditModel, gscModel, mapsModel, rankingsModel, spendModel, vitalsModel } from '../hooks/lib/tabs'

const day = (i: number) => new Date(Date.UTC(2026, 6, 3) + i * 86_400_000).toISOString().slice(0, 10)
const GSC_DATE = { property: 'sc-domain:a.com', error: null, rows: Array.from({ length: 60 }, (_, i) => ({ keys: [day(i)], date: day(i), clicks: i < 32 ? 10 : 20, impressions: 100, ctr: 10, position: 10 - i / 10 })) }
const GSC_QUERY = { error: null, rows: [{ keys: ['a'], query: 'a', clicks: 5, impressions: 50, ctr: 10, position: 2 }, { keys: ['b'], query: 'b', clicks: 1, impressions: 90, ctr: 1, position: 7 }] }

describe('chart helpers', () => {
  test('spark rows scale to their own range and invert for positions', () => {
    expect(sparkRow([1, 2, 3], 3)).toBe('▁▅█')
    expect(sparkRow([1, 2, 3], 3, true)).toBe('█▅▁')
    expect(sparkRow([1, null, 3], 3)).toBe('▁ █')
  })

  test('resample averages buckets down to the width', () => {
    expect(resample([1, 3, 5, 7], 2)).toEqual([2, 6])
  })

  test('bars fill to the value', () => {
    expect(barRow(5, 10, 4)).toBe('██░░')
  })

  test('status colors follow the thresholds', () => {
    expect(scoreColor(85)).toBe(COLORS.good)
    expect(scoreColor(40)).toBe(COLORS.poor)
    expect(rankColor(null)).toBe(COLORS.muted)
    expect(rankColor(2)).toBe(COLORS.good)
    expect(vitalColor(3000, 2500, 4000)).toBe(COLORS.warn)
  })

  test('every chart kind makes an SVG well under the size limit', () => {
    const charts = [
      svgOf({ kind: 'line', title: 'L', series: [{ name: 'x', values: Array.from({ length: 90 }, (_, i) => i), color: COLORS.blue }], xLabels: ['a', 'b'], bands: { good: 10, poor: 50 } }),
      svgOf({ kind: 'bars', title: 'B', rows: [{ label: 'x', value: 3, color: COLORS.good }], max: 5 }),
      svgOf({ kind: 'grid', title: 'G', ranks: [[1, null], [5, 30]] }),
    ]

    for (const chart of charts) {
      expect(chart.source.startsWith('<svg')).toBe(true)
      expect(chart.source.length).toBeLessThan(131_072)
    }
  })

  test('the HTML export is self-contained and escapes text', () => {
    const html = htmlPage('T', 'now', [{ heading: '<b>x</b>', source: 's', kpis: [], charts: [], tables: [], notes: [] }])

    expect(html).toContain('&lt;b&gt;x&lt;/b&gt;')
    expect(html).not.toContain('<script')
    expect(html).toContain('prefers-color-scheme:dark')
  })
})

describe('tab models', () => {
  test('Search Console compares the last 28 days with the 28 before', () => {
    const model = gscModel(GSC_DATE, GSC_QUERY, 'sc-domain:a.com', 'now')

    expect(model.kpis[0]).toEqual({ label: 'Clicks, 28 days', value: '560 (+100%)' })
    expect(model.tables[0]?.rows[0]?.[0]).toBe('a')
  })

  test('an API error becomes a message with the fix', () => {
    const model = gscModel({ error: 'no credentials', rows: [] }, null, '', 'now')

    expect(model.error).toBe('no credentials')
    expect(model.notes.join(' ')).toContain('/seo google setup')
  })

  test('Rankings buckets queries and lists striking distance', () => {
    const model = rankingsModel(GSC_DATE, GSC_QUERY, null, 'sc-domain:a.com', 'now')

    expect(model.kpis.find(k => k.label === 'Queries in top 3')?.value).toBe('1')
    expect(model.tables[0]?.rows[0]?.[0]).toBe('b')
  })

  test('Vitals reads p75 against the thresholds', () => {
    const model = vitalsModel({ target: 'https://a.com', metrics: { largest_contentful_paint: { p75_values: [3000, 2400], good_threshold: 2500, poor_threshold: 4000 } }, collection_periods: [] }, 'https://a.com', 'now')

    expect(model.kpis).toEqual([{ label: 'LCP p75', value: '2400 ms good' }])
  })

  test('the audit is sorted weakest first and keeps critical findings', () => {
    const model = auditModel({ summary: { health_score: 60 }, categories: [{ name: 'A', score: 90, findings: [] }, { name: 'B', score: 30, findings: [{ title: 'bad', severity: 'Critical' }] }] }, 'x-audit/audit-data.json', 'now')
    const bars = model.charts[0]

    expect(bars?.kind === 'bars' ? bars.rows.map(r => r.label) : []).toEqual(['B', 'A'])
    expect(model.tables[0]?.rows).toEqual([['Critical', 'B', 'bad']])
  })

  test('Maps computes share of local voice from the grid', () => {
    const model = mapsModel({ keyword: 'k', ranks: [[1, 2], [5, null]] }, 'g.json', 'now')

    expect(model.kpis[0]).toEqual({ label: 'Share of local voice', value: '50%' })
    expect(model.kpis[3]).toEqual({ label: 'Not found', value: '1' })
  })

  test('a missing audit or grid says how to make one', () => {
    expect(auditModel(null, '', 'now').notes.join(' ')).toContain('/seo audit')
    expect(mapsModel(null, '', 'now').notes.join(' ')).toContain('/seo maps grid')
  })

  test('Spend leaves out the reset row', () => {
    const model = spendModel({ date: '2026-10-03', total_usd: 1, daily_limit_usd: 10, by_endpoint: { _audit_reset: { cost_usd: 0 }, x: { cost_usd: 1 } } }, { daily_totals: {} }, 'now')
    const bars = model.charts[1]

    expect(bars?.kind === 'bars' ? bars.rows.map(r => r.label) : []).toEqual(['x'])
  })
})
