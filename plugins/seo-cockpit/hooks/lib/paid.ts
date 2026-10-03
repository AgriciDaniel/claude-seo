/**
 * Which tool calls spend money, and how each one is priced.
 *
 * Pure: no `$`. register.ts asks `classify` about every tool call it sees and
 * only holds the ones it returns a PaidCall for.
 */

export type PaidCall =
  /**
   * Priced by claude-seo's DataForSEO cost table: an MCP tool, or a script
   * that bills one or more endpoints (`compare` bills two).
   */
  | { kind: 'dataforseo'; endpoints: readonly string[]; label: string }
  /** Anything else that bills: no cost table, so the person decides. */
  | { kind: 'ask'; label: string; allowKey: string }

/** MCP servers whose calls bill a paid account. Matched on the server segment of `mcp__<server>__<tool>`. */
const PAID_MCP_SERVERS: ReadonlyArray<{ pattern: RegExp; label: string }> = [
  { pattern: /ahrefs/i, label: 'Ahrefs' },
  { pattern: /se-?ranking/i, label: 'SE Ranking' },
  { pattern: /firecrawl/i, label: 'Firecrawl' },
  { pattern: /profound/i, label: 'Profound' },
  { pattern: /banana/i, label: 'Gemini image generation' },
]

/**
 * DataForSEO lookups that list reference data and cost nothing: locations,
 * languages, filters, categories, model lists.
 */
const FREE_DATAFORSEO = /(?:_locations|_languages|_filters|_loc_and_lang|_categories|llm_models)$/

/** claude-seo scripts that bill, but have no cost-table row: the person decides. */
const PAID_SCRIPTS: ReadonlyArray<{ pattern: RegExp; label: string }> = [
  { pattern: /\bmoz_api\.py\b/, label: 'Moz API' },
  { pattern: /\bkeywordseverywhere_api\.py\b/, label: 'Keywords Everywhere' },
  { pattern: /\bnlp_analyze\.py\b/, label: 'Google Cloud Natural Language (billed past the free tier)' },
  { pattern: /\bindexing_notify\.py\b/, label: 'Google Indexing API (uses daily quota)' },
  // Either the launcher form (`run --extension banana generate.py`) or a direct path, either slash.
  { pattern: /--extension\s+banana\s+(?:generate|batch|edit)\.py\b|\bbanana[\\/]scripts[\\/](?:generate|batch|edit)\.py\b/, label: 'Gemini image generation' },
]

/** Paid APIs Claude reaches with curl or WebFetch, keyed by host (SE Ranking and Profound ship no MCP server). */
const PAID_HOSTS: ReadonlyArray<{ pattern: RegExp; label: string }> = [
  { pattern: /\bapi\d?\.seranking\.com\b/i, label: 'SE Ranking API' },
  { pattern: /\bapi\.tryprofound\.com\b/i, label: 'Profound API' },
  { pattern: /\bapi\.dataforseo\.com\b/i, label: 'DataForSEO API (direct, not priced)' },
]

/** Splits `mcp__<server>__<tool>`; null for a tool that is not an MCP tool. */
export function mcpParts(tool: string): { server: string; name: string } | null {
  const match = /^mcp__(.+?)__(.+)$/.exec(tool)

  if (match === null || match[1] === undefined || match[2] === undefined) {
    return null
  }

  return { server: match[1], name: match[2] }
}

/** The single commands of a shell line: split on `&&`, `||`, `;`, `|` and newlines. */
export function segmentsOf(command: string): string[] {
  return command.split(/&&|\|\||[;|\n]/).map(part => part.trim()).filter(part => part !== '')
}

/**
 * The DataForSEO endpoints a `dataforseo_merchant.py` run bills, from its
 * subcommand and `--marketplace`: `search` bills one (Google unless
 * `--marketplace amazon`), `sellers` one, `compare` Google then Amazon.
 */
export function merchantEndpoints(segment: string): string[] {
  const sub = /dataforseo_merchant\.py\s+(\w+)/.exec(segment)?.[1]

  if (sub === 'sellers') {
    return ['merchant_google_sellers_search']
  }

  if (sub === 'compare') {
    return ['merchant_google_products_search', 'merchant_amazon_products_search']
  }

  return /--marketplace[=\s]+["']?amazon\b/i.test(segment) ? ['merchant_amazon_products_search'] : ['merchant_google_products_search']
}

function classifySegment(segment: string): PaidCall | null {
  if (/\bdataforseo_merchant\.py\b/.test(segment)) {
    const endpoints = merchantEndpoints(segment)

    return { kind: 'dataforseo', endpoints, label: `DataForSEO Merchant (${endpoints.join(' + ')})` }
  }

  const script = PAID_SCRIPTS.find(entry => entry.pattern.test(segment))

  if (script !== undefined) {
    return { kind: 'ask', label: script.label, allowKey: `script:${script.label}` }
  }

  const host = PAID_HOSTS.find(entry => entry.pattern.test(segment))

  return host === undefined ? null : { kind: 'ask', label: host.label, allowKey: `host:${host.label}` }
}

/** Merges the paid parts of one shell line: every DataForSEO endpoint, else the first ask. */
function merge(calls: readonly PaidCall[]): PaidCall | null {
  const priced = calls.flatMap(call => (call.kind === 'dataforseo' ? call.endpoints : []))
  const ask = calls.find(call => call.kind === 'ask')

  // A line that mixes a priced endpoint and an unpriced paid script asks: the person sees the whole line.
  if (ask !== undefined) {
    return priced.length === 0 ? ask : { kind: 'ask', label: `${ask.label} and DataForSEO`, allowKey: `line:${ask.label}+dataforseo` }
  }

  return priced.length === 0 ? null : { kind: 'dataforseo', endpoints: priced, label: calls.map(call => call.label).join(', ') }
}

/**
 * The paid call a tool call is, or null when it costs nothing.
 *
 * A shell line is classified one command at a time, so a cost check chained
 * in front of a paid script (`check x && run merchant.py`) never hides it.
 *
 * @param tool the tool's name as `tool.call` reports it
 * @param command the shell command, for Bash and PowerShell
 * @param url the URL, for WebFetch
 */
export function classify(tool: string, command: string | undefined, url?: string): PaidCall | null {
  const mcp = mcpParts(tool)

  if (mcp !== null) {
    if (/dataforseo/i.test(mcp.server)) {
      return FREE_DATAFORSEO.test(mcp.name) ? null : { kind: 'dataforseo', endpoints: [mcp.name], label: `DataForSEO ${mcp.name}` }
    }

    const paid = PAID_MCP_SERVERS.find(entry => entry.pattern.test(mcp.server))

    return paid === undefined ? null : { kind: 'ask', label: `${paid.label} (${mcp.name})`, allowKey: `mcp:${mcp.server}` }
  }

  if (tool === 'WebFetch' && url !== undefined) {
    const host = PAID_HOSTS.find(entry => entry.pattern.test(url))

    return host === undefined ? null : { kind: 'ask', label: host.label, allowKey: `host:${host.label}` }
  }

  if ((tool !== 'Bash' && tool !== 'PowerShell') || command === undefined) {
    return null
  }

  return merge(segmentsOf(command).map(classifySegment).filter((call): call is PaidCall => call !== null))
}
