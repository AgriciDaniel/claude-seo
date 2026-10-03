/**
 * Plain-text answers for the zero-token commands. Pure.
 */

import { usd } from './verdict'

const SPARK = '▁▂▃▄▅▆▇█'

/** One block character per value, scaled to the largest. */
export function spark(values: readonly number[]): string {
  const top = Math.max(0, ...values)

  return values
    .map(value => (top <= 0 || value <= 0 ? ' ' : SPARK[Math.min(SPARK.length - 1, Math.floor((value / top) * (SPARK.length - 1)))]))
    .join('')
}

type Today = { date?: unknown; total_usd?: unknown; daily_limit_usd?: unknown; remaining_usd?: unknown; calls?: unknown; by_endpoint?: unknown }
type Summary = { daily_totals?: unknown; grand_total_usd?: unknown; total_calls?: unknown; period_days?: unknown }

const n = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0)

/** The last `days` calendar days ending at `today` (YYYY-MM-DD), oldest first. */
export function lastDays(today: string, days: number): string[] {
  const end = new Date(`${today}T00:00:00Z`)

  if (Number.isNaN(end.getTime())) {
    return []
  }

  return Array.from({ length: days }, (_, i) => {
    const day = new Date(end.getTime() - (days - 1 - i) * 86_400_000)

    return day.toISOString().slice(0, 10)
  })
}

/**
 * The /seo-spend answer from `dataforseo_costs.py today` and `summary --days 30`.
 */
export function spendText(today: Today, summary: Summary): string {
  const date = typeof today.date === 'string' ? today.date : ''
  const totals = typeof summary.daily_totals === 'object' && summary.daily_totals !== null ? (summary.daily_totals as Record<string, { total_usd?: unknown; calls?: unknown }>) : {}
  const days = lastDays(date, 30)
  const series = days.map(day => n(totals[day]?.total_usd))
  const sum = (values: readonly number[]) => values.reduce((a, b) => a + b, 0)
  // The same 30 calendar days for the total, the call count and the spark row
  // (the script's own window is "now minus 30 days", which reaches into day 31).
  const monthCalls = sum(days.map(day => n(totals[day]?.calls)))
  const allRows = typeof today.by_endpoint === 'object' && today.by_endpoint !== null ? Object.entries(today.by_endpoint as Record<string, { cost_usd?: unknown; calls?: unknown }>) : []
  // A ledger reset leaves a $0 audit row; it is not a call.
  const resets = n(allRows.find(([endpoint]) => endpoint === '_audit_reset')?.[1].calls)
  const byEndpoint = allRows.filter(([endpoint]) => endpoint !== '_audit_reset')
  const lines = [
    `DataForSEO spend (claude-seo ledger)`,
    `  today   ${usd(n(today.total_usd))} of ${usd(n(today.daily_limit_usd))} cap, ${n(today.calls) - resets} calls, ${usd(n(today.remaining_usd))} left`,
    `  7 days  ${usd(sum(series.slice(-7)))}`,
    `  30 days ${usd(days.length > 0 ? sum(series) : n(summary.grand_total_usd))}, ${days.length > 0 ? monthCalls : n(summary.total_calls)} calls`,
  ]

  if (days.length > 0) {
    lines.push(`  last 30 days  |${spark(series)}|  ${days[0]} to ${days.at(-1)}`)
  }

  if (byEndpoint.length > 0) {
    lines.push('  today by endpoint:')

    for (const [endpoint, row] of byEndpoint.sort((a, b) => n(b[1].cost_usd) - n(a[1].cost_usd)).slice(0, 8)) {
      lines.push(`    ${usd(n(row.cost_usd)).padStart(8)}  ${n(row.calls)}x  ${endpoint}`)
    }
  }

  return lines.join('\n')
}

type Doctor = { ready?: unknown; mode?: unknown; plugin_version?: unknown; python_version?: unknown; browser_ready?: unknown; reasons?: unknown }

/** The /seo-doctor answer from `claude-seo doctor --json`. */
export function doctorText(doctor: Doctor, root: string): string {
  const reasons = Array.isArray(doctor.reasons) ? doctor.reasons.filter((reason): reason is string => typeof reason === 'string') : []
  const lines = [
    `claude-seo ${typeof doctor.plugin_version === 'string' ? doctor.plugin_version : '?'} at ${root}`,
    `  runtime   ${doctor.ready === true ? 'ready' : 'setup required'} (${typeof doctor.mode === 'string' ? doctor.mode : '?'} mode, Python ${typeof doctor.python_version === 'string' ? doctor.python_version : '?'})`,
    `  Chromium  ${doctor.browser_ready === true ? 'ready' : 'not installed'}`,
    ...reasons.map(reason => `  reason    ${reason}`),
  ]

  if (doctor.ready !== true) {
    lines.push(`  fix       run: "${root}/scripts/claude-seo" setup`)
  }

  return lines.join('\n')
}
