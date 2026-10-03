/**
 * Charts as data: text rows for the terminal, SVG strings for the desktop and
 * VS Code surfaces, and a self-contained HTML page for export. Pure.
 *
 * SVG text and axes use `currentColor` so a chart reads on light and dark
 * backgrounds; series and status colors are fixed mid-tones that hold on both.
 */

export type Series = { name: string; values: ReadonlyArray<number | null>; color: string }

export type Chart =
  | { kind: 'line'; title: string; series: readonly Series[]; xLabels: readonly [string, string]; invert?: boolean; unit?: string; bands?: { good: number; poor: number } }
  | { kind: 'bars'; title: string; rows: ReadonlyArray<{ label: string; value: number; color: string; text?: string }>; max: number }
  | { kind: 'grid'; title: string; ranks: ReadonlyArray<ReadonlyArray<number | null>> }

export const COLORS = {
  blue: '#3b82f6',
  violet: '#8b5cf6',
  good: '#16a34a',
  warn: '#d97706',
  poor: '#dc2626',
  muted: '#8a8f98',
} as const

/** Green from 80, amber from 50, red below. */
export const scoreColor = (score: number): string => (score >= 80 ? COLORS.good : score >= 50 ? COLORS.warn : COLORS.poor)

/** Local-pack style: top 3 green, 4 to 10 amber, beyond red, absent grey. */
export const rankColor = (rank: number | null): string => (rank === null ? COLORS.muted : rank <= 3 ? COLORS.good : rank <= 10 ? COLORS.warn : COLORS.poor)

/** Good, needs improvement, or poor against a metric's two thresholds. */
export const vitalColor = (value: number, good: number, poor: number): string => (value <= good ? COLORS.good : value <= poor ? COLORS.warn : COLORS.poor)

const SPARK = '▁▂▃▄▅▆▇█'
const escape = (text: string): string => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export const compact = (value: number): string =>
  Math.abs(value) >= 1_000_000 ? `${(value / 1_000_000).toFixed(1)}M` : Math.abs(value) >= 10_000 ? `${Math.round(value / 1000)}k` : Math.abs(value) >= 1000 ? `${(value / 1000).toFixed(1)}k` : `${Math.round(value * 100) / 100}`

/** Squeezes a series to at most `width` points by averaging buckets. */
export function resample(values: ReadonlyArray<number | null>, width: number): Array<number | null> {
  if (values.length <= width) {
    return [...values]
  }

  return Array.from({ length: width }, (_, i) => {
    const bucket = values.slice(Math.floor((i * values.length) / width), Math.floor(((i + 1) * values.length) / width)).filter((v): v is number => v !== null)

    return bucket.length === 0 ? null : bucket.reduce((a, b) => a + b, 0) / bucket.length
  })
}

/** One block character per value between the series' own min and max; gaps stay blank. */
export function sparkRow(values: ReadonlyArray<number | null>, width: number, invert = false): string {
  const points = resample(values, width)
  const present = points.filter((v): v is number => v !== null)
  const low = Math.min(...present)
  const high = Math.max(...present)

  return points
    .map(value => {
      if (value === null) {
        return ' '
      }

      const share = high === low ? 0.5 : (value - low) / (high - low)

      return SPARK[Math.round((invert ? 1 - share : share) * (SPARK.length - 1))] ?? ' '
    })
    .join('')
}

/** A horizontal bar of `width` cells for `value` out of `max`. */
export function barRow(value: number, max: number, width: number): string {
  const cells = max <= 0 ? 0 : Math.max(0, Math.min(width, Math.round((value / max) * width)))

  return '█'.repeat(cells) + '░'.repeat(width - cells)
}

/** First and last present values, for "from ... to ..." labels. */
export function endsOf(values: ReadonlyArray<number | null>): { first: number | null; last: number | null } {
  const present = values.filter((v): v is number => v !== null)

  return { first: present[0] ?? null, last: present.at(-1) ?? null }
}

// ------------------------------------------------------------------- SVG

const W = 560

function lineSvg(chart: Extract<Chart, { kind: 'line' }>): string {
  const height = 170
  const pad = { left: 46, right: 12, top: 24, bottom: 26 }
  const plotW = W - pad.left - pad.right
  const plotH = height - pad.top - pad.bottom
  const all = chart.series.flatMap(s => s.values.filter((v): v is number => v !== null))
  const bandValues = chart.bands === undefined ? [] : [chart.bands.good, chart.bands.poor]
  let low = Math.min(...all, ...bandValues)
  let high = Math.max(...all, ...bandValues)

  if (!Number.isFinite(low) || !Number.isFinite(high)) {
    low = 0
    high = 1
  }

  if (high === low) {
    high = low + 1
  }

  const y = (v: number) => {
    const share = (v - low) / (high - low)

    return pad.top + (chart.invert === true ? share : 1 - share) * plotH
  }

  const longest = Math.max(1, ...chart.series.map(s => s.values.length))
  const x = (i: number) => pad.left + (longest === 1 ? plotW / 2 : (i / (longest - 1)) * plotW)
  const parts: string[] = []

  if (chart.bands !== undefined) {
    const { good, poor } = chart.bands

    parts.push(
      `<rect x="${pad.left}" y="${Math.min(y(good), y(low))}" width="${plotW}" height="${Math.abs(y(good) - y(low))}" fill="${COLORS.good}" opacity="0.10"/>`,
      `<rect x="${pad.left}" y="${Math.min(y(poor), y(good))}" width="${plotW}" height="${Math.abs(y(poor) - y(good))}" fill="${COLORS.warn}" opacity="0.10"/>`,
      `<rect x="${pad.left}" y="${Math.min(y(high), y(poor))}" width="${plotW}" height="${Math.abs(y(high) - y(poor))}" fill="${COLORS.poor}" opacity="0.10"/>`,
      // Labelled threshold lines, so the zones read without a legend.
      `<line x1="${pad.left}" y1="${y(good)}" x2="${pad.left + plotW}" y2="${y(good)}" stroke="${COLORS.good}" stroke-dasharray="4 3"/>`,
      `<text x="${pad.left + plotW - 4}" y="${y(good) - 4}" text-anchor="end" font-size="10" fill="${COLORS.good}">good ${escape(compact(good))}</text>`,
      `<line x1="${pad.left}" y1="${y(poor)}" x2="${pad.left + plotW}" y2="${y(poor)}" stroke="${COLORS.poor}" stroke-dasharray="4 3"/>`,
      `<text x="${pad.left + plotW - 4}" y="${y(poor) + 12}" text-anchor="end" font-size="10" fill="${COLORS.poor}">poor ${escape(compact(poor))}</text>`,
    )
  }

  parts.push(
    `<line x1="${pad.left}" y1="${pad.top + plotH}" x2="${pad.left + plotW}" y2="${pad.top + plotH}" stroke="currentColor" opacity="0.3"/>`,
    `<text x="${pad.left - 6}" y="${y(high) + 4}" text-anchor="end" font-size="10" fill="currentColor" opacity="0.7">${escape(compact(high))}</text>`,
    `<text x="${pad.left - 6}" y="${y(low) + 4}" text-anchor="end" font-size="10" fill="currentColor" opacity="0.7">${escape(compact(low))}</text>`,
    `<text x="${pad.left}" y="${height - 8}" font-size="10" fill="currentColor" opacity="0.7">${escape(chart.xLabels[0])}</text>`,
    `<text x="${pad.left + plotW}" y="${height - 8}" text-anchor="end" font-size="10" fill="currentColor" opacity="0.7">${escape(chart.xLabels[1])}</text>`,
  )

  chart.series.forEach((series, index) => {
    const segments: string[] = []
    let open = false

    series.values.forEach((value, i) => {
      if (value === null) {
        open = false

        return
      }

      segments.push(`${open ? 'L' : 'M'}${x(i).toFixed(1)},${y(value).toFixed(1)}`)
      open = true
    })
    parts.push(`<path d="${segments.join(' ')}" fill="none" stroke="${series.color}" stroke-width="2" stroke-linejoin="round"/>`)
    parts.push(`<text x="${pad.left + index * 150}" y="14" font-size="11" fill="${series.color}">● ${escape(series.name)}</text>`)
  })

  return svgDoc(height, chart.title, parts)
}

function barsSvg(chart: Extract<Chart, { kind: 'bars' }>): string {
  const rowH = 22
  const labelW = 170
  const height = 12 + chart.rows.length * rowH
  const plotW = W - labelW - 70
  const parts = chart.rows.flatMap((row, i) => {
    const y = 8 + i * rowH
    const width = chart.max <= 0 ? 0 : Math.max(0, Math.min(plotW, (row.value / chart.max) * plotW))

    return [
      `<text x="${labelW - 8}" y="${y + 14}" text-anchor="end" font-size="11" fill="currentColor">${escape(row.label.length > 26 ? `${row.label.slice(0, 25)}…` : row.label)}</text>`,
      `<rect x="${labelW}" y="${y + 3}" width="${plotW}" height="14" rx="3" fill="currentColor" opacity="0.08"/>`,
      `<rect x="${labelW}" y="${y + 3}" width="${width.toFixed(1)}" height="14" rx="3" fill="${row.color}"/>`,
      `<text x="${labelW + plotW + 8}" y="${y + 14}" font-size="11" fill="currentColor">${escape(row.text ?? compact(row.value))}</text>`,
    ]
  })

  return svgDoc(height, chart.title, parts)
}

function gridSvg(chart: Extract<Chart, { kind: 'grid' }>): string {
  const size = Math.max(1, chart.ranks.length)
  const cell = Math.min(40, Math.floor(300 / size))
  const height = size * cell + 40
  const parts = chart.ranks.flatMap((row, r) =>
    row.flatMap((rank, c) => [
      `<rect x="${20 + c * cell}" y="${10 + r * cell}" width="${cell - 3}" height="${cell - 3}" rx="4" fill="${rankColor(rank)}"/>`,
      `<text x="${20 + c * cell + (cell - 3) / 2}" y="${10 + r * cell + (cell - 3) / 2 + 4}" text-anchor="middle" font-size="11" fill="#ffffff">${rank === null ? '-' : rank > 20 ? '20+' : rank}</text>`,
    ]),
  )
  const legendY = 10 + size * cell + 18

  parts.push(
    ...[
      ['1-3', COLORS.good],
      ['4-10', COLORS.warn],
      ['11+', COLORS.poor],
      ['not found', COLORS.muted],
    ].map(([label, color], i) => `<rect x="${20 + i * 90}" y="${legendY - 9}" width="10" height="10" rx="2" fill="${color}"/><text x="${34 + i * 90}" y="${legendY}" font-size="11" fill="currentColor">${label}</text>`),
  )

  return svgDoc(height, chart.title, parts)
}

function svgDoc(height: number, title: string, parts: readonly string[]): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${height}" width="${W}" height="${height}" font-family="system-ui, sans-serif" role="img"><title>${escape(title)}</title>${parts.join('')}</svg>`
}

/** The chart as an SVG string (well under the 131,072-character limit for these sizes). */
export function svgOf(chart: Chart): { source: string; height: number } {
  const source = chart.kind === 'line' ? lineSvg(chart) : chart.kind === 'bars' ? barsSvg(chart) : gridSvg(chart)
  const height = Number(/height="(\d+)"/.exec(source)?.[1] ?? 200)

  return { source, height }
}

// ------------------------------------------------------------------- HTML

export type Section = {
  heading: string
  source: string
  kpis: ReadonlyArray<{ label: string; value: string }>
  charts: readonly Chart[]
  tables: ReadonlyArray<{ head: readonly string[]; rows: ReadonlyArray<readonly string[]> }>
  notes: readonly string[]
}

/** A self-contained page (inline CSS and SVG, no scripts), readable in light and dark. */
export function htmlPage(title: string, generated: string, sections: readonly Section[]): string {
  const body = sections
    .map(
      section => `<section><h2>${escape(section.heading)}</h2><p class="src">${escape(section.source)}</p>
${section.kpis.length > 0 ? `<div class="kpis">${section.kpis.map(k => `<div class="kpi"><span>${escape(k.label)}</span><b>${escape(k.value)}</b></div>`).join('')}</div>` : ''}
${section.charts.map(chart => `<figure>${svgOf(chart).source}</figure>`).join('\n')}
${section.tables.map(t => `<table><thead><tr>${t.head.map(h => `<th>${escape(h)}</th>`).join('')}</tr></thead><tbody>${t.rows.map(r => `<tr>${r.map(c => `<td>${escape(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`).join('\n')}
${section.notes.map(n => `<p class="note">${escape(n)}</p>`).join('')}</section>`,
    )
    .join('\n')

  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)}</title>
<style>
:root{--bg:#f7f7f5;--fg:#1d1f23;--card:#ffffff;--line:#e3e3df;--muted:#6b7079}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--fg:#e8e8e6;--card:#1f2228;--line:#30343b;--muted:#9aa0a8}}
*{box-sizing:border-box}body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:760px;margin:0 auto}h1{font-size:24px;margin:0 0 4px}.gen{color:var(--muted);margin:0 0 24px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 16px}
h2{font-size:18px;margin:0}.src{color:var(--muted);font-size:13px;margin:2px 0 12px}
.kpis{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}.kpi{border:1px solid var(--line);border-radius:8px;padding:6px 10px}.kpi span{display:block;color:var(--muted);font-size:12px}.kpi b{font-size:17px}
figure{margin:0 0 12px;color:var(--fg)}figure svg{max-width:100%;height:auto}
table{width:100%;border-collapse:collapse;font-size:13px;margin:0 0 12px}th,td{text-align:left;padding:5px 6px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-weight:600}
.note{color:var(--muted);font-size:13px;margin:4px 0}
</style></head><body><main><h1>${escape(title)}</h1><p class="gen">${escape(generated)}</p>
${body}
</main></body></html>`
}
