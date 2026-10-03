import type { EngineInterface, On, PluginOptions, ResultOf } from 'claude-code'

import { auditFromPrompt, bandText, compactInstructions, economyModel, isSeoAgent, noteWrite, receiptText, type Audit } from './lib/audit'
import { htmlPage } from './lib/charts'
import { doctorText, spendText } from './lib/format'
import { classify, type PaidCall } from './lib/paid'
import { candidatesOf, joinPath, latestVersion, MARKER } from './lib/root'
import { auditModel, emptyModel, gscModel, mapsModel, rankingsModel, spendModel, TABS, vitalsModel, type TabId, type TabModel } from './lib/tabs'
import { combine, isUnpriced, parseCheck, usd, type Verdict } from './lib/verdict'
import { paneView, type Kit, type PaneState } from './views/pane'

type ToolResult = ResultOf['tool.call']

/** What one activation knows: its settings, and what it has learned since it loaded. */
type Ctx = {
  setting: string
  python: string
  isGuardOn: boolean
  /** Paid tools the person allowed until the plugin reloads. */
  allowed: Set<string>
  root: string | null
  isEconomy: boolean
  isBandOn: boolean
  /** The audit being followed, kept after it finishes until the next prompt. */
  audit: Audit | null
  isBandHidden: boolean
  isReceiptShown: boolean
  /** Stops the once-a-second redraw of the band's clock. */
  stopTicker: (() => void) | null
  /** Search Console property and the URL for Core Web Vitals, from /config. */
  site: string
  pageUrl: string
  pane: PaneState & { isOpen: boolean; models: Partial<Record<TabId, TabModel>> }
}

const PANE_ID = 'seo-cockpit'

/** `sc-domain:example.com` or `https://example.com/` as a URL CrUX can read. */
function urlOfSite(site: string): string {
  const domain = /^sc-domain:(.+)$/.exec(site.trim())?.[1]

  return domain !== undefined ? `https://${domain}` : site.trim()
}

const stamp = (): string => new Date().toISOString().slice(0, 16).replace('T', ' ')

const HELD = 'seo-cockpit held this paid call'
const ALLOW = 'Allow until reload'

/** The tools the guard looks at; `classify` decides which of their calls are paid. */
const GUARDED_TOOLS = ['Bash', 'WebFetch', /^PowerShell$/, /^mcp__/] as const

/** A string field of a tool call's arguments, whatever the tool. */
function fieldOf(e: object, key: string): string | undefined {
  const value = (e as Readonly<Record<string, unknown>>)[key]

  return typeof value === 'string' ? value : undefined
}

// Every function that takes `$` is declared here at the top of the file and
// spells each call `$.noun.method(...)`, so `claude plugin validate` can read
// what the module calls off its source.

async function findRoot($: EngineInterface, ctx: Ctx): Promise<string | null> {
  if (ctx.root !== null) {
    return ctx.root
  }

  const { fixed, cacheDir, cacheRoot } = candidatesOf($.plugin.root, ctx.setting)

  for (const candidate of fixed) {
    if (await $.fs.exists(joinPath(candidate, MARKER))) {
      ctx.root = candidate

      return ctx.root
    }
  }

  // This plugin's own marketplace first, then any other that carries claude-seo.
  const cacheDirs = [cacheDir]

  try {
    for (const entry of await $.fs.list(cacheRoot)) {
      const dir = joinPath(cacheRoot, entry.name, 'claude-seo')

      if (entry.kind === 'dir' && dir !== cacheDir) {
        cacheDirs.push(dir)
      }
    }
  } catch {
    // No plugin cache: not installed from a marketplace.
  }

  for (const dir of cacheDirs) {
    try {
      const version = latestVersion((await $.fs.list(dir)).filter(entry => entry.kind === 'dir').map(entry => entry.name))
      const candidate = version === null ? null : joinPath(dir, version)

      if (candidate !== null && (await $.fs.exists(joinPath(candidate, MARKER)))) {
        ctx.root = candidate

        return ctx.root
      }
    } catch {
      // That marketplace has no claude-seo.
    }
  }

  return null
}

/** Runs one of claude-seo's stdlib-only scripts with the configured Python. */
async function runScript($: EngineInterface, ctx: Ctx, seoRoot: string, script: string, args: readonly string[]) {
  return $.process.run([ctx.python, joinPath(seoRoot, 'scripts', script), ...args], { timeoutMs: 20_000 })
}

/** Writes a guarded call's cost to the ledger. Never throws: the call already ran. */
async function logCost($: EngineInterface, ctx: Ctx, seoRoot: string, endpoint: string, cost: number): Promise<boolean> {
  try {
    const { exitCode } = await runScript($, ctx, seoRoot, 'dataforseo_costs.py', ['log', endpoint, String(cost), '--note', 'seo-cockpit estimate'])

    return exitCode === 0
  } catch {
    return false
  }
}

/** Runs the call, then logs each endpoint it billed at its table price. A denied, failed or unpriced call is not logged. */
async function runAndLog($: EngineInterface, ctx: Ctx, seoRoot: string, checks: ReadonlyArray<{ endpoint: string; verdict: Verdict }>, run: () => Promise<ToolResult>): Promise<ToolResult> {
  const result = await run()

  if (result.deny !== undefined) {
    return result
  }

  const names = checks.map(check => check.endpoint).join(', ')

  if (result.isError === true) {
    return { ...result, context: [...(result.context ?? []), `seo-cockpit did not log ${names}: the call failed, and DataForSEO does not bill failed tasks.`] }
  }

  if (checks.some(check => isUnpriced(check.verdict))) {
    return { ...result, context: [...(result.context ?? []), `seo-cockpit did not log ${names}: it has no price in the cost table. Log the actual cost from the response with dataforseo_costs.py log <endpoint> <cost>.`] }
  }

  const logged = await Promise.all(checks.map(check => logCost($, ctx, seoRoot, check.endpoint, 'costUsd' in check.verdict ? check.verdict.costUsd : 0)))
  const total = checks.reduce((sum, check) => sum + ('costUsd' in check.verdict ? check.verdict.costUsd : 0), 0)

  if (ctx.audit !== null && ctx.audit.finishMs === null) {
    ctx.audit = { ...ctx.audit, spentUsd: ctx.audit.spentUsd + total }
  }
  // The skills tell Claude to log each call itself; say it is done so it is not counted twice.
  const note = logged.every(Boolean)
    ? `seo-cockpit logged this call to the claude-seo DataForSEO ledger (${names}, about ${usd(total)}). Do not run dataforseo_costs.py log for it.`
    : `seo-cockpit could not log this call's cost. Log it with dataforseo_costs.py log <endpoint> <actual cost> for: ${names}.`

  return { ...result, context: [...(result.context ?? []), note] }
}

/** Asks the person; a dismissed dialog, or a run with no one to ask, is a no. The safe answer is listed first. */
async function askOrNull($: EngineInterface, question: string, choices: readonly string[]): Promise<string | null> {
  try {
    return await $.ui.ask(question, choices)
  } catch {
    return null
  }
}

async function guard($: EngineInterface, ctx: Ctx, paid: PaidCall, run: () => Promise<ToolResult>): Promise<ToolResult> {
  if (paid.kind === 'ask') {
    if (ctx.allowed.has(paid.allowKey)) {
      return run()
    }

    const answer = await askOrNull($, `${paid.label} bills a paid account. Run this call?`, ['Hold it', 'Run it', ALLOW])

    if (answer === ALLOW) {
      ctx.allowed.add(paid.allowKey)
    }

    return answer === 'Run it' || answer === ALLOW ? run() : { deny: `${HELD}: the person did not approve ${paid.label}.` }
  }

  const seoRoot = await findRoot($, ctx)

  if (seoRoot === null) {
    return { deny: `${HELD}: claude-seo was not found, so the DataForSEO budget could not be checked. Set "claude-seo folder" in /config, or turn the spend guard off there.` }
  }

  const checks = await Promise.all(
    paid.endpoints.map(async endpoint => {
      const { exitCode, stdout } = await runScript($, ctx, seoRoot, 'dataforseo_costs.py', ['check', endpoint])

      return { endpoint, verdict: parseCheck(exitCode, stdout) }
    }),
  )
  const verdict = combine(checks.map(check => check.verdict))

  switch (verdict.decision) {
    case 'approved':
      return runAndLog($, ctx, seoRoot, checks, run)
    case 'blocked':
      return { deny: `${HELD}: ${verdict.message}` }
    case 'error':
      // Look for claude-seo again next time: an update may have moved it.
      ctx.root = null

      return { deny: `${HELD}: ${verdict.message}. Run /seo-doctor.` }
    case 'needs_approval': {
      const left = verdict.remainingUsd === null ? '' : `, ${usd(verdict.remainingUsd)} left today`
      const price = isUnpriced(verdict) ? 'has no listed price' : `costs about ${usd(verdict.costUsd)}`
      const answer = await askOrNull(
        $,
        `${paid.label} ${price} (${verdict.reason.replace(/_/g, ' ')}; ${usd(verdict.todayUsd)} spent today${left}). Run it?`,
        ['Hold it', 'Approve'],
      )

      return answer === 'Approve' ? runAndLog($, ctx, seoRoot, checks, run) : { deny: `${HELD}: the person did not approve ${paid.label}.` }
    }
  }
}

/** Redraws the band once a second while an audit runs, so its clock moves. */
function startTicker($: EngineInterface, ctx: Ctx): void {
  if (ctx.stopTicker === null) {
    const timer = $.clock.every(1000, () => $.ui.invalidate('ui.render'))

    ctx.stopTicker = () => timer.cancel()
  }
}

function stopTicker(ctx: Ctx): void {
  ctx.stopTicker?.()
  ctx.stopTicker = null
}

/** Starts following a new audit and shows the band again. */
function follow($: EngineInterface, ctx: Ctx, audit: Audit): void {
  ctx.audit = audit
  ctx.isBandHidden = false
  ctx.isReceiptShown = false
  startTicker($, ctx)
  $.ui.invalidate('ui.render')
}

/** Runs a claude-seo script through its managed runtime (for scripts that need its packages) and parses the JSON it prints. */
async function runtimeJson($: EngineInterface, ctx: Ctx, seoRoot: string, script: string, args: readonly string[]): Promise<{ data: unknown; error: string | null }> {
  try {
    const { exitCode, stdout, stderr } = await $.process.run([ctx.python, joinPath(seoRoot, 'scripts', 'runtime.py'), 'run', script, ...args], { timeoutMs: 90_000 })

    try {
      return { data: JSON.parse(stdout), error: null }
    } catch {
      const reason = stderr.trim().split('\n').at(-1) ?? ''

      return { data: null, error: exitCode === 3 ? 'claude-seo runtime is not set up: run /seo setup' : reason || `${script} printed no JSON (exit ${exitCode})` }
    }
  } catch (error) {
    return { data: null, error: error instanceof Error ? error.message : String(error) }
  }
}

/** The newest file under the working folder's `*<suffix>` folders whose name passes `test`. */
async function newestFile($: EngineInterface, suffix: string, test: (name: string) => boolean): Promise<string | null> {
  let best: { path: string; mtime: number } | null = null

  try {
    const cwd = await $.session.cwd()

    for (const dir of (await $.fs.list(cwd)).filter(entry => entry.kind === 'dir' && entry.name.endsWith(suffix))) {
      for (const file of (await $.fs.list(joinPath(cwd, dir.name))).filter(entry => entry.kind === 'file' && test(entry.name))) {
        const path = joinPath(cwd, dir.name, file.name)
        const { mtimeMs } = await $.fs.stat(path)

        if (best === null || mtimeMs > best.mtime) {
          best = { path, mtime: mtimeMs }
        }
      }
    }
  } catch {
    // An unreadable folder has nothing to show; the tab says how to make some.
  }

  return best?.path ?? null
}

/** A path as shown on screen: relative to the working folder when it is inside it. */
async function shown($: EngineInterface, path: string | null): Promise<string> {
  if (path === null) {
    return ''
  }

  const cwd = await $.session.cwd()

  return path.startsWith(`${cwd}/`) ? path.slice(cwd.length + 1) : path
}

async function readJson($: EngineInterface, path: string): Promise<unknown> {
  try {
    return JSON.parse(await $.fs.read(path))
  } catch {
    return null
  }
}

/** Builds one tab's model from claude-seo's own scripts and files. Free: no paid API is called. */
async function buildTab($: EngineInterface, ctx: Ctx, tab: TabId): Promise<TabModel> {
  const at = stamp()
  const label = TABS.find(t => t.id === tab)?.label ?? tab
  const seoRoot = await findRoot($, ctx)

  if (seoRoot === null) {
    return emptyModel(label, 'claude-seo', at, 'claude-seo was not found. Set "claude-seo folder" in /config.')
  }

  const property = ctx.site.trim()
  const propertyArgs = property === '' ? [] : ['--property', property]

  if (tab === 'gsc' || tab === 'rankings') {
    const [byDate, byQuery] = await Promise.all([
      runtimeJson($, ctx, seoRoot, 'gsc_query.py', ['query', '--dimensions', 'date', '--days', '90', '--limit', '1000', '--json', ...propertyArgs]),
      runtimeJson($, ctx, seoRoot, 'gsc_query.py', ['query', '--dimensions', 'query', '--days', '28', '--limit', tab === 'gsc' ? '10' : '200', '--json', ...propertyArgs]),
    ])

    if (byDate.error !== null) {
      return emptyModel(label, 'gsc_query.py', at, byDate.error)
    }

    if (tab === 'gsc') {
      return gscModel(byDate.data, byQuery.data, property, at)
    }

    const target = ctx.pageUrl || urlOfSite(property)
    const drift = target === '' ? { data: null } : await runtimeJson($, ctx, seoRoot, 'drift_history.py', [target, '--limit', '20'])

    return rankingsModel(byDate.data, byQuery.data, drift.data, property, at)
  }

  if (tab === 'vitals') {
    const target = ctx.pageUrl || urlOfSite(property) || (ctx.audit === null ? '' : `https://${ctx.audit.domain}`)

    if (target === '') {
      return emptyModel(label, 'crux_history.py', at, 'No URL to measure. Set "Search Console property" or "Page for Core Web Vitals" in /config.')
    }

    const crux = await runtimeJson($, ctx, seoRoot, 'crux_history.py', [target, '--json'])

    return crux.error !== null ? emptyModel(label, 'crux_history.py', at, crux.error) : vitalsModel(crux.data, target, at)
  }

  if (tab === 'audit') {
    const path = ctx.audit?.dir != null ? joinPath(ctx.audit.dir, 'audit-data.json') : await newestFile($, '-audit', name => name === 'audit-data.json')

    return auditModel(path === null ? null : await readJson($, path), await shown($, path), at)
  }

  if (tab === 'maps') {
    const path = await newestFile($, '-maps', name => /^geo-grid-.*\.json$/.test(name))

    return mapsModel(path === null ? null : await readJson($, path), await shown($, path), at)
  }

  const [today, summary] = await Promise.all([runScript($, ctx, seoRoot, 'dataforseo_costs.py', ['today']), runScript($, ctx, seoRoot, 'dataforseo_costs.py', ['summary', '--days', '30'])])

  try {
    return spendModel(JSON.parse(today.stdout), JSON.parse(summary.stdout), at)
  } catch {
    return emptyModel(label, 'dataforseo_costs.py', at, 'The spend ledger could not be read.')
  }
}

/** Loads a tab into the pane and the cache, redrawing as it goes. */
async function loadTab($: EngineInterface, ctx: Ctx, tab: TabId): Promise<void> {
  ctx.pane.isLoading = true
  $.ui.invalidate('ui.render')

  try {
    const model = await buildTab($, ctx, tab)

    ctx.pane.models[tab] = model
    await $.store.set(`tab:${tab}`, model).catch(() => undefined)
  } finally {
    ctx.pane.isLoading = false
    ctx.pane.model = ctx.pane.models[ctx.pane.tab] ?? null
    $.ui.invalidate('ui.render')
  }
}

/** Shows a tab: its last result (this session or the cache) at once; nothing is fetched until asked. */
async function pickTab($: EngineInterface, ctx: Ctx, tab: TabId): Promise<void> {
  ctx.pane.tab = tab

  if (ctx.pane.models[tab] === undefined) {
    const cached = await $.store.get(`tab:${tab}`).catch(() => undefined)

    if (typeof cached === 'object' && cached !== null && 'heading' in cached) {
      ctx.pane.models[tab] = cached as TabModel
    }
  }

  ctx.pane.model = ctx.pane.models[tab] ?? null
  $.ui.invalidate('ui.render')
}

/** Writes every loaded tab into one self-contained HTML page in the working folder; returns its path. */
async function exportHtml($: EngineInterface, ctx: Ctx, loadAll: boolean): Promise<string> {
  if (loadAll) {
    for (const tab of TABS) {
      ctx.pane.models[tab.id] = await buildTab($, ctx, tab.id)
    }
  }

  const sections = TABS.flatMap(tab => {
    const model = ctx.pane.models[tab.id]

    return model === undefined ? [] : [{ ...model, source: `${model.source} · fetched ${model.fetchedAt}`, notes: model.error === null ? model.notes : [model.error, ...model.notes] }]
  })
  const cwd = await $.session.cwd()
  const path = joinPath(cwd, `seo-cockpit-${stamp().replace(/[: ]/g, '-')}.html`)

  await $.fs.write(path, htmlPage('SEO Cockpit', `Generated ${stamp()} by seo-cockpit from claude-seo data`, sections))
  ctx.pane.exported = path
  $.ui.invalidate('ui.render')

  return path
}

async function cockpitCommand($: EngineInterface, ctx: Ctx, args: string): Promise<{ text: string }> {
  try {
    if (args.trim().toLowerCase() === 'export') {
      return { text: `seo-cockpit: dashboard written to ${await exportHtml($, ctx, true)}` }
    }

    await pickTab($, ctx, ctx.pane.tab)

    const opened = await $.ui.open({ id: PANE_ID, title: 'SEO Cockpit' })

    if (opened.isPlaced) {
      ctx.pane.isOpen = true

      return { text: 'seo-cockpit: pane open. Keys 1 to 6 pick a view, r loads it, e exports HTML, x closes.' }
    }

    // No pane here (the VS Code chat panel, a narrow terminal): the HTML page is the cockpit.
    return { text: `seo-cockpit: no pane on this screen (${opened.reason}). Dashboard written to ${await exportHtml($, ctx, true)}` }
  } catch (error) {
    return { text: `seo-cockpit: ${error instanceof Error ? error.message : String(error)}` }
  }
}

async function registerCommands($: EngineInterface): Promise<void> {
  await Promise.all([
    $.command.register({ name: 'seo-spend', description: 'claude-seo DataForSEO spend: today, 7 and 30 days, by endpoint', immediate: true }).catch(() => undefined),
    $.command.register({ name: 'seo-doctor', description: 'claude-seo runtime readiness and where it is installed', immediate: true }).catch(() => undefined),
    $.command.register({ name: 'seo-cockpit', description: 'Charts for Search Console, rankings, Core Web Vitals, the audit, Maps and spend', argumentHint: '[export]', immediate: true }).catch(() => undefined),
  ])
}

async function spendCommand($: EngineInterface, ctx: Ctx): Promise<{ text: string }> {
  const seoRoot = await findRoot($, ctx)

  if (seoRoot === null) {
    return { text: 'seo-cockpit: claude-seo was not found. Set "claude-seo folder" in /config.' }
  }

  try {
    const [today, summary] = await Promise.all([
      runScript($, ctx, seoRoot, 'dataforseo_costs.py', ['today']),
      runScript($, ctx, seoRoot, 'dataforseo_costs.py', ['summary', '--days', '30']),
    ])

    if (today.exitCode !== 0 || summary.exitCode !== 0) {
      const failed = today.exitCode !== 0 ? today : summary
      // A ledger error prints its reason as JSON on stdout, not on stderr.
      const reason = /"message"\s*:\s*"([^"]*)"/.exec(failed.stdout)?.[1] || failed.stderr.trim().split('\n').at(-1) || 'no detail'

      return { text: `seo-cockpit: the ledger could not be read (${reason}).` }
    }

    return { text: spendText(JSON.parse(today.stdout), JSON.parse(summary.stdout)) }
  } catch (error) {
    return { text: `seo-cockpit: the ledger could not be read (${error instanceof Error ? error.message : String(error)}). Is "${ctx.python}" on PATH? Set "Python command" in /config.` }
  }
}

async function doctorCommand($: EngineInterface, ctx: Ctx): Promise<{ text: string }> {
  const seoRoot = await findRoot($, ctx)

  if (seoRoot === null) {
    return { text: 'seo-cockpit: claude-seo was not found next to this plugin or in the plugin cache. Set "claude-seo folder" in /config.' }
  }

  try {
    // Exit 3 means "setup required" and still prints the report.
    const { stdout } = await runScript($, ctx, seoRoot, 'runtime.py', ['doctor', '--json'])

    return { text: `${doctorText(JSON.parse(stdout), seoRoot)}\n  guard     ${ctx.isGuardOn ? 'on' : 'off'} (Python: ${ctx.python})` }
  } catch (error) {
    return { text: `seo-cockpit: doctor failed (${error instanceof Error ? error.message : String(error)}). Is "${ctx.python}" on PATH?` }
  }
}

/**
 * seo-cockpit: a spend guard over paid SEO API calls and zero-token commands
 * for claude-seo. This is the only file that calls `on()`; the rules live in
 * ./lib and never touch `$`.
 *
 * @param on the engine's registrar
 * @param options the plugin's userConfig values
 */
export function register(on: On, options: PluginOptions) {
  const ctx: Ctx = {
    setting: typeof options.claudeSeoRoot === 'string' ? options.claudeSeoRoot : '',
    python: typeof options.python === 'string' && options.python.trim() !== '' ? options.python.trim() : 'python3',
    isGuardOn: options.spendGuard !== false,
    allowed: new Set<string>(),
    root: null,
    isEconomy: options.economy === true,
    isBandOn: options.auditBand !== false,
    audit: null,
    isBandHidden: false,
    isReceiptShown: false,
    stopTicker: null,
    site: typeof options.site === 'string' ? options.site : '',
    pageUrl: typeof options.pageUrl === 'string' ? options.pageUrl.trim() : '',
    pane: { tab: 'gsc', model: null, isLoading: false, exported: null, isOpen: false, models: {} },
  }

  // ------------------------------------------------------------ spend guard

  on('tool.call', { tool: GUARDED_TOOLS }, async ($, e, next) => {
    if (!ctx.isGuardOn) {
      return next(e)
    }

    const paid = classify(e.tool, fieldOf(e, 'command'), fieldOf(e, 'url'))

    return paid === null ? next(e) : guard($, ctx, paid, () => next(e))
  }).catch(async ($, e, next) =>
    // After the call ran, its result stands: saying it did not run would invite a paid retry.
    next.called
      ? next(e)
      : { deny: `${HELD}: the spend guard failed, so the call did not run. Run /seo-doctor, or turn the spend guard off in /config.` },
  )

  // ---------------------------------------------------------- audit progress

  on('prompt.submit', async ($, e, next) => {
    const audit = auditFromPrompt(e.text, Date.now())

    if (audit !== null) {
      follow($, ctx, audit)
    } else if (ctx.audit !== null && ctx.audit.finishMs !== null) {
      // A finished audit's band stays up until the next prompt.
      ctx.audit = null
      $.ui.invalidate('ui.render')
    }

    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    if (!isSeoAgent(e.subagentType)) {
      return next(e)
    }

    if (ctx.audit !== null && ctx.audit.finishMs === null) {
      ctx.audit = { ...ctx.audit, agents: { ...ctx.audit.agents, [e.tool_use_id]: { type: e.subagentType, state: 'running', startMs: Date.now() } } }
      $.ui.invalidate('ui.render')
    }

    const model = ctx.isEconomy && e.model === undefined ? economyModel(e.subagentType) : null

    return next(model === null ? e : { ...e, model })
  })

  // A foreground Agent call returns when its subagent is done.
  on('tool.call', { tool: ['Agent', /^Task$/] }, async ($, e, next) => {
    const result = await next(e)
    const run = ctx.audit?.agents[e.tool_use_id]

    if (ctx.audit !== null && run !== undefined) {
      const state = result.deny !== undefined || result.isError === true ? 'failed' : 'done'

      ctx.audit = { ...ctx.audit, agents: { ...ctx.audit.agents, [e.tool_use_id]: { ...run, state, endMs: Date.now() } } }
      $.ui.invalidate('ui.render')
    }

    return result
  })

  on('tool.call', { tool: ['Write', 'Edit'] }, async ($, e, next) => {
    const result = await next(e)
    const path = fieldOf(e, 'file_path')

    if (path !== undefined && result.deny === undefined && result.isError !== true) {
      const before = ctx.audit
      // A Write carries the whole file; an Edit only a fragment, so its score is not read.
      const after = noteWrite(before, path, e.tool === 'Write' ? fieldOf(e, 'content') : undefined, Date.now())

      if (after !== null && after !== before) {
        if (before === null || before.finishMs !== null) {
          follow($, ctx, after)
        } else {
          ctx.audit = after
          $.ui.invalidate('ui.render')
        }
      }
    }

    return result
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    const audit = ctx.audit

    // The receipt goes under the main answer, once, when the audit's data file exists.
    if (e.agentId !== undefined || audit === null || audit.finishMs !== null || audit.score === null || ctx.isReceiptShown) {
      return result
    }

    const now = Date.now()

    ctx.audit = { ...audit, finishMs: now }
    ctx.isReceiptShown = true
    stopTicker(ctx)
    $.ui.invalidate('ui.render')

    const receipt = receiptText(audit, now)

    return { ...result, text: result.text ? `${result.text}\n${receipt}` : receipt }
  })

  on('session.compact', async ($, e, next) => {
    const audit = ctx.audit

    if (audit === null || audit.finishMs !== null) {
      return next(e)
    }

    return next({ ...e, instructions: [e.instructions, compactInstructions(audit)].filter(Boolean).join('\n\n') })
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const audit = ctx.audit

    if (!ctx.isBandOn || audit === null || ctx.isBandHidden || e.props.hasSurvey) {
      return next(e)
    }

    const { Box, Text, Button } = $.ui.resolve(e)
    const columns = Math.max(20, Math.floor(e.props.bodyColumns) - 10)

    return Box({
      flexDirection: 'row',
      columnGap: 1,
      children: [
        Text({ color: audit.finishMs === null ? 'cyan' : 'green', children: [bandText(audit, Date.now(), columns, ctx.isEconomy)] }),
        Button({
          key: 'seo-cockpit-hide',
          label: 'hide',
          plain: true,
          onPress: () => {
            ctx.isBandHidden = true
            $.ui.invalidate('ui.render')
          },
        }),
      ],
    })
  })

  // ------------------------------------------------------------------- pane

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== PANE_ID) {
      return next(e)
    }

    const table = $.ui.resolve(e)
    const kit: Kit = {
      Box: table.Box,
      Text: table.Text,
      Button: table.Button,
      ...('Link' in table && { Link: table.Link }),
      ...('Svg' in table && { Svg: table.Svg }),
    }

    ctx.pane.isOpen = true

    return paneView(kit, ctx.pane, Math.max(30, Math.floor(e.props.bodyColumns) - 2), {
      pick: tab => void pickTab($, ctx, tab).catch(() => undefined),
      refresh: () => void loadTab($, ctx, ctx.pane.tab).catch(() => undefined),
      exportHtml: () => void exportHtml($, ctx, false).catch(() => undefined),
      close: () => void $.ui.close({ id: PANE_ID }).catch(() => undefined),
    })
  })

  on('ui.close', async ($, e, next) => {
    if (e.id === PANE_ID) {
      ctx.pane.isOpen = false
    }

    return next(e)
  })

  // --------------------------------------------------------------- commands

  on('session.start', async ($, e, next) => {
    await registerCommands($)

    return next(e)
  })

  // /clear and /resume skip session.start; registering again replaces the command, so this is safe to repeat.
  on('classic.SessionStart', async ($, e, next) => {
    await registerCommands($)

    return next(e)
  })

  on('command.run', { command: 'seo-spend' }, async ($, e, next) => spendCommand($, ctx))

  on('command.run', { command: 'seo-doctor' }, async ($, e, next) => doctorCommand($, ctx))

  on('command.run', { command: 'seo-cockpit' }, async ($, e, next) => cockpitCommand($, ctx, e.args))
}
