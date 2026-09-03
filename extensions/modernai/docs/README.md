# Modern AI Extension: Setup

## Install

```
./extensions/modernai/install.sh
```

No API key needed. Queries Modern AI's free, gated, single-brand-lookup endpoint
anonymously, rate-limited per Modern AI's own published anti-scrape policy (a small
free ceiling per rolling 30-day window; registered/paid access lifts it).

## Usage

```
/seo modernai <brandname>
```

Returns the brand's AI Recommendation Rate (first-choice %) and Recommendation
Inclusion Rate (appears-anywhere %), both clearly labeled and distinguished, plus
source-class counts. One brand per call; this is a lookup tool, not a bulk data
export.

## Uninstall

```
./extensions/modernai/uninstall.sh
```
