import { describe, expect, test } from 'claude-code/testing'

import { APPROVED, BLOCKED, command, NEEDS, SESSION, worldOf } from './fixtures/world'

// MCP tool inputs are typed from the servers connected on the machine that last loaded the mod,
// so a test naming servers that machine lacks casts its input.
const SERP = { tool: 'mcp__dataforseo__serp_organic_live_advanced' } as never
const LLM = { tool: 'mcp__dataforseo__ai_opt_llm_ment_search' } as never
const AHREFS = { tool: 'mcp__ahrefs__site_explorer' } as never

describe('spend guard', () => {
  test('a free tool passes untouched and runs nothing', async ($, on) => {
    const world = worldOf(on)

    await $.tool.call({ tool: 'Read', file_path: '/work/a.md' })

    expect(world.ran).toEqual(['Read'])
    expect(world.runs).toEqual([])
  })

  test('an approved DataForSEO call runs, is logged, and tells Claude not to log it again', async ($, on) => {
    const world = worldOf(on, { scripts: { check: { stdout: APPROVED }, log: { stdout: { status: 'logged' } } } })

    const result = await $.tool.call(SERP)

    expect(world.ran).toEqual(['mcp__dataforseo__serp_organic_live_advanced'])
    expect(world.runs).toEqual(['dataforseo_costs.py check serp_organic_live_advanced', 'dataforseo_costs.py log serp_organic_live_advanced 0.002 --note seo-cockpit estimate'])
    expect(world.asked).toEqual([])
    expect(JSON.stringify(result)).toContain('Do not run dataforseo_costs.py log')
  })

  test('a blocked call never reaches the tool', async ($, on) => {
    const world = worldOf(on, { scripts: { check: { stdout: BLOCKED } } })

    const result = await $.tool.call(SERP)

    expect(world.ran).toEqual([])
    expect(result.deny).toContain('Daily limit $10.00')
  })

  test('a cost check that fails holds the call', async ($, on) => {
    const world = worldOf(on, { scripts: { check: { exitCode: 1, stdout: '' } } })

    const result = await $.tool.call(SERP)

    expect(world.ran).toEqual([])
    expect(result.deny).toContain('cost check exited 1')
  })

  test('claude-seo missing holds the call and says how to fix it', async ($, on) => {
    const world = worldOf(on, { hasRoot: false })

    const result = await $.tool.call(SERP)

    expect(world.ran).toEqual([])
    expect(result.deny).toContain('claude-seo folder')
  })

  test('a spawn failure is caught and holds the call', async ($, on) => {
    const world = worldOf(on, { scripts: { check: 'throw' } })

    const result = await $.tool.call(SERP)

    expect(world.ran).toEqual([])
    expect(result.deny).toContain('spend guard failed')
  })

  test('a call that needs approval runs once the person approves', async ($, on) => {
    const world = worldOf(on, { scripts: { check: { stdout: NEEDS } }, answer: 'Approve' })

    await $.tool.call(LLM)

    expect(world.asked.length).toBe(1)
    expect(world.asked[0]).toContain('about $0.10')
    expect(world.ran).toEqual(['mcp__dataforseo__ai_opt_llm_ment_search'])
  })

  test('a call that needs approval is held when the dialog is dismissed', async ($, on) => {
    const world = worldOf(on, { scripts: { check: { stdout: NEEDS } }, answer: null })

    const result = await $.tool.call(LLM)

    expect(world.ran).toEqual([])
    expect(result.deny).toContain('did not approve')
  })

  test('"Allow until reload" stops asking about that server', async ($, on) => {
    const world = worldOf(on, { answer: 'Allow until reload' })

    await $.tool.call(AHREFS)
    await $.tool.call(AHREFS)

    expect(world.asked.length).toBe(1)
    expect(world.ran).toEqual(['mcp__ahrefs__site_explorer', 'mcp__ahrefs__site_explorer'])
  })

  test('a call that failed is not logged as spend', async ($, on) => {
    const world = worldOf(on, { scripts: { check: { stdout: APPROVED } }, toolFails: true })

    const result = await $.tool.call(SERP)

    expect(world.runs).toEqual(['dataforseo_costs.py check serp_organic_live_advanced'])
    expect(JSON.stringify(result)).toContain('did not log')
  })

  test('an approved unknown endpoint runs but is not logged at a guessed price', async ($, on) => {
    const world = worldOf(on, {
      scripts: { check: { stdout: { status: 'needs_approval', approval_reason: 'unknown_endpoint', estimated_cost_usd: 0.05, message: 'm' } } },
      answer: 'Approve',
    })

    const result = await $.tool.call({ tool: 'mcp__dataforseo__brand_new_endpoint' } as never)

    expect(world.asked[0]).toContain('has no listed price')
    expect(world.runs).toEqual(['dataforseo_costs.py check brand_new_endpoint'])
    expect(JSON.stringify(result)).toContain('no price in the cost table')
  })

  test('the merchant compare checks both endpoints and logs both', async ($, on) => {
    const world = worldOf(on, { scripts: { check: { stdout: APPROVED }, log: { stdout: { status: 'logged' } } } })

    await $.tool.call({ tool: 'Bash', command: 'run dataforseo_merchant.py compare shoes' })

    expect(world.runs.filter(run => run.includes(' check '))).toEqual([
      'dataforseo_costs.py check merchant_google_products_search',
      'dataforseo_costs.py check merchant_amazon_products_search',
    ])
    expect(world.runs.filter(run => run.includes(' log ')).length).toBe(2)
  })

  test('the safe answer is listed first in every question', async ($, on) => {
    const choices: string[][] = []

    on('tool.call', { tool: 'AskUserQuestion' }, ($, e, next) => {
      choices.push((e.questions[0]?.options ?? []).map(option => option.label))

      return next(e)
    })
    worldOf(on, { scripts: { check: { stdout: NEEDS } }, answer: null })

    await $.tool.call(AHREFS)
    await $.tool.call(LLM)

    expect(choices.map(list => list[0])).toEqual(['Hold it', 'Hold it'])
  })

  test('with the guard off, paid calls pass without a check', { options: { spendGuard: false } }, async ($, on) => {
    const world = worldOf(on)

    await $.tool.call(SERP)

    expect(world.runs).toEqual([])
    expect(world.ran).toEqual(['mcp__dataforseo__serp_organic_live_advanced'])
  })
})

describe('google settings', () => {
  test('/config Google settings reach claude-seo\'s scripts, and only them', { options: { googleAccount: 'gcloud', googleApiKey: 'test-key' } }, async ($, on) => {
    const world = worldOf(on, { scripts: { today: { stdout: {} }, summary: { stdout: {} } } })

    await $.command.run(command('seo-spend'))

    expect(world.envs[0]?.CLAUDE_SEO_GOOGLE_AUTH).toBe('adc')
    expect(world.envs[0]?.GOOGLE_API_KEY).toBe('test-key')
    // A checkout: claude-seo uses its own runtime folder, never this plugin's.
    expect(world.envs[0]?.CLAUDE_PLUGIN_DATA).toBe('')
  })

  test('auto leaves claude-seo\'s own order alone', async ($, on) => {
    const world = worldOf(on, { scripts: { today: { stdout: {} }, summary: { stdout: {} } } })

    await $.command.run(command('seo-spend'))

    expect(world.envs[0]?.CLAUDE_SEO_GOOGLE_AUTH).toBeUndefined()
    expect(world.envs[0]?.GOOGLE_API_KEY).toBeUndefined()
  })
})

describe('commands', () => {
  test('the start registers all three commands', async ($, on) => {
    const world = worldOf(on)

    await $.session.start(SESSION)

    expect(world.commands.sort()).toEqual(['seo-cockpit', 'seo-doctor', 'seo-spend'])
  })

  test('/seo-spend answers from the ledger without a turn', async ($, on) => {
    worldOf(on, {
      scripts: {
        today: { stdout: { date: '2026-10-03', total_usd: 0.25, daily_limit_usd: 10, remaining_usd: 9.75, calls: 5, by_endpoint: {} } },
        summary: { stdout: { daily_totals: { '2026-10-03': { total_usd: 0.25 } }, grand_total_usd: 0.25, total_calls: 5 } },
      },
    })

    const result = await $.command.run(command('seo-spend'))

    expect(result.text).toContain('today   $0.25 of $10.00 cap, 5 calls')
  })

  test('/seo-doctor reports setup required with the fix', async ($, on) => {
    worldOf(on, { scripts: { doctor: { exitCode: 3, stdout: { ready: false, mode: 'plugin', plugin_version: '2.4.1', python_version: '3.12', browser_ready: false, reasons: ['venv missing'] } } } })

    const result = await $.command.run(command('seo-doctor'))

    expect(result.text).toContain('setup required')
    expect(result.text).toContain('venv missing')
    expect(result.text).toContain('guard     on')
  })
})
