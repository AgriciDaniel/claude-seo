import type { EngineInterface, On, PluginOptions, ResultOf } from 'claude-code'

import { auditFromPrompt, bandText, compactInstructions, economyModel, isSeoAgent, noteWrite, receiptText, type Audit } from './lib/audit'
import { COLORS, htmlPage } from './lib/charts'
import { doctorText, spendText } from './lib/format'
import { classify, type PaidCall } from './lib/paid'
import { candidatesOf, joinPath, latestVersion, MARKER, runtimeEnvOf } from './lib/root'
import { chooseTarget, hostOf, rowOf, ROWS, siteOfAudit, statusLine } from './lib/overview'
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
  pane: PaneState & { isOpen: boolean }
  /** Google settings from /config, handed to claude-seo's scripts only. */
  googleAccount: string
  googleApiKey: string
  /** Where the person keeps their audits (`<site>-audit/` folders), found from any working folder. */
  auditsFolder: string
  /** What the person typed in the pane as the site, per working folder. */
  typed: string | null
}

const PANE_ID = 'seo-cockpit'


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

/** The environment claude-seo's scripts run with: its own runtime folder, plus the Google settings from /config. */
function scriptEnv(ctx: Ctx, seoRoot: string): Record<string, string> {
  return {
    ...runtimeEnvOf(seoRoot),
    ...(ctx.googleAccount === 'gcloud' && { CLAUDE_SEO_GOOGLE_AUTH: 'adc' }),
    ...(ctx.googleApiKey !== '' && { GOOGLE_API_KEY: ctx.googleApiKey }),
  }
}

/** Runs one of claude-seo's stdlib-only scripts with the configured Python. */
async function runScript($: EngineInterface, ctx: Ctx, seoRoot: string, script: string, args: readonly string[]) {
  return $.process.run([ctx.python, joinPath(seoRoot, 'scripts', script), ...args], { timeoutMs: 20_000, env: scriptEnv(ctx, seoRoot) })
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

/** The band's clock needs redrawing only while the band shows a running audit. */
function syncTicker($: EngineInterface, ctx: Ctx): void {
  const audit = ctx.audit

  if (ctx.isBandOn && !ctx.isBandHidden && audit !== null && audit.finishMs === null) {
    startTicker($, ctx)
  } else {
    stopTicker(ctx)
  }
}

/** Sets the audit, redraws, and keeps a copy in the store so a reload mid-audit does not lose it. */
function setAudit($: EngineInterface, ctx: Ctx, audit: Audit | null): void {
  ctx.audit = audit
  syncTicker($, ctx)
  $.ui.invalidate('ui.render')
  void $.store.set('audit', audit).catch(() => undefined)
}

/** Starts following a new audit and shows the band again. */
function follow($: EngineInterface, ctx: Ctx, audit: Audit): void {
  ctx.isBandHidden = false
  ctx.isReceiptShown = false
  setAudit($, ctx, audit)
}

/** An audit older than this with no result is treated as abandoned. */
const STALE_MS = 3 * 60 * 60 * 1000

/** After a reload, picks up an audit that was still running. */
async function restoreAudit($: EngineInterface, ctx: Ctx): Promise<void> {
  if (ctx.audit !== null) {
    return
  }

  const saved = (await $.store.get('audit').catch(() => null)) as Audit | null

  if (saved !== null && typeof saved === 'object' && typeof saved.domain === 'string' && saved.finishMs === null && Date.now() - saved.startMs < STALE_MS) {
    ctx.audit = saved
    syncTicker($, ctx)
    $.ui.invalidate('ui.render')
  }
}

/** Runs a claude-seo script through its managed runtime (for scripts that need its packages) and parses the JSON it prints. */
async function runtimeJson($: EngineInterface, ctx: Ctx, seoRoot: string, script: string, args: readonly string[]): Promise<{ data: unknown; error: string | null }> {
  try {
    const { exitCode, stdout, stderr } = await $.process.run([ctx.python, joinPath(seoRoot, 'scripts', 'runtime.py'), 'run', script, ...args], { timeoutMs: 90_000, env: scriptEnv(ctx, seoRoot) })

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

/** The store key for a tab's last result: per working folder and property, so one project's data never shows in another. */
async function cacheKey($: EngineInterface, ctx: Ctx, tab: TabId): Promise<string> {
  return `tab:${tab}:${await $.session.cwd()}:${ctx.site}`
}

const isModel = (value: unknown): value is TabModel => {
  const m = value as Partial<TabModel> | null

  return typeof m === 'object' && m !== null && typeof m.heading === 'string' && Array.isArray(m.kpis) && Array.isArray(m.charts) && Array.isArray(m.tables) && Array.isArray(m.notes)
}

/** The audit for a site: a live one, this folder's if it is about that site, else the one remembered for it. */
async function auditFor($: EngineInterface, ctx: Ctx, host: string | null): Promise<[unknown, string]> {
  if (ctx.audit?.dir != null && (host === null || ctx.audit.domain === host)) {
    const path = joinPath(ctx.audit.dir, 'audit-data.json')

    return [await readJson($, path), await shown($, path)]
  }

  const here = await newestFile($, '-audit', name => name === 'audit-data.json')

  if (here !== null) {
    const data = await readJson($, here)

    if (host === null || siteOfAudit(here.split(/[/\\]/).at(-2) ?? '', data) === host) {
      return [data, await shown($, here)]
    }
  }

  const remembered = host === null ? undefined : await $.store.get(`audit:${host}`).catch(() => undefined)

  if (typeof remembered === 'string') {
    const data = await readJson($, remembered)

    if (data !== null) {
      return [data, remembered]
    }
  }

  // The audits folder from /config: `<site>-audit/audit-data.json`, with or without www.
  if (host !== null && ctx.auditsFolder !== '') {
    for (const name of [`${host}-audit`, `www.${host}-audit`]) {
      const path = joinPath(ctx.auditsFolder, name, 'audit-data.json')
      const data = await readJson($, path)

      if (data !== null) {
        void $.store.set(`audit:${host}`, path).catch(() => undefined)

        return [data, path]
      }
    }
  }

  return [null, '']
}

async function readJson($: EngineInterface, path: string): Promise<unknown> {
  try {
    return JSON.parse(await $.fs.read(path))
  } catch {
    return null
  }
}

/** The site the cockpit is about: this folder's choice, its audit, the /config default, then the last site used. */
async function resolveHost($: EngineInterface, ctx: Ctx): Promise<void> {
  const cwd = await $.session.cwd().catch(() => '')

  if (ctx.typed === null) {
    const saved = await $.store.get(`target:${cwd}`).catch(() => undefined)

    ctx.typed = typeof saved === 'string' ? saved : null
  }

  let inferred: string | null = ctx.audit?.domain ?? null

  if (inferred === null) {
    const path = await newestFile($, '-audit', name => name === 'audit-data.json')

    if (path !== null) {
      const folder = path.split(/[/\\]/).at(-2) ?? ''

      inferred = siteOfAudit(folder, await readJson($, path))

      // Remember where this site's audit lives, so the Audit row works from any folder.
      if (inferred !== null) {
        void $.store.set(`audit:${inferred}`, path).catch(() => undefined)
      }
    }
  }

  const setting = ctx.site || ctx.pageUrl
  const chosen = chooseTarget(setting, ctx.typed, inferred)
  let host = chosen.host
  let source: PaneState['hostSource'] = chosen.source

  // Nothing here says which site: use the last one seen anywhere, and say so.
  if (host === null) {
    const last = await $.store.get('target:last').catch(() => undefined)

    host = typeof last === 'string' ? hostOf(last) : null
    source = host === null ? null : 'last'
  } else {
    void $.store.set('target:last', host).catch(() => undefined)
  }

  ctx.pane.host = host
  ctx.pane.hostSource = source
}

/**
 * The Search Console property for a site. A /config value counts only when it
 * is a real property (`sc-domain:` or a URL prefix) for that site; a bare name
 * such as `claude-seo.md` is not a property and becomes `sc-domain:claude-seo.md`.
 */
function propertyFor(setting: string, host: string): string {
  const value = setting.trim()

  return hostOf(value) === host && /^(sc-domain:|https?:\/\/)/i.test(value) ? value : `sc-domain:${host}`
}

/** Builds one source's model from claude-seo's own scripts and files. Free: no paid API is called. */
async function buildTab($: EngineInterface, ctx: Ctx, tab: TabId): Promise<TabModel> {
  const at = stamp()
  const label = TABS.find(t => t.id === tab)?.label ?? tab
  const seoRoot = await findRoot($, ctx)

  if (seoRoot === null) {
    return emptyModel(label, 'claude-seo', at, 'claude-seo was not found. Set "claude-seo folder" in /config.')
  }

  const host = ctx.pane.host
  // The /config property and page apply only to the site they name; any other site uses its domain property and home page.
  const property = host === null ? '' : propertyFor(ctx.site, host)
  const propertyArgs = property === '' ? [] : ['--property', property]
  const url = host === null ? '' : hostOf(ctx.pageUrl) === host ? ctx.pageUrl : `https://${host}`

  if (tab === 'gsc' || tab === 'rankings') {
    // With no site, claude-seo would fall back to its own default property, which may be another site.
    if (property === '') {
      return emptyModel(label, 'gsc_query.py', at, 'No URL to measure.')
    }

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

    const drift = url === '' ? { data: null } : await runtimeJson($, ctx, seoRoot, 'drift_history.py', [url, '--limit', '20'])

    return rankingsModel(byDate.data, byQuery.data, drift.data, property, at)
  }

  if (tab === 'vitals') {
    if (url === '') {
      return emptyModel(label, 'crux_history.py', at, 'No URL to measure.')
    }

    const crux = await runtimeJson($, ctx, seoRoot, 'crux_history.py', [url, '--json'])

    return crux.error !== null ? emptyModel(label, 'crux_history.py', at, crux.error) : vitalsModel(crux.data, url, at)
  }

  if (tab === 'audit') {
    return auditModel(...(await auditFor($, ctx, host)), at)
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

/** Loads one source, cache first: the last result shows at once, the fresh one replaces it. */
async function loadSource($: EngineInterface, ctx: Ctx, tab: TabId): Promise<void> {
  const key = await cacheKey($, ctx, tab).catch(() => null)

  if (ctx.pane.models[tab] === undefined && key !== null) {
    const cached = await $.store.get(key).catch(() => undefined)

    if (isModel(cached)) {
      ctx.pane.models[tab] = cached
    }
  }

  ctx.pane.loading = new Set([...ctx.pane.loading, tab])
  $.ui.invalidate('ui.render')

  try {
    const model = await buildTab($, ctx, tab)

    ctx.pane.models[tab] = model

    if (key !== null) {
      await $.store.set(key, model).catch(() => undefined)
    }
  } finally {
    ctx.pane.loading = new Set([...ctx.pane.loading].filter(t => t !== tab))
    $.ui.invalidate('ui.render')
  }
}

/** Loads every source in the background (all free), then pins the one-line summary under the prompt. */
async function loadAll($: EngineInterface, ctx: Ctx): Promise<void> {
  // Every row says "checking" from the first frame, not "not loaded".
  ctx.pane.loading = new Set(ROWS.map(row => row.id))
  $.ui.invalidate('ui.render')
  await resolveHost($, ctx)
  await Promise.allSettled(ROWS.map(row => loadSource($, ctx, row.id)))

  const rows = ROWS.map(row => rowOf(row.id, ctx.pane.models[row.id], false))

  $.ui.status(statusLine(ctx.pane.host, rows))
}

/** Remembers a site the person gave: for this folder, and as the last one used anywhere. */
async function rememberTarget($: EngineInterface, ctx: Ctx, value: string): Promise<void> {
  ctx.typed = value.trim()
  ctx.pane.models = {}
  await $.store.set(`target:${await $.session.cwd()}`, ctx.typed).catch(() => undefined)
  await $.store.set('target:last', hostOf(ctx.typed)).catch(() => undefined)
}

/** The person typed the site in the pane: remember it and load again. */
async function setTarget($: EngineInterface, ctx: Ctx, value: string): Promise<void> {
  if (hostOf(value) === null) {
    return
  }

  await rememberTarget($, ctx, value)
  await loadAll($, ctx)
}

/** Writes every loaded source into one self-contained HTML page in the working folder; returns its path. */
async function exportHtml($: EngineInterface, ctx: Ctx, loadAllFirst: boolean): Promise<string> {
  if (loadAllFirst) {
    await resolveHost($, ctx)

    for (const tab of TABS) {
      ctx.pane.models[tab.id] = await buildTab($, ctx, tab.id)
    }
  }

  const sections = TABS.flatMap(tab => {
    const model = ctx.pane.models[tab.id]

    return model === undefined ? [] : [{ ...model, source: `${model.source} · fetched ${model.fetchedAt}`, notes: model.error === null ? model.notes : [model.error, ...model.notes] }]
  })
  const cwd = await $.session.cwd()
  const path = joinPath(cwd, `seo-cockpit-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.html`)

  await $.fs.write(path, htmlPage(`SEO Cockpit${ctx.pane.host === null ? '' : `: ${ctx.pane.host}`}`, `Generated ${stamp()} by seo-cockpit from claude-seo data`, sections))
  ctx.pane.exported = path
  $.ui.invalidate('ui.render')

  return path
}

async function cockpitCommand($: EngineInterface, ctx: Ctx, args: string): Promise<{ text: string }> {
  // The engine already names the plugin above a command's answer; the text is the outcome only.
  try {
    const arg = args.trim()

    if (arg.toLowerCase() === 'export') {
      return { text: `Dashboard written to ${await exportHtml($, ctx, true)}` }
    }

    // `/seo-cockpit claude-seo.md`: that site, remembered for this folder and as the last one used.
    if (arg !== '') {
      if (hostOf(arg) === null) {
        return { text: `"${arg}" is not a site. Try /seo-cockpit example.com, or /seo-cockpit export.` }
      }

      await rememberTarget($, ctx, arg)

      if (ctx.pane.isOpen) {
        void loadAll($, ctx).catch(() => undefined)

        return { text: `Cockpit switched to ${hostOf(arg)}.` }
      }
    } else if (ctx.pane.isOpen) {
      // A second /seo-cockpit closes it, as the official modernization pane does.
      await $.ui.close({ id: PANE_ID }).catch(() => undefined)
      ctx.pane.isOpen = false

      return { text: 'Cockpit closed.' }
    }

    await resolveHost($, ctx)

    // Ask for room: inline, the engine grants up to what the layout spares (a size the person set wins).
    // Docked beside the transcript (fullscreen, 110+ columns), the pane is full height anyway.
    const opened = await $.ui.open({ id: PANE_ID, title: 'SEO Cockpit', focus: true, rows: 40 })

    if (opened.isPlaced) {
      ctx.pane.isOpen = true
      ctx.pane.view = 'overview'
      void loadAll($, ctx).catch(() => undefined)

      return { text: ctx.pane.host === null ? 'Cockpit open. Type the site in the pane to load its data.' : `Cockpit open for ${ctx.pane.host}.` }
    }

    // No pane here (the VS Code chat panel): the HTML page is the cockpit.
    return { text: `No pane on this screen (${opened.reason}). Dashboard written to ${await exportHtml($, ctx, true)}` }
  } catch (error) {
    return { text: `The cockpit could not open: ${error instanceof Error ? error.message : String(error)}` }
  }
}

async function registerCommands($: EngineInterface): Promise<void> {
  await Promise.all([
    $.command.register({ name: 'seo-spend', description: 'claude-seo DataForSEO spend: today, 7 and 30 days, by endpoint', immediate: true }).catch(() => undefined),
    $.command.register({ name: 'seo-doctor', description: 'claude-seo runtime readiness and where it is installed', immediate: true }).catch(() => undefined),
    $.command.register({ name: 'seo-cockpit', description: 'Charts for Search Console, rankings, Core Web Vitals, the audit, Maps and spend', argumentHint: '[site | export]', immediate: true }).catch(() => undefined),
  ])
}

async function spendCommand($: EngineInterface, ctx: Ctx): Promise<{ text: string }> {
  const seoRoot = await findRoot($, ctx)

  if (seoRoot === null) {
    return { text: 'claude-seo was not found. Set "claude-seo folder" in /config.' }
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

      return { text: `The ledger could not be read (${reason}).` }
    }

    return { text: spendText(JSON.parse(today.stdout), JSON.parse(summary.stdout)) }
  } catch (error) {
    return { text: `The ledger could not be read (${error instanceof Error ? error.message : String(error)}). Is "${ctx.python}" on PATH? Set "Python command" in /config.` }
  }
}

async function doctorCommand($: EngineInterface, ctx: Ctx): Promise<{ text: string }> {
  const seoRoot = await findRoot($, ctx)

  if (seoRoot === null) {
    return { text: 'claude-seo was not found next to this plugin or in the plugin cache. Set "claude-seo folder" in /config.' }
  }

  try {
    // Exit 3 means "setup required" and still prints the report.
    const { stdout } = await runScript($, ctx, seoRoot, 'runtime.py', ['doctor', '--json'])

    return { text: `${doctorText(JSON.parse(stdout), seoRoot)}\n  guard     ${ctx.isGuardOn ? 'on' : 'off'} (Python: ${ctx.python})` }
  } catch (error) {
    return { text: `Doctor failed (${error instanceof Error ? error.message : String(error)}). Is "${ctx.python}" on PATH?` }
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
    pane: { view: 'overview', models: {}, loading: new Set(), host: null, hostSource: null, exported: null, isOpen: false },
    typed: null,
    googleAccount: typeof options.googleAccount === 'string' ? options.googleAccount : 'auto',
    auditsFolder: typeof options.auditsFolder === 'string' ? options.auditsFolder.trim() : '',
    googleApiKey: typeof options.googleApiKey === 'string' ? options.googleApiKey.trim() : '',
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
    } else if (ctx.audit !== null && (ctx.audit.finishMs !== null || Date.now() - ctx.audit.startMs > STALE_MS)) {
      // A finished audit's band stays up until the next prompt; an abandoned one goes too.
      setAudit($, ctx, null)
    }

    return next(e)
  })

  // A slash command may reach the engine as a command run rather than prompt text; observe both.
  on('command.run', { command: ['seo', 'claude-seo:seo'] }, async ($, e, next) => {
    const audit = auditFromPrompt(`/seo ${e.args}`, Date.now())

    if (audit !== null && (ctx.audit === null || ctx.audit.domain !== audit.domain || ctx.audit.finishMs !== null)) {
      follow($, ctx, audit)
    }

    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    if (!isSeoAgent(e.subagentType)) {
      return next(e)
    }

    const isFollowing = ctx.audit !== null && ctx.audit.finishMs === null

    if (ctx.audit !== null && isFollowing) {
      setAudit($, ctx, { ...ctx.audit, agents: { ...ctx.audit.agents, [e.tool_use_id]: { type: e.subagentType, state: 'running', startMs: Date.now() } } })
    }

    const model = ctx.isEconomy && e.model === undefined ? economyModel(e.subagentType) : null
    const result = await next(model === null ? e : { ...e, model })
    const run = ctx.audit?.agents[e.tool_use_id]

    // The agent's id lets its own turn end close it, which a background agent needs.
    if (ctx.audit !== null && run !== undefined && result.agentId !== undefined) {
      setAudit($, ctx, { ...ctx.audit, agents: { ...ctx.audit.agents, [e.tool_use_id]: { ...run, agentId: result.agentId } } })
    }

    return result
  })

  // A foreground Agent call returns when its subagent is done; a background one returns at launch.
  on('tool.call', { tool: 'Agent' }, async ($, e, next) => {
    const result = await next(e)
    const run = ctx.audit?.agents[e.tool_use_id]
    const status = (result.result as { status?: unknown } | undefined)?.status
    const isLaunchOnly = status === 'async_launched' || status === 'remote_launched'

    if (ctx.audit !== null && run !== undefined && run.state === 'running' && !isLaunchOnly) {
      const state = result.deny !== undefined || result.isError === true ? 'failed' : 'done'

      setAudit($, ctx, { ...ctx.audit, agents: { ...ctx.audit.agents, [e.tool_use_id]: { ...run, state, endMs: Date.now() } } })
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
          setAudit($, ctx, after)
        }
      }
    }

    return result
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    const audit = ctx.audit

    if (e.agentId !== undefined) {
      // A subagent finished: close its run (the only signal a background agent gives).
      const entry = audit === null ? undefined : Object.entries(audit.agents).find(([, run]) => run.agentId === e.agentId && run.state === 'running')

      if (audit !== null && entry !== undefined) {
        setAudit($, ctx, { ...audit, agents: { ...audit.agents, [entry[0]]: { ...entry[1], state: 'done', endMs: Date.now() } } })
      }

      return result
    }

    // The receipt goes under the main answer, once, when the audit's data file exists.
    if (audit === null || audit.finishMs !== null || audit.score === null || ctx.isReceiptShown) {
      return result
    }

    const now = Date.now()

    ctx.isReceiptShown = true
    setAudit($, ctx, { ...audit, finishMs: now })

    const receipt = receiptText(audit, now)
    // `next` resolves to the answer itself; any other text is shown beneath it. Keep another mod's line, never the answer.
    const theirs = result.text !== '' && result.text !== e.answer ? result.text : ''

    return { ...result, text: theirs === '' ? receipt : `${theirs}\n${receipt}` }
  })

  on('session.compact', async ($, e, next) => {
    const audit = ctx.audit

    if (e.agentId !== undefined || audit === null || audit.finishMs !== null) {
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
    // Other mods' bands sit below ours rather than being replaced.
    const theirs = await next(e)

    return Box({
      flexDirection: 'column',
      children: [
        Box({
          flexDirection: 'row',
          columnGap: 1,
          children: [
            Text({ color: audit.finishMs === null ? COLORS.blue : COLORS.good, children: [bandText(audit, Date.now(), columns, ctx.isEconomy)] }),
            Button({
              key: 'seo-cockpit-hide',
              label: 'hide',
              plain: true,
              onPress: () => {
                ctx.isBandHidden = true
                syncTicker($, ctx)
                $.ui.invalidate('ui.render')
              },
            }),
          ],
        }),
        theirs,
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
      ...('Markdown' in table && { Markdown: table.Markdown }),
      // An Input exists on every surface but mobile.
      ...(e.surface !== 'mobile' && 'Input' in table && { Input: table.Input }),
      // Every table is completed with every element name, so `'Svg' in table` holds on the terminal too, where an Svg draws nothing.
      ...(e.surface !== 'terminal' && 'Svg' in table && { Svg: table.Svg }),
    }

    ctx.pane.isOpen = true

    return paneView(kit, ctx.pane, Math.max(24, Math.floor(e.props.bodyColumns) - 1), e.props.isFocused, {
      open: tab => {
        ctx.pane.view = tab
        $.ui.invalidate('ui.render')
      },
      back: () => {
        ctx.pane.view = 'overview'
        $.ui.invalidate('ui.render')
      },
      refresh: () => void loadAll($, ctx).catch(() => undefined),
      exportHtml: () => void exportHtml($, ctx, false).catch(() => undefined),
      setTarget: value => void setTarget($, ctx, value).catch(() => undefined),
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
    await restoreAudit($, ctx)

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
