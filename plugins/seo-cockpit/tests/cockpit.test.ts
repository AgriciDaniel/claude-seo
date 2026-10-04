import { describe, expect, mock, test } from 'claude-code/testing'

import { command, worldOf } from './fixtures/world'

// As the owner's terminal drew it: an inline pane about 53 cells wide.
const NARROW = { plugin: 'seo-cockpit', component: 'Pane' as const, requestId: 'seo-cockpit', viewport: { columns: 55, rows: 40 }, props: { title: 'SEO Cockpit', isFocused: true, bodyColumns: 53, placement: 'inline' as const, scroll: { offset: 0, bodyRows: 12 }, view: {} } }
const WIDE = { ...NARROW, viewport: { columns: 160, rows: 50 }, props: { ...NARROW.props, bodyColumns: 110, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 40 } } }

const AUDIT = JSON.stringify({ summary: { health_score: 85 }, categories: [{ name: 'Schema', score: 76, findings: [] }, { name: 'Technical SEO', score: 94, findings: [] }], meta: { site: 'https://claude-seo.md' } })

/** The listing of a working folder holding one audit. */
const LISTING = { '/work': [{ name: 'claude-seo.md-audit', kind: 'dir' as const }], '/work/claude-seo.md-audit': [{ name: 'audit-data.json', kind: 'file' as const }] }

/** The rest of that folder: its files' contents, and the engine calls the pane makes. */
function auditFolder(on: Parameters<typeof worldOf>[0]) {
  on('session.cwd', () => ({ value: '/work' }))
  on('fs.stat', () => ({ value: { kind: 'file', size: AUDIT.length, mtimeMs: 1, isLink: false } }) as never)
  on('fs.read', ($, e) => (e.path.endsWith('audit-data.json') ? { value: AUDIT } : { deny: 'ENOENT' }))
  on('store.get', () => ({ value: undefined }))
  on('store.set', () => ({ value: undefined }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)
}

describe('cockpit', () => {
  test('/seo-cockpit opens on the Overview for the site this folder shows, with no setup', async ($, on) => {
    worldOf(on, { listing: LISTING, scripts: { run: { exitCode: 3, stdout: '', stderr: 'Claude SEO runtime is not ready.' } } })
    auditFolder(on)

    const opened: string[] = []

    on('ui.open', ($, e) => {
      opened.push(`${e.id}${e.focus === true ? ' focused' : ''}${e.closeOnEscape === true ? ' esc' : ''}`)

      return { value: { isPlaced: true } } as never
    })
    mock.clock(on)

    const result = await $.command.run(command('seo-cockpit'))

    expect(opened).toEqual(['seo-cockpit focused'])
    // The engine names the plugin itself; the reply is the outcome only.
    expect(result.text).toBe('Cockpit open for claude-seo.md.')

    const ui = await $.ui.mount({ ...NARROW, surface: 'terminal' })

    expect(await ui.find({ type: 'Text', text: /claude-seo\.md/ })).toBeDefined()
    expect(await ui.find({ key: 'row-audit' })).toBeDefined()
    expect(await ui.find({ key: 'row-vitals' })).toBeDefined()
  })

  test('a second /seo-cockpit closes it', async ($, on) => {
    worldOf(on, { listing: LISTING })
    auditFolder(on)
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    on('ui.close', () => ({ value: undefined }))
    mock.clock(on)

    await $.command.run(command('seo-cockpit'))

    expect((await $.command.run(command('seo-cockpit'))).text).toBe('Cockpit closed.')
  })

  test('with no site to infer, the pane asks for one in place', async ($, on) => {
    worldOf(on)
    on('session.cwd', () => ({ value: '/empty' }))
    on('store.get', () => ({ value: undefined }))
    on('store.set', () => ({ value: undefined }))
    on('ui.status', () => ({ value: undefined }))
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)
    mock.clock(on)

    expect((await $.command.run(command('seo-cockpit'))).text).toContain('Type the site in the pane')

    const ui = await $.ui.mount({ ...NARROW, surface: 'terminal' })

    expect(await ui.find({ key: 'target' })).toBeDefined()
  })

  test('in a folder with no audit, the last site used anywhere is shown, and can be changed', async ($, on) => {
    worldOf(on)
    on('session.cwd', () => ({ value: '/elsewhere' }))
    on('store.get', ($, e) => ({ value: e.key === 'target:last' ? 'claude-seo.md' : undefined }))
    on('store.set', () => ({ value: undefined }))
    on('ui.status', () => ({ value: undefined }))
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)
    mock.clock(on)

    expect((await $.command.run(command('seo-cockpit'))).text).toBe('Cockpit open for claude-seo.md.')

    const ui = await $.ui.mount({ ...NARROW, surface: 'terminal' })

    expect(await ui.find({ type: 'Text', text: /last used/ })).toBeDefined()
    expect(await ui.find({ key: 'target' })).toBeDefined()
  })

  test('/seo-cockpit <site> opens that site and remembers it here and as the last one', async ($, on) => {
    worldOf(on)

    const saved: Record<string, unknown> = {}

    on('session.cwd', () => ({ value: '/elsewhere' }))
    on('store.get', ($, e) => ({ value: saved[e.key] }))
    on('store.set', ($, e) => {
      saved[e.key] = e.value

      return { value: undefined }
    })
    on('ui.status', () => ({ value: undefined }))
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)
    mock.clock(on)

    expect((await $.command.run(command('seo-cockpit', 'claude-seo.md'))).text).toBe('Cockpit open for claude-seo.md.')
    expect(saved['target:/elsewhere']).toBe('claude-seo.md')
    expect(saved['target:last']).toBe('claude-seo.md')
    expect((await $.command.run(command('seo-cockpit', 'claude-ads.md'))).text).toBe('Cockpit switched to claude-ads.md.')
    expect((await $.command.run(command('seo-cockpit', 'not a site'))).text).toContain('is not a site')
  })

  test('the default site opens from any folder, with its remembered audit', { options: { site: 'claude-seo.md' } }, async ($, on) => {
    worldOf(on)
    on('session.cwd', () => ({ value: '/anywhere' }))
    on('store.get', ($, e) => ({ value: e.key === 'audit:claude-seo.md' ? '/work/claude-seo.md-audit/audit-data.json' : undefined }))
    on('store.set', () => ({ value: undefined }))
    on('fs.read', ($, e) => (e.path.endsWith('audit-data.json') ? { value: AUDIT } : { deny: 'ENOENT' }))
    on('ui.status', () => ({ value: undefined }))
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)
    mock.clock(on)

    expect((await $.command.run(command('seo-cockpit'))).text).toBe('Cockpit open for claude-seo.md.')

    const ui = await $.ui.mount({ ...NARROW, surface: 'terminal' })

    expect(await ui.find({ type: 'Text', text: /default/ })).toBeDefined()
    await ui.press({ key: 'refresh' })
    expect(await ui.find({ key: 'row-audit' })).toBeDefined()
  })

  test('a bare default site queries the sc-domain property, and the audits folder finds its audit', { options: { site: 'claude-seo.md', auditsFolder: '/audits' } }, async ($, on) => {
    const world = worldOf(on, { scripts: { run: { stdout: { error: null, rows: [] } } } })

    on('session.cwd', () => ({ value: '/anywhere' }))
    on('store.get', () => ({ value: undefined }))
    on('store.set', () => ({ value: undefined }))
    on('fs.read', ($, e) => (e.path === '/audits/claude-seo.md-audit/audit-data.json' ? { value: AUDIT } : { deny: 'ENOENT' }))
    on('ui.status', () => ({ value: undefined }))
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)
    mock.clock(on)

    await $.command.run(command('seo-cockpit'))

    const ui = await $.ui.mount({ ...WIDE, surface: 'terminal' })

    await ui.press({ key: 'refresh' })
    // Search Console needs sc-domain:claude-seo.md; the bare name is not a property.
    expect(world.runs.some(run => run.includes('--property sc-domain:claude-seo.md'))).toBe(true)
    expect(world.runs.some(run => / --property claude-seo\.md/.test(run))).toBe(false)
    await ui.press({ key: 'row-audit' })
    expect(await ui.find({ type: 'Text', text: /85\/100/ })).toBeDefined()
  })

  test('a site chosen in a folder beats the default', { options: { site: 'claude-seo.md' } }, async ($, on) => {
    worldOf(on)
    on('session.cwd', () => ({ value: '/client' }))
    on('store.get', ($, e) => ({ value: e.key === 'target:/client' ? 'client.example' : undefined }))
    on('store.set', () => ({ value: undefined }))
    on('ui.status', () => ({ value: undefined }))
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    on('ui.render', () => ({ type: 'Text', props: {}, children: ['engine'] }) as never)
    mock.clock(on)

    expect((await $.command.run(command('seo-cockpit'))).text).toBe('Cockpit open for client.example.')
  })

  test('with no pane on screen, it writes the HTML dashboard instead', async ($, on) => {
    worldOf(on)

    const written: string[] = []

    on('ui.open', () => ({ value: { isPlaced: false, reason: 'no pane here' } }) as never)
    on('session.cwd', () => ({ value: '/work' }))
    on('store.get', () => ({ value: undefined }))
    on('fs.write', ($, e) => {
      written.push(e.path)

      return { value: undefined }
    })

    const result = await $.command.run(command('seo-cockpit'))

    expect(result.text).toContain('No pane on this screen (no pane here)')
    expect(written.length).toBe(1)
    expect(written[0]).toMatch(/^\/work\/seo-cockpit-.*\.html$/)
  })

  test('a row opens its detail; charts are text in the terminal and SVG on the desktop', async ($, on) => {
    const day = (i: number) => new Date(Date.UTC(2026, 6, 3) + i * 86_400_000).toISOString().slice(0, 10)
    const gsc = { property: 'sc-domain:claude-seo.md', error: null, rows: Array.from({ length: 60 }, (_, i) => ({ keys: [day(i)], date: day(i), query: 'q', clicks: i, impressions: 10 * i, ctr: 1, position: 5 })) }

    // runtime.py run <script> ...: the fixture keys on the subcommand, `run`.
    worldOf(on, { listing: LISTING, scripts: { run: { stdout: gsc } } })
    auditFolder(on)
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    mock.clock(on)

    await $.command.run(command('seo-cockpit'))

    const terminal = await $.ui.mount({ ...WIDE, surface: 'terminal' })

    await terminal.press({ key: 'refresh' })
    await terminal.press({ key: 'row-gsc' })
    expect(await terminal.find({ type: 'Text', text: /Clicks per day/ })).toBeDefined()
    expect(await terminal.find({ type: 'Svg' })).toBeUndefined()
    await terminal.unmount()

    const desktop = await $.ui.mount({ ...WIDE, surface: 'desktop' })

    expect(await desktop.find({ type: 'Svg' })).toBeDefined()
    await desktop.press({ key: 'back' })
    expect(await desktop.find({ key: 'row-audit' })).toBeDefined()
  })

  test('unfocused, the footer says how to reach the keys instead of listing them', async ($, on) => {
    worldOf(on, { listing: LISTING })
    auditFolder(on)
    on('ui.open', () => ({ value: { isPlaced: true } }) as never)
    mock.clock(on)

    await $.command.run(command('seo-cockpit'))

    const ui = await $.ui.mount({ ...NARROW, surface: 'terminal', props: { ...NARROW.props, isFocused: false } })

    expect(await ui.find({ type: 'Text', text: /ctrl\+x tab/ })).toBeDefined()
    expect(await ui.find({ key: 'refresh' })).toBeUndefined()
  })
})
