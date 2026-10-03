/**
 * The cockpit's tabs as data: each builder turns one claude-seo script's JSON
 * into KPIs, charts and tables. Pure. Every model names its source and when
 * it was fetched, so no number on screen is unlabeled.
 */

import { COLORS, compact, endsOf, scoreColor, vitalColor, type Chart, type Section } from './charts'
import { lastDays } from './format'
import { usd } from './verdict'

export type TabId = 'gsc' | 'rankings' | 'vitals' | 'audit' | 'maps' | 'spend'

export const TABS: ReadonlyArray<{ id: TabId; key: string; label: string }> = [
  { id: 'gsc', key: '1', label: 'Search Console' },
  { id: 'rankings', key: '2', label: 'Rankings' },
  { id: 'vitals', key: '3', label: 'Vitals' },
  { id: 'audit', key: '4', label: 'Audit' },
  { id: 'maps', key: '5', label: 'Maps' },
  { id: 'spend', key: '6', label: 'Spend' },
]

export type TabModel = Section & { error: string | null; fetchedAt: string }

type Json = Record<string, unknown>

const obj = (value: unknown): Json => (typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Json) : {})
const arr = (value: unknown): unknown[] => (Array.isArray(value) ? value : [])
const num = (value: unknown): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null)
const str = (value: unknown): string => (typeof value === 'string' ? value : '')
const sum = (values: ReadonlyArray<number | null>) => values.reduce<number>((a, b) => a + (b ?? 0), 0)
const mean = (values: ReadonlyArray<number | null>) => {
  const present = values.filter((v): v is number => v !== null)

  return present.length === 0 ? null : present.reduce((a, b) => a + b, 0) / present.length
}

const pct = (now: number, before: number): string => (before === 0 ? '' : ` (${now >= before ? '+' : ''}${Math.round(((now - before) / before) * 100)}%)`)

/** A model that says what is missing and how to get it. */
export function emptyModel(heading: string, source: string, fetchedAt: string, error: string, notes: readonly string[] = []): TabModel {
  return { heading, source, fetchedAt, error, kpis: [], charts: [], tables: [], notes }
}

type GscRow = { date: string; query: string; clicks: number; impressions: number; ctr: number; position: number }

function gscRows(raw: unknown): GscRow[] {
  return arr(obj(raw).rows).map(row => {
    const r = obj(row)
    const keys = arr(r.keys).map(str)

    return {
      date: str(r.date) || (keys[0] ?? ''),
      query: str(r.query) || (keys[0] ?? ''),
      clicks: num(r.clicks) ?? 0,
      impressions: num(r.impressions) ?? 0,
      ctr: num(r.ctr) ?? 0,
      position: num(r.position) ?? 0,
    }
  })
}

/** The error a gsc_query.py result carries, or null. */
export const gscError = (raw: unknown): string | null => (str(obj(raw).error) || null)

/**
 * Search Console: 90 days by date, plus the top queries of the last 28 days.
 * Deltas compare the last 28 days with the 28 before them.
 */
export function gscModel(byDate: unknown, byQuery: unknown, property: string, fetchedAt: string): TabModel {
  const heading = 'Search Console'
  const error = gscError(byDate)

  if (error !== null) {
    return emptyModel(heading, `gsc_query.py, ${property || 'default property'}`, fetchedAt, error, ['Set up Google access with /seo google setup, then set "Search Console property" in /config.'])
  }

  const days = gscRows(byDate).filter(row => /^\d{4}-\d{2}-\d{2}$/.test(row.date)).sort((a, b) => a.date.localeCompare(b.date))

  if (days.length === 0) {
    return emptyModel(heading, `gsc_query.py, ${property || 'default property'}`, fetchedAt, 'Search Console returned no rows for the last 90 days.')
  }

  const last28 = days.slice(-28)
  const prev28 = days.slice(-56, -28)
  const clicks = sum(last28.map(d => d.clicks))
  const impressions = sum(last28.map(d => d.impressions))
  const range = obj(obj(byDate).date_range)
  const queries = gscRows(byQuery).slice(0, 10)

  return {
    heading,
    source: `Google Search Console, ${str(obj(byDate).property) || property}, ${str(range.start) || days[0]?.date} to ${str(range.end) || days.at(-1)?.date} (data lags about 2 days)`,
    fetchedAt,
    error: null,
    kpis: [
      { label: 'Clicks, 28 days', value: `${compact(clicks)}${pct(clicks, sum(prev28.map(d => d.clicks)))}` },
      { label: 'Impressions, 28 days', value: `${compact(impressions)}${pct(impressions, sum(prev28.map(d => d.impressions)))}` },
      { label: 'CTR, 28 days', value: impressions === 0 ? 'n/a' : `${((clicks / impressions) * 100).toFixed(1)}%` },
      { label: 'Avg position, 28 days', value: (mean(last28.map(d => d.position)) ?? 0).toFixed(1) },
    ],
    charts: [
      { kind: 'line', title: 'Clicks per day', series: [{ name: 'Clicks', values: days.map(d => d.clicks), color: COLORS.blue }], xLabels: [days[0]?.date ?? '', days.at(-1)?.date ?? ''] },
      { kind: 'line', title: 'Impressions per day', series: [{ name: 'Impressions', values: days.map(d => d.impressions), color: COLORS.violet }], xLabels: [days[0]?.date ?? '', days.at(-1)?.date ?? ''] },
    ],
    tables:
      queries.length === 0
        ? []
        : [{ head: ['Top query, 28 days', 'Clicks', 'Impr.', 'CTR', 'Pos.'], rows: queries.map(q => [q.query, compact(q.clicks), compact(q.impressions), `${q.ctr}%`, q.position.toFixed(1)]) }],
    notes: [],
  }
}

/** Rankings: average position over time (lower is better), where the top queries rank, and drift checks. */
export function rankingsModel(byDate: unknown, byQuery: unknown, drift: unknown, property: string, fetchedAt: string): TabModel {
  const heading = 'Rankings'
  const error = gscError(byDate)

  if (error !== null) {
    return emptyModel(heading, `gsc_query.py, ${property || 'default property'}`, fetchedAt, error, ['Rankings come from Search Console average position, so they need Google access too.'])
  }

  const days = gscRows(byDate).filter(row => /^\d{4}-\d{2}-\d{2}$/.test(row.date)).sort((a, b) => a.date.localeCompare(b.date))
  const queries = gscRows(byQuery)
  const buckets = [
    { label: 'Top 3', test: (p: number) => p <= 3, color: COLORS.good },
    { label: '4 to 10', test: (p: number) => p > 3 && p <= 10, color: COLORS.warn },
    { label: '11 to 20', test: (p: number) => p > 10 && p <= 20, color: COLORS.poor },
    { label: '21+', test: (p: number) => p > 20, color: COLORS.muted },
  ].map(b => ({ label: b.label, value: queries.filter(q => b.test(q.position)).length, color: b.color }))
  const comparisons = arr(obj(drift).comparisons).map(obj).reverse()
  const charts: Chart[] = []

  if (days.length > 0) {
    charts.push({ kind: 'line', title: 'Average position (lower is better)', series: [{ name: 'Avg position', values: days.map(d => d.position), color: COLORS.blue }], xLabels: [days[0]?.date ?? '', days.at(-1)?.date ?? ''], invert: true })
  }

  if (queries.length > 0) {
    charts.push({ kind: 'bars', title: 'Top queries by position band', rows: buckets, max: Math.max(1, ...buckets.map(b => b.value)) })
  }

  if (comparisons.length > 1) {
    charts.push({
      kind: 'line',
      title: 'Drift checks: issues found per comparison',
      series: [
        { name: 'Critical', values: comparisons.map(c => num(c.critical)), color: COLORS.poor },
        { name: 'Warning', values: comparisons.map(c => num(c.warning)), color: COLORS.warn },
      ],
      xLabels: [str(comparisons[0]?.timestamp).slice(0, 10), str(comparisons.at(-1)?.timestamp).slice(0, 10)],
    })
  }

  const striking = queries.filter(q => q.position > 3 && q.position <= 15 && q.impressions > 0).sort((a, b) => b.impressions - a.impressions).slice(0, 8)
  const { first, last } = endsOf(days.map(d => d.position))

  return {
    heading,
    source: `Google Search Console average position, ${property || str(obj(byDate).property) || 'default property'}; drift: claude-seo baselines`,
    fetchedAt,
    error: days.length === 0 && queries.length === 0 ? 'Search Console returned no rows.' : null,
    kpis: [
      { label: 'Avg position, now', value: last === null ? 'n/a' : last.toFixed(1) },
      { label: '90 days ago', value: first === null ? 'n/a' : first.toFixed(1) },
      { label: 'Queries in top 3', value: String(buckets[0]?.value ?? 0) },
      { label: 'Queries tracked', value: String(queries.length) },
    ],
    charts,
    tables: striking.length === 0 ? [] : [{ head: ['Striking distance (pos. 4 to 15)', 'Pos.', 'Impr.', 'Clicks'], rows: striking.map(q => [q.query, q.position.toFixed(1), compact(q.impressions), compact(q.clicks)]) }],
    notes: comparisons.length > 1 ? [] : ['No drift history for this URL yet. Run /seo drift baseline <url> to start tracking on-page changes.'],
  }
}

const VITALS: ReadonlyArray<{ key: string; label: string; unit: string; color: string }> = [
  { key: 'largest_contentful_paint', label: 'LCP', unit: 'ms', color: COLORS.blue },
  { key: 'interaction_to_next_paint', label: 'INP', unit: 'ms', color: COLORS.violet },
  { key: 'cumulative_layout_shift', label: 'CLS', unit: '', color: COLORS.blue },
]

/** Core Web Vitals: CrUX p75 per collection period, against Google's good and poor thresholds. */
export function vitalsModel(raw: unknown, target: string, fetchedAt: string): TabModel {
  const heading = 'Core Web Vitals'
  const data = obj(raw)
  const error = str(data.error)

  if (error !== '') {
    return emptyModel(heading, `crux_history.py, ${target}`, fetchedAt, error, ['CrUX needs a Google API key and enough real-user traffic for the URL or origin.'])
  }

  const periods = arr(data.collection_periods).map(obj)
  const metrics = obj(data.metrics)
  const xLabels: [string, string] = [str(periods[0]?.last), str(periods.at(-1)?.last)]
  const charts: Chart[] = []
  const kpis: Array<{ label: string; value: string }> = []

  for (const vital of VITALS) {
    const metric = obj(metrics[vital.key])
    const values = arr(metric.p75_values).map(num)
    const good = num(metric.good_threshold)
    const poor = num(metric.poor_threshold)
    const { last } = endsOf(values)

    if (values.length === 0 || good === null || poor === null) {
      continue
    }

    const shown = (v: number) => (vital.unit === 'ms' ? `${Math.round(v)} ms` : v.toFixed(2))
    const verdict = last === null ? '' : last <= good ? ' good' : last <= poor ? ' needs work' : ' poor'

    kpis.push({ label: `${vital.label} p75`, value: last === null ? 'n/a' : `${shown(last)}${verdict}` })
    charts.push({ kind: 'line', title: `${vital.label} p75 (good ≤ ${shown(good)}, poor > ${shown(poor)})`, series: [{ name: vital.label, values, color: last === null ? vital.color : vitalColor(last, good, poor) }], xLabels, bands: { good, poor }, unit: vital.unit })
  }

  return {
    heading,
    source: `Chrome UX Report history, ${str(data.target) || target}, ${str(data.form_factor) || 'ALL'} devices, ${periods.length} weekly periods`,
    fetchedAt,
    error: charts.length === 0 ? 'CrUX has no Core Web Vitals history for this target.' : null,
    kpis,
    charts,
    tables: [],
    notes: ['p75 is the value 75% of real visits beat. Thresholds: LCP 2.5 s, INP 200 ms, CLS 0.1.'],
  }
}

/** The audit scorecard from audit-data.json. */
export function auditModel(raw: unknown, path: string, fetchedAt: string): TabModel {
  const heading = 'Audit scorecard'
  const data = obj(raw)
  const summary = obj(data.summary)
  const score = num(summary.health_score)
  const categories = arr(data.categories)
    .map(obj)
    .flatMap(c => {
      const value = num(c.score)

      return value === null ? [] : [{ label: str(c.name), value, color: scoreColor(value), text: `${value}/100` }]
    })

  if (score === null && categories.length === 0) {
    return emptyModel(heading, path || 'audit-data.json', fetchedAt, 'No audit found in this folder.', ['Run /seo audit <url>; its audit-data.json appears here.'])
  }

  const severity = (finding: Json) => str(finding.severity)
  const findings = arr(data.categories)
    .map(obj)
    .flatMap(c => arr(c.findings).map(obj).map(f => ({ category: str(c.name), title: str(f.title), severity: severity(f) })))
    .filter(f => f.severity === 'Critical' || f.severity === 'High')
    .slice(0, 8)
  const wins = arr(summary.quick_wins).map(w => (typeof w === 'string' ? w : str(obj(w).title))).filter(Boolean).slice(0, 5)

  return {
    heading,
    source: `${path}${str(summary.business_type) ? `, business type: ${str(summary.business_type)}` : ''}`,
    fetchedAt,
    error: null,
    kpis: [
      { label: 'Health score', value: score === null ? 'n/a' : `${score}/100` },
      { label: 'Categories', value: String(categories.length) },
      { label: 'Critical and high findings', value: String(findings.length) },
    ],
    charts: categories.length === 0 ? [] : [{ kind: 'bars', title: 'Score by category', rows: [...categories].sort((a, b) => a.value - b.value), max: 100 }],
    tables: findings.length === 0 ? [] : [{ head: ['Severity', 'Category', 'Finding'], rows: findings.map(f => [f.severity, f.category, f.title]) }],
    notes: wins.map(w => `Quick win: ${w}`),
  }
}

/** The Maps geo-grid from a saved geo-grid-*.json (skills/seo-maps, step 8). */
export function mapsModel(raw: unknown, path: string, fetchedAt: string): TabModel {
  const heading = 'Maps geo-grid'
  const data = obj(raw)
  const ranks = arr(data.ranks).map(row => arr(row).map(cell => (typeof cell === 'number' && Number.isFinite(cell) ? cell : null)))

  if (ranks.length === 0) {
    return emptyModel(heading, path || 'geo-grid-*.json', fetchedAt, 'No saved geo-grid in this folder.', ['Run /seo maps grid <keyword> <location> (uses DataForSEO credits); the grid is saved as <business>-maps/geo-grid-<keyword>-<date>.json.'])
  }

  const cells = ranks.flat()
  const found = cells.filter((c): c is number => c !== null)
  const top3 = found.filter(c => c <= 3).length
  const solv = num(data.solv) ?? (cells.length === 0 ? 0 : Math.round((top3 / cells.length) * 100))

  return {
    heading,
    source: `${path}: "${str(data.keyword)}" near ${str(data.location) || 'the business'}, ${str(data.date)}, ${ranks.length}x${ranks[0]?.length ?? 0} grid${num(data.radius_km) === null ? '' : `, ${num(data.radius_km)} km radius`}`,
    fetchedAt,
    error: null,
    kpis: [
      { label: 'Share of local voice', value: `${solv}%` },
      { label: 'Points in top 3', value: `${top3} of ${cells.length}` },
      { label: 'Average rank where found', value: found.length === 0 ? 'n/a' : (found.reduce((a, b) => a + b, 0) / found.length).toFixed(1) },
      { label: 'Not found', value: String(cells.length - found.length) },
    ],
    charts: [{ kind: 'grid', title: `Rank by grid point: ${str(data.keyword)}`, ranks }],
    tables: [],
    notes: [`${str(data.business) || 'The business'}; north is up.`],
  }
}

/** Spend: DataForSEO per day for 30 days, and today by endpoint, from the claude-seo ledger. */
export function spendModel(today: unknown, summary: unknown, fetchedAt: string): TabModel {
  const t = obj(today)
  const totals = obj(obj(summary).daily_totals)
  const days = lastDays(str(t.date), 30)
  const series = days.map(day => num(obj(totals[day]).total_usd) ?? 0)
  const byEndpoint = Object.entries(obj(t.by_endpoint))
    .filter(([endpoint]) => endpoint !== '_audit_reset')
    .map(([endpoint, row]) => ({ label: endpoint, value: num(obj(row).cost_usd) ?? 0 }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
  const limit = num(t.daily_limit_usd) ?? 0
  const spent = num(t.total_usd) ?? 0

  return {
    heading: 'Spend',
    source: `claude-seo DataForSEO ledger, ${days[0] ?? ''} to ${days.at(-1) ?? ''}`,
    fetchedAt,
    error: null,
    kpis: [
      { label: 'Today', value: `${usd(spent)} of ${usd(limit)}` },
      { label: '7 days', value: usd(series.slice(-7).reduce((a, b) => a + b, 0)) },
      { label: '30 days', value: usd(series.reduce((a, b) => a + b, 0)) },
    ],
    charts: [
      { kind: 'line', title: 'DataForSEO spend per day (USD)', series: [{ name: 'Spend', values: series, color: COLORS.blue }], xLabels: [days[0] ?? '', days.at(-1) ?? ''] },
      ...(byEndpoint.length === 0
        ? []
        : [{ kind: 'bars' as const, title: 'Today by endpoint', rows: byEndpoint.map(row => ({ ...row, color: limit > 0 && spent / limit > 0.8 ? COLORS.warn : COLORS.blue, text: usd(row.value) })), max: Math.max(...byEndpoint.map(row => row.value)) }]),
    ],
    tables: [],
    notes: ['Image generation and other providers keep their own ledgers and are not shown here.'],
  }
}

