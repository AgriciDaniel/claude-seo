# Google Cloud Natural Language API Reference

NLP analysis enhances E-E-A-T scoring by measuring entity coverage, content sentiment, and topic classification using Google's own taxonomy.

## Endpoint

`POST https://language.googleapis.com/v2/documents:annotateText?key={API_KEY}`

## Features

| Feature | What It Does | SEO Use |
|---------|-------------|---------|
| `extractEntities` | Extract people, orgs, places, events with salience scores | Topic coverage depth, entity optimization |
| `extractDocumentSentiment` | Document + sentence-level sentiment score/magnitude | Content tone assessment |
| `classifyText` | Map content to 700+ Google categories | Topic relevance verification |
| `moderateText` | Content safety/moderation categories | Content quality flags |

## Entity Types

PERSON, LOCATION, ORGANIZATION, EVENT, WORK_OF_ART, CONSUMER_GOOD, OTHER, PHONE_NUMBER, ADDRESS, DATE, NUMBER, PRICE

Each entity includes:
- `name`: Entity text
- `type`: Entity type
- `salience`: Importance score (0-1, higher = more relevant)
- `sentiment`: Per-entity sentiment (score + magnitude)
- `metadata`: Wikipedia URL, MID (Knowledge Graph ID)
- `mentions`: Occurrences in the text

## Sentiment Scoring

- **Score**: -1.0 (negative) to +1.0 (positive)
- **Magnitude**: 0 to infinity (emotional intensity, higher = more emotional)
- Neutral content: score ~0, low magnitude
- Mixed content: score ~0, HIGH magnitude (both positive and negative)

## Pricing

| Feature | Free/month | Paid (per 1K chars) |
|---------|-----------|-------------------|
| Entity Analysis | 5,000 units | $0.001 |
| Sentiment Analysis | 5,000 units | $0.001 |
| Content Classification | 30,000 units | $0.002 |
| Text Moderation | 50,000 units | $0.0005 |

One "unit" = 1,000 characters. Free tier resets monthly.

## Enable the API

1. Go to [console.cloud.google.com/apis/library](https://console.cloud.google.com/apis/library)
2. Search for "Cloud Natural Language API"
3. Click Enable
4. **Billing must be enabled** on the project (free tier still applies)

Uses the same API key as PSI/CrUX.
