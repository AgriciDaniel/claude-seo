# Modern AI Extension

Run one command, get a brand's real AI Recommendation Rate, or a clear
"not yet published" answer. Free, no API key.

## What this does

Returns a brand's real AI Recommendation Rate (how often it is the AI's
#1 pick on buyer-intent questions) and Recommendation Inclusion Rate (how
often it is mentioned at all), plus source-class counts. One free lookup.

Single-brand lookups only. This is not a bulk data export; the endpoint
blocks anything shaped like a scripted list-all request.

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

The endpoint is live. A brand with a published measurement returns its
real score. A brand not yet measured returns "brand not yet published."
