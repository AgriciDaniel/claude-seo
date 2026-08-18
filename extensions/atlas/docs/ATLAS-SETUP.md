# Atlas Cloud Extension Setup

## Requirements

- Claude SEO installed
- Python 3.10 or newer through the managed Claude SEO runtime
- An Atlas Cloud API key exposed as `ATLASCLOUD_API_KEY`
- HTTPS access to `api.atlascloud.ai` and Atlas output hosts

## Install

```bash
./extensions/atlas/install.sh
export ATLASCLOUD_API_KEY="..."
```

Persist the environment variable using your shell's secret manager or runtime
configuration. Do not put the key in the repository or pass it on the command
line.

## Verify Without Generation

```bash
test -n "$ATLASCLOUD_API_KEY" && echo "Atlas Cloud key is configured"
claude-seo doctor
```

The verification above does not submit a paid generation request.

## First Generation

```bash
claude-seo run --extension atlas generate.py \
  --prompt "Minimal editorial illustration of a website performance audit" \
  --size '1200*630'
```

Each invocation performs one paid generation POST. A failed POST is not
retried automatically. Result polling uses bounded GET requests.

## Troubleshooting

- `ATLASCLOUD_API_KEY is not set`: export the key in the same shell.
- HTTP 401/403: verify the key and account access; do not print the key.
- HTTP 429/5xx: stop and decide explicitly whether to make a new request.
- Poll timeout: inspect the prediction separately before creating another paid
  request.
- Output host rejected: do not bypass the allowlist; confirm the current Atlas
  output domain before updating the client.
