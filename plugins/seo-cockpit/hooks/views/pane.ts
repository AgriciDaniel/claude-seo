/**
 * The cockpit pane as an element tree. Pure: register.ts hands in the
 * surface's element constructors and the actions; nothing here touches `$`.
 *
 * Every surface gets text charts (block characters and colored bars). Where
 * the surface draws `Svg` (desktop, and VS Code per the 2.1.288 typings), the
 * charts are drawn as SVG instead.
 */

import type { Elements, RenderElement } from 'claude-code'

import { barRow, endsOf, rankColor, sparkRow, svgOf, type Chart } from '../lib/charts'
import { TABS, type TabId, type TabModel } from '../lib/tabs'

export type Kit = Pick<Elements['terminal'], 'Box' | 'Text' | 'Button'> & Partial<Pick<Elements['terminal'], 'Markdown'>> & { Svg?: Elements['desktop']['Svg'] }

export type PaneState = {
  tab: TabId
  model: TabModel | null
  isLoading: boolean
  /** The last HTML export, as a file path. */
  exported: string | null
}

export type PaneActions = {
  pick: (tab: TabId) => void
  refresh: () => void
  exportHtml: () => void
  close: () => void
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

/** The whole pane: tab buttons, the tab's content, and the actions. */
export function paneView(kit: Kit, state: PaneState, columns: number, actions: PaneActions): RenderElement {
  const { Box, Text, Button } = kit
  const tabs = Box({
    flexDirection: 'row',
    columnGap: 1,
    // A plain button with a hotkey draws as "1: label", so the label carries no key of its own.
    children: TABS.map(tab => Button({ key: `tab-${tab.id}`, label: `${tab.id === state.tab ? '▸ ' : ''}${tab.label}`, hotkey: tab.key, plain: true, onPress: () => actions.pick(tab.id) })),
  })
  const body: RenderElement[] = []
  const model = state.model

  if (state.isLoading) {
    body.push(Text({ dimColor: true, children: ['Loading from claude-seo...'] }))
  } else if (model === null) {
    body.push(Text({ dimColor: true, children: ['Press r to load this view. Nothing is fetched until you ask.'] }))
  } else {
    body.push(Text({ bold: true, children: [model.heading] }), Text({ dimColor: true, children: [cut(`${model.source}  ·  fetched ${model.fetchedAt}`, columns * 2)] }))

    if (model.error !== null) {
      body.push(Text({ color: '#dc2626', children: [cut(model.error, columns * 3)] }))
    }

    if (model.kpis.length > 0) {
      body.push(Box({ flexDirection: 'row', columnGap: 3, children: model.kpis.map(kpi => Text({ children: [`${kpi.label}: `, Text({ bold: true, children: [kpi.value] })] })) }))
    }

    for (const chart of model.charts) {
      body.push(Box({ flexDirection: 'column', marginTop: 1, children: chartView(kit, chart, columns) }))
    }

    for (const table of model.tables) {
      body.push(Box({ flexDirection: 'column', marginTop: 1, children: tableView(kit, table, columns) }))
    }

    body.push(...model.notes.map(note => Text({ dimColor: true, children: [cut(note, columns * 3)] })))
  }

  const footer: RenderElement[] = [
    Button({ key: 'refresh', label: 'Refresh', hotkey: 'r', plain: true, onPress: actions.refresh }),
    Button({ key: 'export', label: 'Export HTML', hotkey: 'e', plain: true, onPress: actions.exportHtml }),
    Button({ key: 'close', label: 'Close', hotkey: 'x', plain: true, onPress: actions.close }),
  ]

  if (state.exported !== null) {
    // A Link takes only https (or http://localhost) and refuses the whole tree otherwise; Markdown links may use file:.
    footer.push(kit.Markdown !== undefined ? kit.Markdown({ text: `[open export](file://${encodeURI(state.exported)})` }) : Text({ dimColor: true, children: [state.exported] }))
  }

  return Box({ flexDirection: 'column', rowGap: 0, children: [tabs, Box({ flexDirection: 'column', marginTop: 1, children: body }), Box({ flexDirection: 'row', columnGap: 2, marginTop: 1, children: footer })] })
}
