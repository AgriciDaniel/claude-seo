/**
 * Following a claude-seo audit from what the session does: the prompt that
 * starts it, the agents it spawns, the files it writes. Pure: no `$`.
 *
 * An audit writes everything under `{domain}-audit/`: per-agent
 * `findings/*.md`, then `audit-data.json` with the health score
 * (skills/seo-audit/SKILL.md, "Structured Audit Data Envelope").
 */

import { usd } from './verdict'

export type AgentRun = { type: string; state: 'running' | 'done' | 'failed'; startMs: number; endMs?: number; agentId?: string }

export type Audit = {
  domain: string
  startMs: number
  /** By the Agent tool call's id. */
  agents: Record<string, AgentRun>
  /** Findings files written, by file name. */
  findings: string[]
  /** The `{domain}-audit` folder, once a write shows where it is. */
  dir: string | null
  /** What the spend guard logged while the audit ran. */
  spentUsd: number
  score: number | null
  categories: ReadonlyArray<{ name: string; score: number }>
  finishMs: number | null
}

/** The five claude-seo agents that run on Opus (agents/*.md frontmatter). */
export const OPUS_AGENTS: ReadonlySet<string> = new Set(['seo-content', 'seo-geo', 'seo-sxo', 'seo-cluster', 'seo-drift'])

/** An agent type without its plugin namespace (`claude-seo:seo-geo` becomes `seo-geo`). */
export const bareType = (type: string): string => type.split(':').at(-1) ?? type

export const isSeoAgent = (type: string): boolean => /^seo-[a-z-]+$/.test(bareType(type))

/** The model an agent is routed to in economy mode, or null to leave it alone. */
export const economyModel = (type: string): string | null => (OPUS_AGENTS.has(bareType(type)) ? 'sonnet' : null)

/** The host of a URL or bare domain, without `www.`; null when there is none. */
export function domainOf(target: string): string | null {
  const text = target.trim().replace(/^["'<]+|["'>]+$/g, '')

  try {
    const host = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`).hostname.toLowerCase()

    return /\./.test(host) ? host.replace(/^www\./, '') : null
  } catch {
    return null
  }
}

/** The audit a prompt starts (`/seo audit <url>`, also namespaced as `/claude-seo:seo audit`), or null. */
export function auditFromPrompt(text: string, nowMs: number): Audit | null {
  const match = /^\s*\/(?:claude-seo:)?seo\s+audit\s+(\S+)/i.exec(text)
  const domain = match?.[1] === undefined ? null : domainOf(match[1])

  return domain === null ? null : newAudit(domain, nowMs)
}

export function newAudit(domain: string, nowMs: number): Audit {
  return { domain, startMs: nowMs, agents: {}, findings: [], dir: null, spentUsd: 0, score: null, categories: [], finishMs: null }
}

/** Where a written file sits in an audit folder, if it does. */
export function auditPathOf(path: string): { dir: string; domain: string; kind: 'finding' | 'data' | 'other'; name: string } | null {
  const match = /^(.*?([^/\\]+)-audit)[/\\](.+)$/.exec(path)

  if (match === null || match[1] === undefined || match[2] === undefined || match[3] === undefined) {
    return null
  }

  const rest = match[3]
  const name = rest.split(/[/\\]/).at(-1) ?? rest
  const kind = /^findings[/\\][^/\\]+\.md$/.test(rest) ? 'finding' : rest === 'audit-data.json' ? 'data' : 'other'

  return { dir: match[1], domain: match[2], kind, name }
}

/** The health score and category scores from an audit-data.json text; nulls when unreadable. */
export function scoresOf(text: string): { score: number | null; categories: Array<{ name: string; score: number }> } {
  try {
    const data = JSON.parse(text) as { summary?: { health_score?: unknown }; categories?: unknown }
    const raw = data.summary?.health_score
    const categories = Array.isArray(data.categories)
      ? data.categories.flatMap(row => {
          const { name, score } = (row ?? {}) as { name?: unknown; score?: unknown }

          return typeof name === 'string' && typeof score === 'number' && Number.isFinite(score) ? [{ name, score }] : []
        })
      : []

    return { score: typeof raw === 'number' && Number.isFinite(raw) ? raw : null, categories }
  } catch {
    return { score: null, categories: [] }
  }
}

/** Records a write; returns the audit it belongs to (started from the folder when none is running). */
export function noteWrite(audit: Audit | null, path: string, content: string | undefined, nowMs: number): Audit | null {
  const where = auditPathOf(path)

  if (where === null) {
    return audit
  }

  const current = audit === null || audit.finishMs !== null ? newAudit(domainOf(where.domain) ?? where.domain, nowMs) : audit
  const next: Audit = { ...current, dir: where.dir }

  if (where.kind === 'finding' && !next.findings.includes(where.name)) {
    next.findings = [...next.findings, where.name]
  }

  if (where.kind === 'data' && content !== undefined) {
    const { score, categories } = scoresOf(content)

    next.score = score
    next.categories = categories
  }

  return next
}

const count = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`

export const elapsed = (ms: number): string => {
  const seconds = Math.max(0, Math.round(ms / 1000))

  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m${String(seconds % 60).padStart(2, '0')}s`
}

/** Agent counts: running, done (failed ones count as done, and are named). */
export function tally(audit: Audit): { running: number; done: number; failed: number } {
  const runs = Object.values(audit.agents)

  return {
    running: runs.filter(run => run.state === 'running').length,
    done: runs.filter(run => run.state !== 'running').length,
    failed: runs.filter(run => run.state === 'failed').length,
  }
}

/** The band's one line, cut to `columns`. */
export function bandText(audit: Audit, nowMs: number, columns: number, isEconomy: boolean): string {
  const { running, done, failed } = tally(audit)
  const parts = [
    `seo audit ${audit.domain}`,
    audit.finishMs !== null ? `done${audit.score === null ? '' : `, score ${audit.score}/100`}` : `${running} running, ${done} done${failed > 0 ? ` (${failed} failed)` : ''}`,
    `findings ${audit.findings.length}`,
    `spend ${usd(audit.spentUsd)}`,
    elapsed((audit.finishMs ?? nowMs) - audit.startMs),
    ...(isEconomy ? ['economy'] : []),
  ]
  const line = parts.join('  ')

  return line.length <= columns ? line : `${line.slice(0, Math.max(0, columns - 1))}…`
}

/** The line shown under the answer once the audit's data file is written. */
export function receiptText(audit: Audit, nowMs: number): string {
  const { done, failed } = tally(audit)
  const report = audit.dir === null ? `${audit.domain}-audit/` : `${audit.dir}/FULL-AUDIT-REPORT.md`
  const weakest = [...audit.categories].sort((a, b) => a.score - b.score).slice(0, 2).map(row => `${row.name} ${row.score}`)

  return [
    `seo audit ${audit.domain}: ${audit.score === null ? 'no score' : `score ${audit.score}/100`}`,
    weakest.length > 0 ? `weakest ${weakest.join(', ')}` : null,
    `${count(done, 'agent')}${failed > 0 ? ` (${failed} failed)` : ''}`,
    count(audit.findings.length, 'findings file'),
    `spend ${usd(audit.spentUsd)}`,
    elapsed(nowMs - audit.startMs),
    report,
  ]
    .filter((part): part is string => part !== null)
    .join('  |  ')
}

/** What compaction is asked to keep while an audit runs. */
export function compactInstructions(audit: Audit): string {
  const done = Object.values(audit.agents).filter(run => run.state !== 'running').map(run => bareType(run.type))
  const running = Object.values(audit.agents).filter(run => run.state === 'running').map(run => bareType(run.type))

  return [
    `A claude-seo audit of ${audit.domain} is in progress. Keep in the summary:`,
    `- the output folder: ${audit.dir ?? `${audit.domain}-audit/`} (findings in findings/, then audit-data.json, FULL-AUDIT-REPORT.md, ACTION-PLAN.md)`,
    `- agents finished: ${done.length > 0 ? done.join(', ') : 'none yet'}; still running: ${running.length > 0 ? running.join(', ') : 'none'}`,
    `- findings files written: ${audit.findings.length > 0 ? audit.findings.join(', ') : 'none yet'}`,
    '- the business type detected, the crawl scope, and any finding not yet written to a file',
  ].join('\n')
}
