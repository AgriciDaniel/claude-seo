import type { On } from 'claude-code'

/**
 * The world beneath seo-cockpit, in memory: what each claude-seo script
 * answers, what the person answers when asked, and a record of everything
 * the plugin asked for.
 */
export type World = {
  /** Every argv the plugin ran, joined by spaces, after the interpreter. */
  runs: string[]
  /** The environment each run was given, in the same order. */
  envs: Array<Readonly<Record<string, string>>>
  /** Every question the plugin asked. */
  asked: string[]
  /** Calls that reached the tool beneath the plugin. */
  ran: string[]
  commands: string[]
}

type Reply = { exitCode?: number; stdout?: unknown; stderr?: string } | 'throw'

export type Setup = {
  /** What the tool beneath the plugin answers: a result (default) or an error result. */
  toolFails?: boolean
  /** Answers by script subcommand (`check`, `log`, `today`, `summary`, `doctor`). */
  scripts?: Partial<Record<string, Reply>>
  /** The label the person picks; `null` dismisses the dialog. */
  answer?: string | null
  /** Whether claude-seo is found on disk. */
  hasRoot?: boolean
  /** Folder listings by path, for tests that need files to exist; any other path is missing. */
  listing?: Readonly<Record<string, ReadonlyArray<{ name: string; kind: 'file' | 'dir' }>>>
}

export function worldOf(on: On, setup: Setup = {}): World {
  const world: World = { runs: [], envs: [], asked: [], ran: [], commands: [] }

  // The kit's bottom hook throws for an event no stub answers; a session start needs one.
  on('session.start', () => ({ cwd: '/work' }))
  on('fs.exists', ($, e) => ({ value: setup.hasRoot !== false && e.path.endsWith('scripts/dataforseo_costs.py') }))
  on('fs.list', ($, e) => {
    const entries = setup.listing?.[e.path]

    return (entries === undefined ? { deny: 'ENOENT' } : { value: entries.map(entry => ({ ...entry, size: 0 })) }) as never
  })

  on('process.run', ($, e) => {
    const args = e.argv.slice(1)
    const script = (args[0] ?? '').split('/').at(-1) ?? ''
    const sub = args[1] ?? ''

    world.runs.push([script, ...args.slice(1)].join(' '))
    world.envs.push(e.init?.env ?? {})

    const reply = setup.scripts?.[sub]

    if (reply === 'throw') {
      return { deny: 'spawn python3 ENOENT' }
    }

    const stdout = reply?.stdout === undefined ? '{}' : typeof reply.stdout === 'string' ? reply.stdout : JSON.stringify(reply.stdout)

    return { value: { exitCode: reply?.exitCode ?? 0, stdout, stderr: reply?.stderr ?? '', isStdoutTruncated: false, isStderrTruncated: false } }
  })

  on('command.register', ($, e) => {
    world.commands.push(e.name)

    return { value: { command: e.name } }
  })

  // The dialog `$.ui.ask` raises, and the tool beneath the plugin.
  on('tool.call', ($, e) => {
    if (e.tool === 'AskUserQuestion') {
      const question = e.questions[0]?.question ?? ''

      world.asked.push(question)

      return setup.answer === null || setup.answer === undefined
        ? { deny: 'dismissed' }
        : { result: { questions: e.questions, answers: { [question]: setup.answer } }, text: setup.answer }
    }

    world.ran.push(e.tool)

    return setup.toolFails === true ? { isError: true as const, result: 'error', text: 'task failed' } : { result: 'ok', text: 'ok' }
  })

  return world
}

export const SESSION = { surface: 'terminal' as const, isInteractive: true, cwd: '/work' }

export const command = (name: string, args = '') => ({
  command: name,
  args,
  origin: { kind: 'composer' as const },
  presentation: { isFullscreen: false, columns: 120 },
})

export const APPROVED = { status: 'approved', total_cost_usd: 0.002, today_spend_usd: 1.5, daily_remaining_usd: 8.5 }
export const NEEDS = { status: 'needs_approval', total_cost_usd: 0.103, today_spend_usd: 1.5, daily_remaining_usd: 8.5, approval_reason: 'warn_endpoint', message: 'm' }
export const BLOCKED = { status: 'blocked', message: 'Daily limit $10.00 would be exceeded.' }
