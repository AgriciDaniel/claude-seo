# Atlas Cloud Image Generation Extension

This optional Claude SEO extension adds an executable Atlas Cloud workflow for
SEO images such as social previews, blog heroes, product images, and
infographic bases.

## Install

```bash
./extensions/atlas/install.sh
export ATLASCLOUD_API_KEY="..."
```

The installer copies the skill, script, and reference file. It does not store
the API key.

## Generate

```bash
claude-seo run --extension atlas generate.py \
  --prompt "Editorial illustration for a technical SEO guide" \
  --size '1200*630'
```

The client submits one asynchronous generation request, polls the returned
prediction with bounded backoff, and downloads the image without forwarding
the API key. See `docs/ATLAS-SETUP.md` for setup and troubleshooting.

## Uninstall

```bash
./extensions/atlas/uninstall.sh
```
