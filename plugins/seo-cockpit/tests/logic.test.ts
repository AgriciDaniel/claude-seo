import { describe, expect, test } from 'claude-code/testing'

import { lastDays, spark, spendText } from '../hooks/lib/format'
import { classify, mcpParts, merchantEndpoints, segmentsOf } from '../hooks/lib/paid'
import { candidatesOf, latestVersion, parentOf, runtimeEnvOf } from '../hooks/lib/root'
import { combine, isUnpriced, parseCheck } from '../hooks/lib/verdict'

describe('classify', () => {
  test('DataForSEO MCP tools are priced by endpoint', () => {
    expect(classify('mcp__dataforseo__serp_organic_live_advanced', undefined)).toEqual({
      kind: 'dataforseo', endpoints: ['serp_organic_live_advanced'], label: 'DataForSEO serp_organic_live_advanced',
    })
  })

  test('free DataForSEO reference lookups are not held', () => {
    expect(classify('mcp__dataforseo__serp_locations', undefined)).toBeNull()
    expect(classify('mcp__dataforseo__ai_opt_llm_ment_loc_and_lang', undefined)).toBeNull()
    expect(classify('mcp__dataforseo__ai_optimization_llm_models', undefined)).toBeNull()
  })

  test('other paid MCP servers ask, keyed by server', () => {
    expect(classify('mcp__ahrefs__site_explorer', undefined)).toEqual({ kind: 'ask', label: 'Ahrefs (site_explorer)', allowKey: 'mcp:ahrefs' })
    expect(classify('mcp__firecrawl-mcp__scrape', undefined)?.kind).toBe('ask')
    expect(classify('mcp__nanobanana-mcp__generate_image', undefined)?.kind).toBe('ask')
  })

  test('free tools and free MCP servers are not held', () => {
    expect(classify('Read', undefined)).toBeNull()
    expect(classify('mcp__github__create_issue', undefined)).toBeNull()
    expect(classify('Bash', 'git status')).toBeNull()
    expect(classify('Bash', 'python3 scripts/pagespeed_check.py https://example.com --json')).toBeNull()
  })

  test('paid scripts through Bash are held; ledger bookkeeping alone is not', () => {
    expect(classify('Bash', 'python3 scripts/moz_api.py metrics example.com')?.kind).toBe('ask')
    expect(classify('Bash', '"$R/scripts/claude-seo" run --extension banana generate.py --prompt "x"')?.kind).toBe('ask')
    expect(classify('PowerShell', 'python extensions\\banana\\scripts\\generate.py --prompt x')?.kind).toBe('ask')
    expect(classify('Bash', '"$R/scripts/claude-seo" run dataforseo_costs.py check serp_organic_live_advanced')).toBeNull()
  })

  test('a cost check chained in front of a paid script does not hide it', () => {
    expect(classify('Bash', 'python3 dataforseo_costs.py check x && "$R/scripts/claude-seo" run dataforseo_merchant.py search shoes')).toEqual({
      kind: 'dataforseo', endpoints: ['merchant_google_products_search'], label: 'DataForSEO Merchant (merchant_google_products_search)',
    })
    expect(classify('Bash', 'run --extension banana generate.py --prompt x; python3 cost_tracker.py log')?.kind).toBe('ask')
  })

  test('the merchant script is priced by subcommand and marketplace', () => {
    expect(merchantEndpoints('dataforseo_merchant.py search shoes')).toEqual(['merchant_google_products_search'])
    expect(merchantEndpoints('dataforseo_merchant.py search shoes --marketplace amazon')).toEqual(['merchant_amazon_products_search'])
    expect(merchantEndpoints('dataforseo_merchant.py sellers shoes')).toEqual(['merchant_google_sellers_search'])
    expect(merchantEndpoints('dataforseo_merchant.py compare shoes')).toEqual(['merchant_google_products_search', 'merchant_amazon_products_search'])
  })

  test('paid APIs reached with curl or WebFetch ask', () => {
    expect(classify('Bash', 'curl -s https://api4.seranking.com/sites')?.kind).toBe('ask')
    expect(classify('WebFetch', undefined, 'https://api.tryprofound.com/v1/x')?.kind).toBe('ask')
    expect(classify('WebFetch', undefined, 'https://example.com')).toBeNull()
  })

  test('segmentsOf splits a shell line', () => {
    expect(segmentsOf('a && b || c; d | e\nf')).toEqual(['a', 'b', 'c', 'd', 'e', 'f'])
  })

  test('mcpParts splits server and tool', () => {
    expect(mcpParts('mcp__plugin_x__do_thing')).toEqual({ server: 'plugin_x', name: 'do_thing' })
    expect(mcpParts('Bash')).toBeNull()
  })
})

describe('parseCheck', () => {
  test('reads each verdict', () => {
    expect(parseCheck(0, JSON.stringify({ status: 'approved', total_cost_usd: 0.002, today_spend_usd: 1, daily_remaining_usd: 9 })).decision).toBe('approved')
    expect(parseCheck(0, JSON.stringify({ status: 'blocked', message: 'cap' }))).toEqual({ decision: 'blocked', message: 'cap' })
  })

  test('an unknown endpoint carries only an estimate', () => {
    const verdict = parseCheck(0, JSON.stringify({ status: 'needs_approval', approval_reason: 'unknown_endpoint', estimated_cost_usd: 0.05 }))

    expect(verdict).toEqual({ decision: 'needs_approval', costUsd: 0.05, todayUsd: 0, remainingUsd: null, reason: 'unknown_endpoint', message: '' })
  })

  test('anything unreadable is an error, never an approval', () => {
    expect(parseCheck(1, '{"status":"approved"}').decision).toBe('error')
    expect(parseCheck(0, 'not json').decision).toBe('error')
    expect(parseCheck(0, '{"status":"maybe"}').decision).toBe('error')
    expect(parseCheck(0, 'null').decision).toBe('error')
  })
})

describe('combine', () => {
  const approved = { decision: 'approved' as const, costUsd: 0.02, todayUsd: 1, remainingUsd: 9 }
  const asks = { decision: 'needs_approval' as const, costUsd: 0.02, todayUsd: 1, remainingUsd: 9, reason: 'warn_endpoint', message: 'm' }

  test('the strictest verdict wins and costs add up', () => {
    expect(combine([approved, approved])).toEqual({ decision: 'approved', costUsd: 0.04, todayUsd: 1, remainingUsd: 9 })
    expect(combine([approved, asks]).decision).toBe('needs_approval')
    expect(combine([asks, { decision: 'blocked', message: 'cap' }])).toEqual({ decision: 'blocked', message: 'cap' })
    expect(combine([]).decision).toBe('error')
  })

  test('an unknown endpoint is unpriced and never logged', () => {
    expect(isUnpriced({ ...asks, reason: 'unknown_endpoint' })).toBe(true)
    expect(isUnpriced(asks)).toBe(false)
  })

  test('a ledger error keeps its reason', () => {
    expect(parseCheck(1, '{"status":"error","message":"ledger is corrupt"}')).toEqual({ decision: 'error', message: 'cost check exited 1 (ledger is corrupt)' })
  })
})

describe('root', () => {
  test('a checkout and an install are both candidates', () => {
    expect(candidatesOf('/repo/claude-seo/plugins/seo-cockpit', '')).toEqual({ fixed: ['/repo/claude-seo'], cacheDir: '/repo/claude-seo/claude-seo', cacheRoot: '/repo' })
    expect(candidatesOf('/c/mkt/seo-cockpit/0.1.0', '/opt/seo/')).toEqual({ fixed: ['/opt/seo', '/c/mkt'], cacheDir: '/c/mkt/claude-seo', cacheRoot: '/c' })
  })

  test('the latest version folder wins, numerically', () => {
    expect(latestVersion(['2.4.1', '2.10.0', '2.9.9', 'tmp'])).toBe('2.10.0')
    expect(latestVersion(['tmp'])).toBeNull()
    expect(latestVersion(['2.5.0-rc1', '2.5.0', '2.4.9'])).toBe('2.5.0')
  })

  test('runtime.py gets claude-seo\'s own data folder, never the calling plugin\'s', () => {
    expect(runtimeEnvOf('/home/u/.claude/plugins/cache/agricidaniel-claude-seo/claude-seo/2.4.1')).toEqual({
      CLAUDE_PLUGIN_DATA: '/home/u/.claude/plugins/data/claude-seo-agricidaniel-claude-seo',
      CLAUDE_PLUGIN_ROOT: '/home/u/.claude/plugins/cache/agricidaniel-claude-seo/claude-seo/2.4.1',
    })
    // A checkout: clear both, so runtime.py uses the checkout's own environment.
    expect(runtimeEnvOf('/home/u/Desktop/Skills/Public/claude-seo')).toEqual({ CLAUDE_PLUGIN_DATA: '', CLAUDE_PLUGIN_ROOT: '' })
  })

  test('parentOf trims trailing slashes', () => {
    expect(parentOf('/a/b/')).toBe('/a')
  })
})

describe('format', () => {
  test('spark scales to the largest value and leaves zero days blank', () => {
    expect(spark([0, 1, 2, 4])).toBe(' ▂▄█')
    expect(spark([0, 0])).toBe('  ')
  })

  test('lastDays counts back from today', () => {
    expect(lastDays('2026-10-03', 3)).toEqual(['2026-10-01', '2026-10-02', '2026-10-03'])
  })

  test('spendText reports today, the week and the month', () => {
    const text = spendText(
      { date: '2026-10-03', total_usd: 0.5, daily_limit_usd: 10, remaining_usd: 9.5, calls: 3, by_endpoint: { backlinks_summary: { cost_usd: 0.4, calls: 2 } } },
      // The script's own 30-day window reaches into day 31 (2026-09-03 here); the text keeps to 30 calendar days.
      { daily_totals: { '2026-09-03': { total_usd: 2.5, calls: 17 }, '2026-10-01': { total_usd: 1, calls: 2 }, '2026-10-03': { total_usd: 0.5, calls: 3 } }, grand_total_usd: 4, total_calls: 22 },
    )

    expect(text).toContain('today   $0.50 of $10.00 cap, 3 calls')
    expect(text).toContain('7 days  $1.50')
    expect(text).toContain('30 days $1.50, 5 calls')
    expect(text).toContain('backlinks_summary')
  })

  test('a ledger reset row is not counted as a call', () => {
    const text = spendText(
      { date: '2026-10-03', total_usd: 0, daily_limit_usd: 10, remaining_usd: 10, calls: 1, by_endpoint: { _audit_reset: { cost_usd: 0, calls: 1 } } },
      { daily_totals: {}, grand_total_usd: 0, total_calls: 1 },
    )

    expect(text).toContain('cap, 0 calls')
    expect(text).not.toContain('_audit_reset')
  })
})
