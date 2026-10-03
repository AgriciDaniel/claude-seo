/**
 * Reading `dataforseo_costs.py check` output into a decision the guard acts on.
 *
 * Pure. Anything that does not parse as a known verdict becomes `error`, and
 * the guard holds the call: a ledger that cannot be read never waves spend through.
 */

export type Verdict =
  | { decision: 'approved'; costUsd: number; todayUsd: number; remainingUsd: number }
  | { decision: 'needs_approval'; costUsd: number; todayUsd: number; remainingUsd: number | null; reason: string; message: string }
  | { decision: 'blocked'; message: string }
  | { decision: 'error'; message: string }

const num = (value: unknown, fallback: number): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback

/**
 * @param exitCode the script's exit status
 * @param stdout what it printed
 */
export function parseCheck(exitCode: number, stdout: string): Verdict {
  if (exitCode !== 0) {
    // A ledger error exits 1 with its reason as JSON on stdout.
    const reason = /"message"\s*:\s*"([^"]*)"/.exec(stdout)?.[1]

    return { decision: 'error', message: `cost check exited ${exitCode}${reason ? ` (${reason})` : ''}` }
  }

  let data: Record<string, unknown>

  try {
    const parsed: unknown = JSON.parse(stdout)

    if (typeof parsed !== 'object' || parsed === null) {
      return { decision: 'error', message: 'cost check printed no JSON object' }
    }

    data = parsed as Record<string, unknown>
  } catch {
    return { decision: 'error', message: 'cost check printed no JSON' }
  }

  const message = typeof data.message === 'string' ? data.message : ''

  switch (data.status) {
    case 'approved':
      return {
        decision: 'approved',
        costUsd: num(data.total_cost_usd, 0),
        todayUsd: num(data.today_spend_usd, 0),
        remainingUsd: num(data.daily_remaining_usd, 0),
      }
    case 'needs_approval':
      return {
        decision: 'needs_approval',
        // An unknown endpoint reports only an estimate.
        costUsd: num(data.total_cost_usd, num(data.estimated_cost_usd, 0)),
        todayUsd: num(data.today_spend_usd, 0),
        remainingUsd: typeof data.daily_remaining_usd === 'number' ? data.daily_remaining_usd : null,
        reason: typeof data.approval_reason === 'string' ? data.approval_reason : 'needs_approval',
        message,
      }
    case 'blocked':
      return { decision: 'blocked', message: message || 'daily DataForSEO limit reached' }
    default:
      return { decision: 'error', message: `cost check returned an unknown status` }
  }
}

export const usd = (value: number): string => `$${value.toFixed(value !== 0 && value < 0.1 ? 3 : 2)}`

/** One decision for a call that bills several endpoints: the strictest verdict wins, costs add up. */
export function combine(verdicts: readonly Verdict[]): Verdict {
  const first = verdicts.find(v => v.decision === 'error') ?? verdicts.find(v => v.decision === 'blocked')

  if (first !== undefined || verdicts.length === 0) {
    return first ?? { decision: 'error', message: 'no cost check ran' }
  }

  const priced = verdicts as ReadonlyArray<Extract<Verdict, { costUsd: number }>>
  const costUsd = priced.reduce((sum, v) => sum + v.costUsd, 0)
  const todayUsd = Math.max(...priced.map(v => v.todayUsd))
  const asks = priced.filter((v): v is Extract<Verdict, { decision: 'needs_approval' }> => v.decision === 'needs_approval')

  if (asks.length === 0) {
    return { decision: 'approved', costUsd, todayUsd, remainingUsd: Math.min(...priced.map(v => (v.decision === 'approved' ? v.remainingUsd : Infinity))) }
  }

  const remaining = priced.map(v => v.remainingUsd).filter((r): r is number => r !== null)

  return {
    decision: 'needs_approval',
    costUsd,
    todayUsd,
    remainingUsd: remaining.length === 0 ? null : Math.min(...remaining),
    reason: [...new Set(asks.map(v => v.reason))].join(', '),
    message: asks.map(v => v.message).join(' '),
  }
}

/** True when the cost table had no price for the endpoint, so the figure is a guess and is not logged. */
export const isUnpriced = (verdict: Verdict): boolean => verdict.decision === 'needs_approval' && verdict.reason.split(', ').includes('unknown_endpoint')
