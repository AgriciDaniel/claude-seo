import { describe, expect, mock, test } from 'claude-code/testing'

import { worldOf } from './fixtures/world'

const DATA = JSON.stringify({ summary: { health_score: 72 }, categories: [{ name: 'Schema', score: 40 }] })
const BAND = {
  plugin: 'seo-cockpit',
  component: 'AbovePrompt' as const,
  viewport: { columns: 140, rows: 40 },
  props: { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 140, scroll: { offset: 0, bodyRows: 10 }, view: {} },
}
const prompt = (text: string) => ({ text, wait: false, origin: { kind: 'composer' as const } })
// The kit's inputs for these events carry engine fields a test does not need; the casts keep the tests readable.
const spawn = (id: string, subagentType: string) =>
  ({ tool_use_id: id, prompt: 'p', description: 'd', subagentType, provider: { plugin: 'claude-seo', tier: 'user' }, parentModel: 'claude-opus-5-5' }) as never
const turnDone = () => ({ turnId: 't1', answer: 'Audit complete.', durationMs: 1000, isAborted: false, reason: 'answer' }) as never

/** The engine's own answers at the bottom of each event the audit hooks pass on. */
function engine(on: Parameters<typeof worldOf>[0]) {
  const seen = { models: [] as (string | undefined)[], instructions: [] as (string | undefined)[] }

  on('prompt.submit', ($, e) => ({ text: e.text }))
  on('agent.spawn', ($, e) => {
    seen.models.push(e.model)

    return { model: e.model ?? 'inherit' }
  })
  // As the engine answers: the turn's own answer text.
  on('turn.complete', ($, e) => ({ text: (e as unknown as { answer: string }).answer }))
  on('session.compact', ($, e) => {
    seen.instructions.push(e.instructions)

    return { messages: e.messages }
  })
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }) as never)

  return seen
}

describe('audit band and receipt', () => {
  test('an audit is followed from prompt to receipt, and the band shows it', async ($, on) => {
    mock.clock(on)
    const world = worldOf(on)

    engine(on)
    await $.prompt.submit(prompt('/seo audit https://example.com'))
    await $.agent.spawn(spawn('call-1', 'claude-seo:seo-technical'))
    await $.agent.spawn(spawn('call-2', 'claude-seo:seo-geo'))
    await $.tool.call({ tool: 'Agent', tool_use_id: 'call-1', prompt: 'p', description: 'd', subagent_type: 'seo-technical' } as never)
    await $.tool.call({ tool: 'Write', file_path: '/work/example.com-audit/findings/technical.md', content: '# Technical' })

    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })

    expect(await ui.find({ type: 'Text', text: /seo audit example\.com {2}1 running, 1 done {2}findings 1/ })).toBeDefined()
    await ui.unmount()

    await $.tool.call({ tool: 'Write', file_path: '/work/example.com-audit/audit-data.json', content: DATA })
    const result = await $.turn.complete(turnDone())

    expect(result.text).toContain('score 72/100')
    expect(result.text).toContain('weakest Schema 40')
    // The receipt alone: the answer is not repeated beneath itself.
    expect(result.text).not.toContain('Audit complete.')
    expect(world.ran.filter(tool => tool === 'Write').length).toBe(2)
  })

  test('the receipt is shown once', async ($, on) => {
    mock.clock(on)
    worldOf(on)
    engine(on)
    await $.tool.call({ tool: 'Write', file_path: '/work/a.com-audit/audit-data.json', content: DATA })

    expect((await $.turn.complete(turnDone())).text).toContain('score 72/100')
    expect((await $.turn.complete(turnDone())).text).toBe('Audit complete.')
  })

  test('other mods\' bands stay visible under ours', async ($, on) => {
    mock.clock(on)
    worldOf(on)
    engine(on)
    await $.prompt.submit(prompt('/seo audit example.com'))

    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })

    expect(await ui.find({ type: 'Text', text: /seo audit example\.com/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'drawn by Claude Code' })).toBeDefined()
  })

  test('with no audit the band is Claude Code\'s own', async ($, on) => {
    worldOf(on)
    engine(on)

    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })

    expect(await ui.find({ type: 'Text', text: 'drawn by Claude Code' })).toBeDefined()
  })

  test('compaction during an audit keeps its state', async ($, on) => {
    mock.clock(on)
    worldOf(on)

    const seen = engine(on)

    await $.prompt.submit(prompt('/seo audit example.com'))
    // A compaction always leaves at least one message; the engine refuses an empty list.
    await $.session.compact({ trigger: 'auto', messages: [{ role: 'user', text: 'Audit example.com', toolUses: [] }] })

    expect(seen.instructions[0]).toContain('A claude-seo audit of example.com is in progress')
  })
})

describe('economy mode', () => {
  test('routes Opus agents to Sonnet and leaves the rest', { options: { economy: true } }, async ($, on) => {
    worldOf(on)

    const seen = engine(on)

    await $.agent.spawn(spawn('c1', 'claude-seo:seo-content'))
    await $.agent.spawn(spawn('c2', 'claude-seo:seo-technical'))
    await $.agent.spawn(spawn('c3', 'Explore'))

    expect(seen.models).toEqual(['sonnet', undefined, undefined])
  })

  test('is off by default', async ($, on) => {
    worldOf(on)

    const seen = engine(on)

    await $.agent.spawn(spawn('c1', 'claude-seo:seo-content'))

    expect(seen.models).toEqual([undefined])
  })
})
