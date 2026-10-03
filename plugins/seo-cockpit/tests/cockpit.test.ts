import { describe, expect, mock, test } from 'claude-code/testing'

import { command, worldOf } from './fixtures/world'

const PANE = { plugin: 'seo-cockpit', component: 'Pane' as const, requestId: 'seo-cockpit', viewport: { columns: 160, rows: 50 }, props: { title: 'SEO Cockpit', isFocused: true, bodyColumns: 110, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 40 }, view: {} } }

describe('cockpit', () => {
  test('/seo-cockpit opens the pane, which fetches nothing until asked', async ($, on) => {
    const world = worldOf(on)
    const opened: string[] = []

    on('ui.open', ($, e) => {
      opened.push(`${e.id}${e.focus === true ? ' focused' : ''}`)

      return { value: { isPlaced: true } } as never
    })
    on('store.get', () => ({ value: undefined }))
    on('session.cwd', () => ({ value: '/work' }))
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)

    const result = await $.command.run(command('seo-cockpit'))
    const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })

    expect(opened).toEqual(['seo-cockpit focused'])
    expect(result.text).toContain('pane open')
    expect(await ui.find({ type: 'Text', text: /Press r to load/ })).toBeDefined()
    expect(world.runs).toEqual([])
  })

  test('with no pane on screen, it writes the HTML dashboard instead', async ($, on) => {
    worldOf(on)

    const written: string[] = []

    on('ui.open', () => ({ value: { isPlaced: false, reason: 'no pane here' } }) as never)
    on('session.cwd', () => ({ value: '/work' }))
    on('fs.write', ($, e) => {
      written.push(e.path)

      return { value: undefined }
    })

    const result = await $.command.run(command('seo-cockpit'))

    expect(result.text).toContain('no pane on this screen (no pane here)')
    expect(written.length).toBe(1)
    expect(written[0]).toMatch(/^\/work\/seo-cockpit-.*\.html$/)
  })

  test('charts are text in the terminal and SVG on the desktop', async ($, on) => {
    const day = (i: number) => new Date(Date.UTC(2026, 6, 3) + i * 86_400_000).toISOString().slice(0, 10)
    const gsc = { property: 'sc-domain:a.com', error: null, rows: Array.from({ length: 60 }, (_, i) => ({ keys: [day(i)], date: day(i), query: 'q', clicks: i, impressions: 10 * i, ctr: 1, position: 5 })) }

    // runtime.py run <script> ...: the fixture keys on the subcommand, `run`.
    worldOf(on, { scripts: { run: { stdout: gsc } } })
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    on('session.cwd', () => ({ value: '/work' }))
    on('store.get', () => ({ value: undefined }))
    on('store.set', () => ({ value: undefined }))
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)
    mock.clock(on)

    await $.command.run(command('seo-cockpit'))

    const terminal = await $.ui.mount({ ...PANE, surface: 'terminal' })

    await terminal.press({ key: 'refresh' })
    expect(await terminal.find({ type: 'Text', text: /Clicks per day/ })).toBeDefined()
    expect(await terminal.find({ type: 'Svg' })).toBeUndefined()
    await terminal.unmount()

    const desktop = await $.ui.mount({ ...PANE, surface: 'desktop' })

    expect(await desktop.find({ type: 'Svg' })).toBeDefined()
  })
})
