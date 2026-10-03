import type { EngineInterface, On, PluginOptions, ResultOf } from 'claude-code'

import { doctorText, spendText } from './lib/format'
import { classify, type PaidCall } from './lib/paid'
import { candidatesOf, joinPath, latestVersion, MARKER } from './lib/root'
import { combine, isUnpriced, parseCheck, usd, type Verdict } from './lib/verdict'

type ToolResult = ResultOf['tool.call']

/** What one activation knows: its settings, and what it has learned since it loaded. */
type Ctx = {
  setting: string
  python: string
  isGuardOn: boolean
  /** Paid tools the person allowed until the plugin reloads. */
  allowed: Set<string>
  root: string | null
}

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

async function registerCommands($: EngineInterface): Promise<void> {
  await Promise.all([
    $.command.register({ name: 'seo-spend', description: 'claude-seo DataForSEO spend: today, 7 and 30 days, by endpoint', immediate: true }).catch(() => undefined),
    $.command.register({ name: 'seo-doctor', description: 'claude-seo runtime readiness and where it is installed', immediate: true }).catch(() => undefined),
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
}
