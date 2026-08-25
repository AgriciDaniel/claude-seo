# Modern AI Extension

AI Recommendation Rate lookups via Modern AI's free, public, known-entity endpoint.

## What this does

Looks up a brand's **Recommendation Rate** (percentage of buyer-intent
questions where AI models pick it as the #1 answer, not just mention it)
and **Recommendation Inclusion Rate** (percentage where it's mentioned at
all), plus source-class counts, via a single free API call.

Single-brand lookups only -- this is not a bulk data export, and the
endpoint's anti-scrape design hard-blocks anything shaped like an
enumeration attempt.

## Install

```
./extensions/modernai/install.sh   # macOS / Linux
./extensions/modernai/install.ps1  # Windows
```

No API key required. The endpoint is free and anonymous up to a rolling
rate ceiling; registered/paid access raises the ceiling.

## Usage

```
/seo modernai <brandname>
```

## Uninstall

```
./extensions/modernai/uninstall.sh
```

## Status

The lookup gate is live and its rate-limiting/anti-scrape logic is real
and tested. The underlying data-publishing pipeline that populates real
Recommendation Rate figures for a given brand is still being built out, so
some lookups may currently return "brand not yet published" rather than a
score -- the skill surfaces that plainly rather than guessing at a number.
