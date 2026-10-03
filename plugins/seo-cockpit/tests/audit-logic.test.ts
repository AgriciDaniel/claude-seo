import { describe, expect, test } from 'claude-code/testing'

import { auditFromPrompt, auditPathOf, bandText, compactInstructions, domainOf, economyModel, isSeoAgent, newAudit, noteWrite, receiptText, scoresOf } from '../hooks/lib/audit'

const DATA = JSON.stringify({ summary: { health_score: 72 }, categories: [{ name: 'Technical SEO', score: 81 }, { name: 'Schema', score: 40 }, { name: 'Content', score: 55 }] })

describe('starting an audit', () => {
  test('the /seo audit prompt starts one, namespaced or not', () => {
    expect(auditFromPrompt('/seo audit https://www.Example.com/shop', 5)?.domain).toBe('example.com')
    expect(auditFromPrompt('/claude-seo:seo audit example.org', 5)?.domain).toBe('example.org')
    expect(auditFromPrompt('/seo page https://example.com', 5)).toBeNull()
    expect(auditFromPrompt('please audit my site', 5)).toBeNull()
  })

  test('domainOf needs a dotted host', () => {
    expect(domainOf('<https://sub.example.co.uk/x>')).toBe('sub.example.co.uk')
    expect(domainOf('localhost')).toBeNull()
  })

  test('a write into a *-audit folder starts one when none is running', () => {
    const audit = noteWrite(null, '/work/example.com-audit/findings/technical.md', '# t', 10)

    expect(audit?.domain).toBe('example.com')
    expect(audit?.dir).toBe('/work/example.com-audit')
    expect(audit?.findings).toEqual(['technical.md'])
  })
})

describe('following it', () => {
  test('auditPathOf tells findings, data and other files apart, either slash', () => {
    expect(auditPathOf('/w/a.com-audit/findings/schema.md')?.kind).toBe('finding')
    expect(auditPathOf('C:\\w\\a.com-audit\\audit-data.json')?.kind).toBe('data')
    expect(auditPathOf('/w/a.com-audit/screenshots/x.png')?.kind).toBe('other')
    expect(auditPathOf('/w/src/index.html')).toBeNull()
  })

  test('the data file carries the score; junk carries none', () => {
    expect(scoresOf(DATA).score).toBe(72)
    expect(scoresOf(DATA).categories.length).toBe(3)
    expect(scoresOf('{oops')).toEqual({ score: null, categories: [] })
  })

  test('a findings file is counted once', () => {
    const one = noteWrite(newAudit('a.com', 0), '/w/a.com-audit/findings/geo.md', 'x', 1)
    const two = noteWrite(one, '/w/a.com-audit/findings/geo.md', 'y', 2)

    expect(two?.findings).toEqual(['geo.md'])
  })

  test('economy routes only the five Opus agents', () => {
    expect(economyModel('claude-seo:seo-geo')).toBe('sonnet')
    expect(economyModel('seo-technical')).toBeNull()
    expect(isSeoAgent('claude-seo:seo-technical')).toBe(true)
    expect(isSeoAgent('Explore')).toBe(false)
  })
})

describe('what it shows', () => {
  const audit = {
    ...newAudit('example.com', 0),
    dir: '/w/example.com-audit',
    agents: { a: { type: 'seo-technical', state: 'done' as const, startMs: 0 }, b: { type: 'seo-geo', state: 'running' as const, startMs: 0 } },
    findings: ['technical.md'],
    spentUsd: 0.42,
  }

  test('the band line counts agents, findings, spend and time, and fits the width', () => {
    expect(bandText(audit, 252_000, 200, true)).toBe('seo audit example.com  1 running, 1 done  findings 1  spend $0.42  4m12s  economy')
    expect(bandText(audit, 252_000, 20, false).length).toBe(20)
  })

  test('the receipt names the score, the weakest categories and the report', () => {
    const done = { ...audit, ...scoresOf(DATA) }
    const text = receiptText(done, 60_000)

    expect(text).toContain('score 72/100')
    expect(text).toContain('weakest Schema 40, Content 55')
    expect(text).toContain('/w/example.com-audit/FULL-AUDIT-REPORT.md')
  })

  test('compaction keeps the folder, agents and findings', () => {
    const text = compactInstructions(audit)

    expect(text).toContain('/w/example.com-audit')
    expect(text).toContain('agents finished: seo-technical; still running: seo-geo')
    expect(text).toContain('technical.md')
  })
})
