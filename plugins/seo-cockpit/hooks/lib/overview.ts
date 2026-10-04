/**
 * The cockpit's Overview: which site it is about, and one line per source.
 * Pure. Built from the tab models, so the Overview and the detail views never
 * disagree.
 */

import type { TabId, TabModel } from './tabs'

/** The Overview's rows, in order of what a person checks first. */
export const ROWS: ReadonlyArray<{ id: TabId; label: string; key: string }> = [
  { id: 'audit', label: 'Audit', key: '1' },
  { id: 'vitals', label: 'Vitals', key: '2' },
  { id: 'gsc', label: 'Search', key: '3' },
  { id: 'rankings', label: 'Rankings', key: '4' },
  { id: 'maps', label: 'Maps', key: '5' },
  { id: 'spend', label: 'Spend', key: '6' },
]

export type RowState = 'loading' | 'ok' | 'missing' | 'error'

export type Row = { id: TabId; label: string; key: string; state: RowState; line: string }

/** The host of a URL, `sc-domain:` property or bare domain; null when there is none. */
export function hostOf(value: string): string | null {
  const text = value.trim().replace(/^sc-domain:/i, '')

  if (text === '') {
    return null
  }

  try {
    const host = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`).hostname.toLowerCase()

    return host.includes('.') ? host.replace(/^www\./, '') : null
  } catch {
    return null
  }
}

/** The site an audit folder is about: `meta.site` in its audit-data.json, else the folder name. */
export function siteOfAudit(folder: string, data: unknown): string | null {
  const meta = (data as { meta?: { site?: unknown } } | null)?.meta
  const fromData = typeof meta?.site === 'string' ? hostOf(meta.site) : null

  return fromData ?? hostOf(folder.replace(/-audit$/, ''))
}

/**
 * The target, most specific first: what the person chose for this folder
 * (typed in the pane, or `/seo-cockpit <site>`), the site this folder's audit
 * is about, then the default from /config. The caller falls back to the last
 * site used when all three are empty.
 */
export function chooseTarget(setting: string, typed: string | null, inferred: string | null): { host: string | null; source: 'typed' | 'folder' | 'setting' | null } {
  const chosen = typed === null ? null : hostOf(typed)

  if (chosen !== null) {
    return { host: chosen, source: 'typed' }
  }

  if (inferred !== null) {
    return { host: inferred, source: 'folder' }
  }

  const fallback = hostOf(setting)

  return fallback === null ? { host: null, source: null } : { host: fallback, source: 'setting' }
}

const kpi = (model: TabModel, label: string): string | undefined => model.kpis.find(k => k.label === label)?.value

const short = (text: string, max = 60): string => (text.length <= max ? text : `${text.slice(0, max - 1)}…`)

/** Turns a script's error into a short reason a person can act on. */
function reasonOf(id: TabId, error: string): string {
  if (/permission denied/i.test(error)) {
    return 'no Search Console access'
  }

  if (/not set up|runtime is not ready/i.test(error)) {
    return 'claude-seo runtime not set up: run /seo setup'
  }

  if (/credential|api key|google access|oauth/i.test(error)) {
    return 'Google not connected: run /seo google setup'
  }

  if (/no saved geo-grid/i.test(error)) {
    return 'no grid yet (/seo maps grid)'
  }

  if (/no audit found/i.test(error)) {
    return 'no audit yet (/seo audit)'
  }

  if (/no url to measure/i.test(error)) {
    return 'needs a site: type it above'
  }

  return short(error)
}

/** One Overview line for a source. */
export function rowOf(id: TabId, model: TabModel | undefined, isLoading: boolean): Row {
  const base = ROWS.find(row => row.id === id) ?? { id, label: id, key: '' }

  if (model === undefined) {
    return { ...base, state: isLoading ? 'loading' : 'missing', line: isLoading ? 'checking…' : 'not loaded' }
  }

  if (model.error !== null) {
    const isMissing = /no audit found|no saved geo-grid|no url to measure|not connected|permission denied|not set up/i.test(model.error)

    return { ...base, state: isMissing ? 'missing' : 'error', line: reasonOf(id, model.error) }
  }

  const parts: Array<string | undefined> = (() => {
    switch (id) {
      case 'audit': {
        const bars = model.charts[0]
        const weakest = bars?.kind === 'bars' ? bars.rows[0] : undefined

        // "Schema / Structured Data" reads as "Schema" on one line.
        const name = weakest?.label.split(/\s[/(]/)[0]

        return [kpi(model, 'Health score'), weakest === undefined ? undefined : `weakest ${name} ${weakest.value}`]
      }
      case 'vitals': {
        // The verdict first, so a narrow pane keeps it: "good · LCP 703ms · INP 48ms · CLS 0.00".
        const values = model.kpis.map(k => `${k.label.replace(' p75', '')} ${k.value.replace(/ (good|needs work|poor)$/, '').replace(' ms', 'ms')}`)
        const verdict = model.kpis.some(k => / poor$/.test(k.value)) ? 'poor' : model.kpis.some(k => / needs work$/.test(k.value)) ? 'needs work' : 'good'

        return [verdict, ...values]
      }
      case 'gsc':
        return [`clicks ${kpi(model, 'Clicks, 28 days') ?? '?'}`, `impr. ${kpi(model, 'Impressions, 28 days') ?? '?'}`]
      case 'rankings':
        return [`avg pos ${kpi(model, 'Avg position, now') ?? '?'}`, `was ${kpi(model, '90 days ago') ?? '?'}`, `top 3: ${kpi(model, 'Queries in top 3') ?? '0'}`]
      case 'maps':
        return [`SoLV ${kpi(model, 'Share of local voice') ?? '?'}`, `${kpi(model, 'Points in top 3') ?? '?'} in top 3`]
      case 'spend':
        return [`today ${(kpi(model, 'Today') ?? '?').split(' of ')[0]}`, `30 days ${kpi(model, '30 days') ?? '?'}`]
    }
  })()

  return { ...base, state: 'ok', line: parts.filter((p): p is string => p !== undefined).join(' · ') }
}

/** The one-line status under the prompt, from what loaded; undefined when nothing did. */
export function statusLine(host: string | null, rows: readonly Row[]): string | undefined {
  const audit = rows.find(r => r.id === 'audit' && r.state === 'ok')
  const vitals = rows.find(r => r.id === 'vitals' && r.state === 'ok')

  if (host === null || (audit === undefined && vitals === undefined)) {
    return undefined
  }

  const score = audit?.line.split(' · ')[0]
  const cwv = vitals === undefined ? undefined : /^(poor|needs work)/.test(vitals.line) ? 'CWV needs work' : 'CWV good'

  // The engine prefixes the plugin's name; the line itself starts with the site.
  return [host, score === undefined ? undefined : `audit ${score}`, cwv].filter(Boolean).join(' · ')
}
