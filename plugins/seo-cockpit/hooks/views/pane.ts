/**
 * The cockpit pane as an element tree. Pure: register.ts hands in the
 * surface's element constructors and the actions; nothing here touches `$`.
 *
 * One Overview (a line per source, in the order a person checks them) and one
 * detail view per source. Sized to the pane's own width: an inline pane in a
 * narrow terminal gets the same content in fewer columns, never a wrapped row
 * of controls. The first row holds no controls, leaving the engine's close
 * mark at the right edge clear.
 *
 * Charts are text (block characters and colored bars) everywhere; where the
 * surface draws `Svg` (desktop, and VS Code per the 2.1.288 typings), the
 * detail view draws them as SVG instead.
 */

import type { Elements, RenderElement } from 'claude-code'

import { barRow, endsOf, rankColor, sparkRow, svgOf, COLORS, type Chart } from '../lib/charts'
import { rowOf, ROWS, type Row } from '../lib/overview'
import type { TabId, TabModel } from '../lib/tabs'

export type Kit = Pick<Elements['terminal'], 'Box' | 'Text' | 'Button'> &
  Partial<Pick<Elements['terminal'], 'Markdown' | 'Input'>> & { Svg?: Elements['desktop']['Svg'] }

export type PaneState = {
  /** The Overview, or one source's detail. */
  view: 'overview' | TabId
  models: Partial<Record<TabId, TabModel>>
  loading: ReadonlySet<TabId>
  /** The site the cockpit is about, and where that came from. */
  host: string | null
  hostSource: 'setting' | 'typed' | 'folder' | 'last' | null
  /** The last HTML export, as a file path. */
  exported: string | null
}

export type PaneActions = {
  open: (tab: TabId) => void
  back: () => void
  refresh: () => void
  exportHtml: () => void
  setTarget: (value: string) => void
}

const cut = (text: string, width: number): string => (text.length <= width ? text : `${text.slice(0, Math.max(0, width - 1))}…`)
const pad = (text: string, width: number): string => cut(text, width).padEnd(width)

function textChart(kit: Kit, chart: Chart, columns: number): RenderElement[] {
  const { Box, Text } = kit
  const title = Text({ bold: true, children: [cut(chart.title, columns)] })

  if (chart.kind === 'line') {
    const width = Math.max(10, Math.min(90, columns - 30))
    const rows = chart.series.map(series => {
      const { first, last } = endsOf(series.values)
      const ends = first === null || last === null ? 'no data' : `${Math.round(first * 100) / 100} to ${Math.round(last * 100) / 100}`

      return Box({ flexDirection: 'row', columnGap: 1, children: [Text({ color: series.color, children: [sparkRow(series.values, width, chart.invert === true)] }), Text({ dimColor: true, children: [cut(`${series.name} ${ends}`, 28)] })] })
    })

    return [title, ...rows, Text({ dimColor: true, children: [cut(`${chart.xLabels[0]}${' '.repeat(Math.max(1, width - chart.xLabels[0].length - chart.xLabels[1].length))}${chart.xLabels[1]}`, columns)] })]
  }

  if (chart.kind === 'bars') {
    const labelW = Math.min(28, Math.max(8, ...chart.rows.map(row => row.label.length)))
    const barW = Math.max(8, Math.min(40, columns - labelW - 14))

    return [
      title,
      ...chart.rows.map(row =>
        Box({ flexDirection: 'row', columnGap: 1, children: [Text({ children: [pad(row.label, labelW)] }), Text({ color: row.color, children: [barRow(row.value, chart.max, barW)] }), Text({ children: [row.text ?? String(row.value)] })] }),
      ),
    ]
  }

  return [
    title,
    ...chart.ranks.map((row, r) =>
      Box({ key: `grid-${r}`, flexDirection: 'row', children: row.map(rank => Text({ color: rankColor(rank), children: [rank === null ? ' -- ' : ` ${String(Math.min(rank, 99)).padStart(2)} `] })) }),
    ),
    Text({ dimColor: true, children: ['1-3 green, 4-10 amber, 11+ red, -- not found; north is up'] }),
  ]
}

function chartView(kit: Kit, chart: Chart, columns: number): RenderElement[] {
  if (kit.Svg !== undefined) {
    const { source, height } = svgOf(chart)
    const width = Math.min(560, Math.max(280, columns * 7))

    return [kit.Svg({ source, alt: chart.title, width, height: Math.round((height * width) / 560) })]
  }

  return textChart(kit, chart, columns)
}

function tableView(kit: Kit, table: TabModel['tables'][number], columns: number): RenderElement[] {
  const widths = table.head.map((head, i) => Math.max(head.length, ...table.rows.map(row => (row[i] ?? '').length)))
  const first = Math.max(12, columns - widths.slice(1).reduce((a, b) => a + b + 2, 0) - 2)
  const fit = widths.map((w, i) => (i === 0 ? Math.min(w, first) : w))
  // Numbers right-aligned, words left-aligned.
  const isNumeric = (i: number) => table.rows.every(row => /^[\d.,%$+\-kM ]*$/.test(row[i] ?? ''))
  const line = (cells: readonly string[]) => cells.map((cell, i) => (i === 0 ? pad(cell, fit[0] ?? 12) : isNumeric(i) ? cell.padStart(fit[i] ?? 4) : pad(cell, fit[i] ?? 4))).join('  ')

  return [kit.Text({ dimColor: true, children: [cut(line(table.head), columns)] }), ...table.rows.map(row => kit.Text({ children: [cut(line(row), columns)] }))]
}

const MARK: Record<Row['state'], { mark: string; color?: string }> = {
  ok: { mark: '●', color: COLORS.good },
  loading: { mark: '…' },
  missing: { mark: '○', color: COLORS.muted },
  error: { mark: '!', color: COLORS.poor },
}

/** Keys work only while the pane holds focus; say how to get it otherwise. */
function footer(kit: Kit, state: PaneState, isFocused: boolean, actions: PaneActions, extra: RenderElement[] = []): RenderElement {
  const { Box, Text, Button } = kit
  const children: RenderElement[] = isFocused
    ? [...extra, Button({ key: 'refresh', label: 'Refresh', hotkey: 'r', plain: true, onPress: actions.refresh }), Button({ key: 'export', label: 'Export', hotkey: 'e', plain: true, onPress: actions.exportHtml })]
    : [Text({ dimColor: true, children: ['ctrl+x tab to use the keys'] })]

  if (state.exported !== null && kit.Markdown !== undefined) {
    // A Link takes only https (or http://localhost) and refuses the whole tree otherwise; Markdown links may use file:.
    children.push(kit.Markdown({ text: `[open export](file://${encodeURI(state.exported)})` }))
  }

  return Box({ flexDirection: 'row', columnGap: 2, marginTop: 1, children })
}

/** The Overview: which site, then one line per source; missing data stays visible with its fix. */
export function overviewView(kit: Kit, state: PaneState, columns: number, isFocused: boolean, actions: PaneActions): RenderElement {
  const { Box, Text, Button } = kit
  const where = { setting: 'default', typed: 'chosen here', folder: 'from this folder', last: 'last used', none: '' }[state.hostSource ?? 'none']
  const children: RenderElement[] = [
    // Row 1 carries no controls: the engine draws its close mark at the right edge.
    Text({ children: [Text({ bold: true, children: [cut(state.host ?? 'No site yet', Math.max(10, columns - 24))] }), Text({ dimColor: true, children: [where === '' ? '' : `  ${where}`] })] }),
  ]

  // No site, or only the last one used elsewhere: offer the field to set this folder's own.
  if ((state.host === null || state.hostSource === 'last') && kit.Input !== undefined) {
    children.push(kit.Input({ key: 'target', label: 'Site', placeholder: state.host ?? 'example.com', submitLabel: 'go', ...(state.host === null && { autoFocus: true }), onSubmit: value => actions.setTarget(value) }))
  }

  const labelWidth = Math.max(...ROWS.map(row => row.label.length))

  for (const row of ROWS.map(r => rowOf(r.id, state.models[r.id], state.loading.has(r.id)))) {
    const { mark } = MARK[row.state]
    // The hotkey draws as "1: " before a plain label; keep the whole line inside the pane.
    const label = cut(`${mark} ${row.label.padEnd(labelWidth)}  ${row.line}`, Math.max(12, columns - 4))

    children.push(Button({ key: `row-${row.id}`, label, hotkey: row.key, plain: true, onPress: () => actions.open(row.id) }))
  }

  children.push(footer(kit, state, isFocused, actions))

  return Box({ flexDirection: 'column', children })
}

/** One source in detail: its numbers, charts and tables, with a way back. */
export function detailView(kit: Kit, state: PaneState, tab: TabId, columns: number, isFocused: boolean, actions: PaneActions): RenderElement {
  const { Box, Text, Button } = kit
  const model = state.models[tab]
  const label = ROWS.find(row => row.id === tab)?.label ?? tab
  const body: RenderElement[] = [Text({ children: [Text({ bold: true, children: [model?.heading ?? label] })] })]

  if (model === undefined) {
    body.push(Text({ dimColor: true, children: [state.loading.has(tab) ? 'checking…' : 'not loaded yet: press r'] }))
  } else {
    body.push(Text({ dimColor: true, children: [cut(`${model.source} · ${model.fetchedAt}`, columns)] }))

    if (model.error !== null) {
      body.push(Text({ color: COLORS.poor, children: [cut(model.error, columns * 3)] }))
    }

    for (const kpi of model.kpis) {
      body.push(Text({ children: [`${kpi.label}: `, Text({ bold: true, children: [kpi.value] })] }))
    }

    for (const chart of model.charts) {
      body.push(Box({ flexDirection: 'column', marginTop: 1, children: chartView(kit, chart, columns) }))
    }

    for (const table of model.tables) {
      body.push(Box({ flexDirection: 'column', marginTop: 1, children: tableView(kit, table, columns) }))
    }

    body.push(...model.notes.map(note => Text({ dimColor: true, children: [cut(note, columns * 3)] })))
  }

  const back = Button({ key: 'back', label: 'Back', hotkey: 'b', plain: true, onPress: actions.back })

  return Box({ flexDirection: 'column', children: [...body, footer(kit, state, isFocused, actions, isFocused ? [back] : [])] })
}

/** The whole pane for its current view. */
export function paneView(kit: Kit, state: PaneState, columns: number, isFocused: boolean, actions: PaneActions): RenderElement {
  return state.view === 'overview' ? overviewView(kit, state, columns, isFocused, actions) : detailView(kit, state, state.view, columns, isFocused, actions)
}
