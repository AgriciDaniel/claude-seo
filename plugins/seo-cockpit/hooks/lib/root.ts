/**
 * Finding claude-seo from seo-cockpit's own folder. Pure string work; the
 * caller checks each candidate on disk.
 *
 * Three layouts:
 *  - a setting the person gave (`claudeSeoRoot`);
 *  - a checkout: seo-cockpit is `<claude-seo>/plugins/seo-cockpit`;
 *  - an install: both live in the plugin cache as
 *    `<cache>/<marketplace>/seo-cockpit/<version>` and
 *    `<cache>/<marketplace>/claude-seo/<version>`.
 */

const trimSlash = (path: string): string => path.replace(/[\\/]+$/, '')

/** The parent folder, or the path itself at a root. */
export function parentOf(path: string): string {
  const clean = trimSlash(path)
  const cut = Math.max(clean.lastIndexOf('/'), clean.lastIndexOf('\\'))

  return cut <= 0 ? clean : clean.slice(0, cut)
}

export const joinPath = (...parts: string[]): string => parts.map((part, i) => (i === 0 ? trimSlash(part) : part.replace(/^[\\/]+|[\\/]+$/g, ''))).join('/')

/** The file whose presence marks a claude-seo folder. */
export const MARKER = 'scripts/dataforseo_costs.py'

/**
 * Folders that may hold claude-seo, most specific first. The cache folders
 * are returned for the caller to list: `cacheDir` is claude-seo under this
 * plugin's own marketplace, `cacheRoot` holds every marketplace (claude-seo
 * may come from another one, such as a community mirror).
 */
export function candidatesOf(pluginRoot: string, setting: string): { fixed: string[]; cacheDir: string; cacheRoot: string } {
  const fixed: string[] = []

  if (setting.trim() !== '') {
    fixed.push(trimSlash(setting.trim()))
  }

  // Checkout: <claude-seo>/plugins/seo-cockpit
  const grandparent = parentOf(parentOf(pluginRoot))

  fixed.push(grandparent)

  // Install: <cache>/<marketplace>/seo-cockpit/<version> -> <cache>/<marketplace>/claude-seo
  return { fixed, cacheDir: joinPath(grandparent, 'claude-seo'), cacheRoot: parentOf(grandparent) }
}

/** `[major, minor, patch, ...]` and whether a pre-release tag follows (`2.5.0-rc1`). */
function partsOf(version: string): { numbers: number[]; isPrerelease: boolean } {
  const [core = '', ...rest] = version.split(/[-+]/)

  return { numbers: core.split('.').map(part => Number.parseInt(part, 10) || 0), isPrerelease: rest.length > 0 && version.includes('-') }
}

/** Compares dotted versions numerically (`2.10.0` after `2.9.1`); a release ranks above its pre-releases. */
function compareVersions(a: string, b: string): number {
  const pa = partsOf(a)
  const pb = partsOf(b)

  for (let i = 0; i < Math.max(pa.numbers.length, pb.numbers.length); i++) {
    const diff = (pa.numbers[i] ?? 0) - (pb.numbers[i] ?? 0)

    if (diff !== 0) {
      return diff
    }
  }

  return pa.isPrerelease === pb.isPrerelease ? a.localeCompare(b) : pa.isPrerelease ? -1 : 1
}

/** The highest version folder name, or null when none looks like a version. */
export function latestVersion(names: readonly string[]): string | null {
  const versions = names.filter(name => /^\d+(?:\.\d+)*(?:[-+].*)?$/.test(name))

  return versions.length === 0 ? null : [...versions].sort(compareVersions).at(-1) ?? null
}

/**
 * The environment claude-seo's runtime.py must see, so it finds the Python
 * environment claude-seo set up, not one keyed to whichever plugin is calling.
 *
 * runtime.py picks its folder from CLAUDE_PLUGIN_DATA, which Claude Code sets
 * per plugin; inherited from this mod's process it names the wrong plugin.
 * - An install (`<home>/.claude/plugins/cache/<mkt>/claude-seo/<ver>`): point
 *   it at claude-seo's own data folder, `<home>/.claude/plugins/data/claude-seo-<mkt>`,
 *   where `/seo setup` puts the environment.
 * - A checkout or a custom folder: clear both variables, so runtime.py uses
 *   its own standalone rule (the checkout's `.venv`).
 */
export function runtimeEnvOf(seoRoot: string): Record<string, string> {
  const match = /^(.*)[\\/]plugins[\\/]cache[\\/]([^\\/]+)[\\/]claude-seo[\\/][^\\/]+[\\/]?$/.exec(seoRoot)

  return match === null || match[1] === undefined || match[2] === undefined
    ? { CLAUDE_PLUGIN_DATA: '', CLAUDE_PLUGIN_ROOT: '' }
    : { CLAUDE_PLUGIN_DATA: `${match[1]}/plugins/data/claude-seo-${match[2]}`, CLAUDE_PLUGIN_ROOT: seoRoot }
}
