# Xquik extension

Add bounded public X-post and topic research to Claude SEO's LISTEN phase.

This optional extension supports 2 read-only commands:

```text
/seo xquik listen <query>
/seo xquik radar
```

Use the results to study audience wording and recurring questions. Do not use
them as direct search ranking signals. The adapter makes one fixed-endpoint
request per command, caps results at 100, and cannot write to X.

Install with `./extensions/xquik/install.sh`. See
[`docs/XQUIK-SETUP.md`](docs/XQUIK-SETUP.md) for setup and safety details.

Xquik is an independent third-party service. Not affiliated with X Corp.
"Twitter" and "X" are trademarks of X Corp.
