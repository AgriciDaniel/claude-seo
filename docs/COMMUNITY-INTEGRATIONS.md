# Community integrations

Integrations built and maintained by other people, in their own repositories.
They are listed here so you can find them. They are **not** part of Claude SEO:
the maintainer has not audited their code, does not ship or update them, and
cannot support them. Read an integration's code and install script before you
run it, the same as for any third-party tool, and send questions and bug
reports to its own repository.

Claude SEO does not bundle third-party paid services as first-party
extensions. A separate repository listed here is the way to offer one.

## Listed

| Integration | Maintainer | What it does | Cost |
|---|---|---|---|
| [claude-seo-proxlane](https://github.com/proxlane/claude-seo-proxlane) | [@scarsam](https://github.com/scarsam) (maintains Proxlane) | Fetches pages through a self-hosted Proxlane gateway that fails over between scraping providers and reports why a page failed (gone, blocked, rate limited). | Gateway is self-hosted; the scraping providers behind it are paid. |
| [claude-seo-cloro](https://github.com/cloro-dev/claude-seo-cloro) | [@rbatista191](https://github.com/rbatista191) (works at cloro) | Asks ChatGPT, Google AI Mode, Gemini and Bing AI Mode a prompt from a chosen country and reports whether the answer mentions or cites a brand, with its sources. | Paid cloro API (Free plan: 500 credits a month); 5 to 7 credits a call. |
| [claude-seo-goanyapi](https://github.com/GoAnyAPI/claude-seo-goanyapi) | [@shineforever](https://github.com/shineforever) (works on GoAnyAPI) | Adds third-party search data from GoAnyAPI's HTTP API: competitor top-10 positions, keyword volumes and difficulty, backlinks, traffic estimates, Google Ads Transparency lookups and reverse AdSense. | Paid GoAnyAPI, prepaid credits (about $0.001 a credit); 1 to 3 credits a call. |

## Getting listed

Open an issue with a link to the repository. An integration is listed when it:

1. Lives in its own public repository with an open-source licence.
2. Says plainly who maintains it and whether the maintainer sells the service
   it connects to.
3. Says what it costs to use, including any paid API behind it.
4. Carries no tracking or affiliate links (no UTM parameters, no referral
   codes) in skill files, scripts or docs.
5. Installs only into the user's own directories, has an uninstall script, and
   does not change Claude SEO's files or dependencies.
6. Keeps credentials out of the repository and out of command output.
7. Treats fetched page content as untrusted data in its skill instructions.

A listing is removed if the repository is archived, stops meeting these
points, or is reported for behaviour its README does not disclose.

"Official SEO MCP Servers" in `docs/MCP-INTEGRATION.md` is a different list:
it holds servers published by the data provider itself.
