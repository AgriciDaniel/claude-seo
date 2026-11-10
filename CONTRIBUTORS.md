# Contributors

Claude SEO is created and maintained by [@AgriciDaniel](https://github.com/AgriciDaniel).

This project thrives thanks to community contributions from the
[AI Marketing Hub](https://www.skool.com/ai-marketing-hub) Pro Hub Challenge
and open-source pull requests.

## Pro Hub Challenge (v1.9.0)

The Pro Hub Challenge invited community members to build extensions for Claude SEO
and Claude Blog. These submissions were reviewed, security-audited, and integrated
into v1.9.0 with the contributors' permission.

| Contributor | Submission | Repo | Integrated As |
|------------|------------|------|--------------|
| **Lutfiya Miller** (Winner) | Semantic Cluster Engine | [Drfiya/semantic-cluster-engine](https://github.com/Drfiya/semantic-cluster-engine) | `seo-cluster` (core skill) |
| **Chris Muller** | Multi-lingual SEO | [Chriss54/claude-blog-multilingual](https://github.com/Chriss54/claude-blog-multilingual) | `seo-hreflang` enhancements (cultural profiles, locale formats, content parity) |
| **Florian Schmitz** | SXO Skill | [tools-enerix/claude-sxo-skill](https://github.com/tools-enerix/claude-sxo-skill) | `seo-sxo` (core skill) |
| **Dan Colta** | SEO Drift Monitor | [dancolta/seo-drift-monitor](https://github.com/dancolta/seo-drift-monitor) | `seo-drift` (core skill) |
| **Matej Marjanovic** | E-commerce + DataForSEO Cost Config + ASO + Platform Support | [matej-marjanovic/claude-seo](https://github.com/matej-marjanovic/claude-seo) | `seo-ecommerce` (core), cost infrastructure, `seo-aso` (extension), `AGENTS.md` |
| **Benjamin Samar** | SEO Dungeon | n/a | Reviewed (not integrated in v1.9.0) |

## Framework Integration (v1.9.5)

| Source | Type | License | Integrated As |
|--------|------|---------|--------------|
| **[FLOW](https://github.com/AgriciDaniel/flow)** by Daniel Agrici | 41 AI prompts + framework doc + bibliography | CC BY 4.0 | `seo-flow` skill + `skills/seo-flow/references/` |

Attribution header on every bundled prompt file (automated by `scripts/sync_flow.py`).

## Community Pull Requests

### v2.5.1

Credit is preserved when a patch was superseded by another fix for the same bug.

| Contributor | PR | Contribution category | Review outcome |
|------------|----|-----------------------|----------------|
| [@rudycelekli](https://github.com/rudycelekli) | [#365](https://github.com/AgriciDaniel/claude-seo/pull/365), [#367](https://github.com/AgriciDaniel/claude-seo/pull/367), [#368](https://github.com/AgriciDaniel/claude-seo/pull/368), [#369](https://github.com/AgriciDaniel/claude-seo/pull/369), [#370](https://github.com/AgriciDaniel/claude-seo/pull/370), [#371](https://github.com/AgriciDaniel/claude-seo/pull/371), [#372](https://github.com/AgriciDaniel/claude-seo/pull/372), [#373](https://github.com/AgriciDaniel/claude-seo/pull/373), [#374](https://github.com/AgriciDaniel/claude-seo/pull/374), [#375](https://github.com/AgriciDaniel/claude-seo/pull/375), [#376](https://github.com/AgriciDaniel/claude-seo/pull/376), [#377](https://github.com/AgriciDaniel/claude-seo/pull/377), [#378](https://github.com/AgriciDaniel/claude-seo/pull/378), [#379](https://github.com/AgriciDaniel/claude-seo/pull/379), [#380](https://github.com/AgriciDaniel/claude-seo/pull/380), [#381](https://github.com/AgriciDaniel/claude-seo/pull/381), [#400](https://github.com/AgriciDaniel/claude-seo/pull/400) | Fifteen fixes across sitemaps, IndexNow, content checks, charset detection, schema validation and the `/seo` command | 15 merged; #365 and #367 superseded by #389 and #359, with a test from #365 carried over |
| [@lab1207](https://github.com/lab1207) | [#358](https://github.com/AgriciDaniel/claude-seo/pull/358), [#359](https://github.com/AgriciDaniel/claude-seo/pull/359) | JSON-LD `@graph` handling in the parser, skill and agent; first fix for the list-valued `@type` hook crash | #359 merged; #358 superseded by #389, with its `@graph` test carried over |
| [@deosiree](https://github.com/deosiree) | [#389](https://github.com/AgriciDaniel/claude-seo/pull/389) | List-valued JSON-LD `@type` in the schema hook, with a warning for malformed values | Merged |
| [@Afloat16](https://github.com/Afloat16) | [#403](https://github.com/AgriciDaniel/claude-seo/pull/403), [#404](https://github.com/AgriciDaniel/claude-seo/pull/404), [#405](https://github.com/AgriciDaniel/claude-seo/pull/405) | Drift URL and robots directive parsing; brand suffix word boundaries | Merged |
| [@HelloWorld3326](https://github.com/HelloWorld3326) | [#384](https://github.com/AgriciDaniel/claude-seo/pull/384), [#385](https://github.com/AgriciDaniel/claude-seo/pull/385) | UTF-8 BOM sitemaps; `<base href>` resolution for links and images | Merged, with follow-up fixes |
| [@switchcasestudio](https://github.com/switchcasestudio) | [#345](https://github.com/AgriciDaniel/claude-seo/pull/345), [#346](https://github.com/AgriciDaniel/claude-seo/pull/346) | Inline-tag spacing in headings and link text; Natural Language v1 request field | Merged |
| [@zhangkom](https://github.com/zhangkom) | [#408](https://github.com/AgriciDaniel/claude-seo/pull/408), [#409](https://github.com/AgriciDaniel/claude-seo/pull/409) | IndexNow text-mode errors; Indexing API quota stop | Merged |
| [@xunguangzlj-cloud](https://github.com/xunguangzlj-cloud) | [#393](https://github.com/AgriciDaniel/claude-seo/pull/393), [#406](https://github.com/AgriciDaniel/claude-seo/pull/406) | CrUX zero-baseline trend; GA4 top-pages error reporting | Merged, with a report follow-up fix |
| [@AdityaWagh06](https://github.com/AdityaWagh06) | [#413](https://github.com/AgriciDaniel/claude-seo/pull/413), [#414](https://github.com/AgriciDaniel/claude-seo/pull/414) | Deprecated-types reference link; hook launcher skip for files without JSON-LD | Merged, with the skip scoped to the schema hook |
| [@dajiaohuang](https://github.com/dajiaohuang) | [#387](https://github.com/AgriciDaniel/claude-seo/pull/387) | Google property selection bound to the audited domain | Merged, with follow-up fixes |
| [@hboon](https://github.com/hboon) | [#364](https://github.com/AgriciDaniel/claude-seo/pull/364) | Backlink verification: exact target match, page-level nofollow, GET when HEAD fails | Merged, with follow-up fixes |
| [@whatcodehaveyougit](https://github.com/whatcodehaveyougit) | [#332](https://github.com/AgriciDaniel/claude-seo/pull/332) | Image format judged by the served bytes, not the URL extension | Merged, with follow-up fixes |
| [@pucilpet](https://github.com/pucilpet) | [#418](https://github.com/AgriciDaniel/claude-seo/pull/418) | Common Crawl newest web graph release discovery | Merged |
| [@Ethereal49](https://github.com/Ethereal49) | [#396](https://github.com/AgriciDaniel/claude-seo/pull/396) | Matomo top-pages error reporting | Merged |
| [@angelocastellani](https://github.com/angelocastellani) | [#386](https://github.com/AgriciDaniel/claude-seo/pull/386) | Merchant task polling while handed or queued | Merged, with a follow-up fix |
| [@harshdazz](https://github.com/harshdazz) | [#383](https://github.com/AgriciDaniel/claude-seo/pull/383) | Windows venv swap retry | Merged |
| [@connabyss](https://github.com/connabyss) | [#392](https://github.com/AgriciDaniel/claude-seo/pull/392) | Strict `--release` value check | Merged |
| [@canermoral5-sys](https://github.com/canermoral5-sys) | [#362](https://github.com/AgriciDaniel/claude-seo/pull/362) | `seo-geo` wording: correlations stated as correlations | Merged |
| [@agammann](https://github.com/agammann) | [#385](https://github.com/AgriciDaniel/claude-seo/pull/385), [#387](https://github.com/AgriciDaniel/claude-seo/pull/387) | Review findings on the base URL and property selection changes | Both findings fixed in the follow-up commits |
| [@joachimBrindeau](https://github.com/joachimBrindeau) | [#318](https://github.com/AgriciDaniel/claude-seo/pull/318) | Port-bound DNS pin for local targets; stricter local target parser | The port-bound pin was reimplemented in the security follow-up commit; the rest of the PR is still under review |
| [@hydraxman](https://github.com/hydraxman) | [#372](https://github.com/AgriciDaniel/claude-seo/pull/372) | Review finding on list-valued price specification types | Fixed in the follow-up commit |

### 2026 maintenance review cycle

These contributors supplied implementation work or substantive design proposals.
Credit is preserved when a patch was superseded, selectively reimplemented, or
not merged after review.

| Contributor | PR | Contribution category | Review outcome |
|------------|----|-----------------------|----------------|
| [@wonsukchoi](https://github.com/wonsukchoi) | [#165](https://github.com/AgriciDaniel/claude-seo/pull/165), [#166](https://github.com/AgriciDaniel/claude-seo/pull/166), [#167](https://github.com/AgriciDaniel/claude-seo/pull/167), [#168](https://github.com/AgriciDaniel/claude-seo/pull/168), [#169](https://github.com/AgriciDaniel/claude-seo/pull/169), [#170](https://github.com/AgriciDaniel/claude-seo/pull/170), [#171](https://github.com/AgriciDaniel/claude-seo/pull/171) | Image paths, runtime setup, sitemap discovery, DataForSEO permissions, Bing API redesign, and Windows launcher proposals | Findings informed current-base implementations; patches were superseded or consolidated after review |
| [@powehi-ai](https://github.com/powehi-ai) | [#162](https://github.com/AgriciDaniel/claude-seo/pull/162) | Codex manifest and documentation proposal | Reviewed; not integrated because the repository already uses its portable Codex surface |
| [@maticyorg](https://github.com/maticyorg) | [#160](https://github.com/AgriciDaniel/claude-seo/pull/160) | Subagent model inheritance proposal | Reviewed; the proposed model value was not portable, so the patch was not integrated |
| [@GilboBlagins](https://github.com/GilboBlagins) | [#159](https://github.com/AgriciDaniel/claude-seo/pull/159) | Optional external knowledge-directory design | Reviewed; not integrated because the trust boundary needs a stricter design |
| [@voipcomjohn](https://github.com/voipcomjohn) | [#158](https://github.com/AgriciDaniel/claude-seo/pull/158) | Windows UTF-8 hook output | Reconciled into the current-base Windows encoding work |
| [@MSADTP](https://github.com/MSADTP) | [#157](https://github.com/AgriciDaniel/claude-seo/pull/157) | Full JSON-LD extraction before output truncation | Reimplemented with bounded structured parsing and regression coverage |
| [@lukababu](https://github.com/lukababu) | [#154](https://github.com/AgriciDaniel/claude-seo/pull/154) | Grok Build installation documentation | Selectively integrated using current official Grok compatibility guidance |
| [@kuhlsnu](https://github.com/kuhlsnu) | [#150](https://github.com/AgriciDaniel/claude-seo/pull/150) | Hosted-builder SPA detection and render timeout handling | Selectively reimplemented with bounded renderer behavior and tests |
| [@SENTMarketing](https://github.com/SENTMarketing) | [#147](https://github.com/AgriciDaniel/claude-seo/pull/147) | Windows-safe OAuth token permissions | Superseded by the current guarded implementation and regression coverage |
| [@BubblyWolf](https://github.com/BubblyWolf) | [#145](https://github.com/AgriciDaniel/claude-seo/pull/145) | Broken references, documentation accuracy, Windows portability, and CI review | Useful findings were reconciled selectively against the current release base |
| [@mubashirsidiki](https://github.com/mubashirsidiki) | [#141](https://github.com/AgriciDaniel/claude-seo/pull/141) | Bright Data extension proposal | Fully reviewed; not integrated because the extension needs a separate security and cost-control design |
| [@mukulcodezz](https://github.com/mukulcodezz) | [#140](https://github.com/AgriciDaniel/claude-seo/pull/140) | Public marketplace branding correction | Superseded by the public branding already shipped on the release branch |
| [@us](https://github.com/us) | [#136](https://github.com/AgriciDaniel/claude-seo/pull/136) | fastCRW crawling extension proposal | Fully reviewed; not integrated because installer, safety, and integration contracts need redesign |

### v2.2.0

| Contributor | PR | What |
|------------|-----|------|
| [@manishpaulsimon](https://github.com/manishpaulsimon) | [#117](https://github.com/AgriciDaniel/claude-seo/pull/117) | Cross-platform `drift_baseline` fetch -> parse handoff (synthesis basis) |
| [@solbergryan](https://github.com/solbergryan) | [#128](https://github.com/AgriciDaniel/claude-seo/pull/128) | Windows compatibility for drift scripts and installer |
| [@GieriGuru](https://github.com/GieriGuru) | [#111](https://github.com/AgriciDaniel/claude-seo/pull/111) | Handle Windows Store Python alias in `install.ps1` |
| [@Shieldxx](https://github.com/Shieldxx) | [#115](https://github.com/AgriciDaniel/claude-seo/pull/115) | Windows + non-Latin-1 baseline portability |
| [@imranaliraqi](https://github.com/imranaliraqi) | [#125](https://github.com/AgriciDaniel/claude-seo/pull/125) | Windows path + UTF-8 baseline portability |
| [@eduardofortesr](https://github.com/eduardofortesr) | [#101](https://github.com/AgriciDaniel/claude-seo/pull/101) | Cross-platform JSON-LD validator hook (python3) |
| [@fayerman-source](https://github.com/fayerman-source) | [#104](https://github.com/AgriciDaniel/claude-seo/pull/104) | Move Google API key from URL to request header |
| [@nickgraynews](https://github.com/nickgraynews) | [#113](https://github.com/AgriciDaniel/claude-seo/pull/113) | Drop deprecated GSC Sitemaps `indexed` field |
| [@PenthouseWaldkirchen](https://github.com/PenthouseWaldkirchen) | [#118](https://github.com/AgriciDaniel/claude-seo/pull/118) | Add authors and keywords to `pyproject.toml` |
| [@chat2deskmx](https://github.com/chat2deskmx) | [#123](https://github.com/AgriciDaniel/claude-seo/pull/123) | Add ruff config and lint cleanup |

### v1.9.7

| Contributor | PR | What |
|------------|-----|------|
| [@xiaolai](https://github.com/xiaolai) | [#62](https://github.com/AgriciDaniel/claude-seo/pull/62) | Sync `extensions/dataforseo` skill with core |
| [@xiaolai](https://github.com/xiaolai) | [#63](https://github.com/AgriciDaniel/claude-seo/pull/63) | Sync `extensions/banana` `seo-image-gen` skill |
| [@xiaolai](https://github.com/xiaolai) | [#64](https://github.com/AgriciDaniel/claude-seo/pull/64) | Pin MCP server package versions in extension installers |
| [@CrepuscularIRIS](https://github.com/CrepuscularIRIS) | [#67](https://github.com/AgriciDaniel/claude-seo/pull/67) | Detect marketplace plugin install path in DataForSEO extension |
| [@evanlu14](https://github.com/evanlu14) | [#69](https://github.com/AgriciDaniel/claude-seo/pull/69) | `pagespeed_check` KeyError fix (`audit_details`) |
| [@EDSprog](https://github.com/EDSprog) | [#70](https://github.com/AgriciDaniel/claude-seo/pull/70) | Update README install section |
| [@NicT89](https://github.com/NicT89) | [#73](https://github.com/AgriciDaniel/claude-seo/pull/73) | Migrate `moz_api` to v2 REST endpoints |
| [@AndronMan](https://github.com/AndronMan) | [#74](https://github.com/AgriciDaniel/claude-seo/pull/74) | Add `Write` tool to `seo-geo` agent |
| [@puneetindersingh](https://github.com/puneetindersingh) | [#56](https://github.com/AgriciDaniel/claude-seo/pull/56) | Add `seo-content-brief` skill |

### v1.9.0 and earlier

| Contributor | PR | What |
|------------|-----|------|
| [@edocltd](https://github.com/edocltd) | [#50](https://github.com/AgriciDaniel/claude-seo/pull/50) | Ukrainian localization |
| [@MalteBerlin](https://github.com/MalteBerlin) | [#45](https://github.com/AgriciDaniel/claude-seo/pull/45) | Sub-skills count correction |
| [@olivierroy](https://github.com/olivierroy) | [#43](https://github.com/AgriciDaniel/claude-seo/pull/43) | Extension install fix |

## Community Issue Reports

### v2.5.1

| Reporter | Issue | Contribution category |
|----------|-------|-----------------------|
| [@unterholzfrank](https://github.com/unterholzfrank) | [#357](https://github.com/AgriciDaniel/claude-seo/issues/357) | Schema hook crash on a list-valued `@type` |
| [@soulalpaca-ctrl](https://github.com/soulalpaca-ctrl) | [#382](https://github.com/AgriciDaniel/claude-seo/issues/382) | Schema hook crash on a list-valued `@type` |
| [@nickdumitru](https://github.com/nickdumitru) | [#333](https://github.com/AgriciDaniel/claude-seo/issues/333), [#334](https://github.com/AgriciDaniel/claude-seo/issues/334), [#335](https://github.com/AgriciDaniel/claude-seo/issues/335) | `@graph` false positives, GBP verified status, news sitemap cap |
| [@unisone](https://github.com/unisone) | [#394](https://github.com/AgriciDaniel/claude-seo/issues/394), [#395](https://github.com/AgriciDaniel/claude-seo/issues/395) | `priceSpecification` list crash; Matomo top-pages error loss |
| [@tomkor](https://github.com/tomkor) | [#337](https://github.com/AgriciDaniel/claude-seo/issues/337) | Wrong-site GA4 and GSC data from the global default property |
| [@zachlagden](https://github.com/zachlagden) | [#342](https://github.com/AgriciDaniel/claude-seo/issues/342) | `/seo` dropping the command word |
| [@Krtgya](https://github.com/Krtgya) | [#348](https://github.com/AgriciDaniel/claude-seo/issues/348) | Windows WinError 5 at the venv swap, with diagnosis and fix shape |
| [@osmosphuket-hub](https://github.com/osmosphuket-hub) | [#330](https://github.com/AgriciDaniel/claude-seo/issues/330) | Spaces dropped around inline tags |
| [@toquedemidas](https://github.com/toquedemidas) | [#322](https://github.com/AgriciDaniel/claude-seo/issues/322) | Entity extraction failing with HTTP 400 |
| [@namaserajesh](https://github.com/namaserajesh) | [#412](https://github.com/AgriciDaniel/claude-seo/issues/412) | Unlinked reference file |
| [@upfastai](https://github.com/upfastai) | [#402](https://github.com/AgriciDaniel/claude-seo/issues/402) | Install blocked by a scanner on a `curl` example |
| [@Docrichards1](https://github.com/Docrichards1) | [#252](https://github.com/AgriciDaniel/claude-seo/issues/252) | Relative reference paths on Windows |

### 2026 maintenance review cycle

| Reporter | Issue | Contribution category |
|----------|-------|-----------------------|
| [@DreaminginAI](https://github.com/DreaminginAI) | [#176](https://github.com/AgriciDaniel/claude-seo/issues/176) | Format-specific report dependency analysis and verification |
| [@sam-fakhreddine](https://github.com/sam-fakhreddine) | [#174](https://github.com/AgriciDaniel/claude-seo/issues/174) | Managed virtual-environment bypass in agent script commands |
| [@n-youn9](https://github.com/n-youn9) | [#173](https://github.com/AgriciDaniel/claude-seo/issues/173) | GSC total-limit pagination hang and reproducible root-cause analysis |
| [@jonathanlombi-debug](https://github.com/jonathanlombi-debug) | [#163](https://github.com/AgriciDaniel/claude-seo/issues/163) | Banana extension script-path and install-layout analysis |
| [@sohilshrestha0](https://github.com/sohilshrestha0) | [#161](https://github.com/AgriciDaniel/claude-seo/issues/161) | Missing render script path in delegated audit execution |
| [@Kickermax](https://github.com/Kickermax) | [#153](https://github.com/AgriciDaniel/claude-seo/issues/153) | Bing Webmaster endpoint failure reproduction and method probing |
| [@Arul-Raaj](https://github.com/Arul-Raaj) | [#149](https://github.com/AgriciDaniel/claude-seo/issues/149) | Retired FAQ rich-result guidance report |
| [@atahan150](https://github.com/atahan150) | [#137](https://github.com/AgriciDaniel/claude-seo/issues/137), [#138](https://github.com/AgriciDaniel/claude-seo/issues/138), [#139](https://github.com/AgriciDaniel/claude-seo/issues/139), [#148](https://github.com/AgriciDaniel/claude-seo/issues/148) | Plugin provisioning, Windows Python resolution, portable script roots, and DataForSEO MCP permissions |
| [@maulikvora](https://github.com/maulikvora) | [#142](https://github.com/AgriciDaniel/claude-seo/issues/142) | Non-default WordPress sitemap discovery |

## Security Disclosures

Responsible disclosures incorporated into v2.2.0. Thank you for reporting privately or via issues:

| Reporter | Report | What |
|----------|--------|------|
| [@Fushuling](https://github.com/Fushuling) | [#110](https://github.com/AgriciDaniel/claude-seo/issues/110) | SSRF parser-differential bypass in `validate_url` |
| [@webgunnz](https://github.com/webgunnz) | [#122](https://github.com/AgriciDaniel/claude-seo/issues/122), [#121](https://github.com/AgriciDaniel/claude-seo/issues/121) | Google API key leak in error output; UTF-8 double-encode |
| [@fayerman-source](https://github.com/fayerman-source) | [#130](https://github.com/AgriciDaniel/claude-seo/issues/130), [#103](https://github.com/AgriciDaniel/claude-seo/issues/103) | GSC false "0 clicks" totals; NLP V1 entity metadata |

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting pull requests,
creating extensions, and participating in future challenges.

Join the community:
- Free: https://www.skool.com/ai-marketing-hub
- Pro: https://www.skool.com/ai-marketing-hub-pro
