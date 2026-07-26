# Chorus

Chorus is a small multi-agent decision prototype for shopping, travel and planning queries.

Instead of returning the first plausible option, it passes a request through three explicit roles:

1. **Finder** gathers and ranks candidate options.
2. **Judge** selects the strongest result and explains the trade-offs.
3. **Critic** challenges the choice, highlights caveats and lowers confidence where appropriate.

The current V1 deliberately uses mocked datasets. That keeps the orchestration, ranking and explanation pipeline testable before live retrieval, pricing and source-verification adapters are introduced.

## Features

- natural-language query input
- budget extraction from phrases such as `under £120`
- weighted scoring across price, rating, trust, refundability and distance
- alternatives and explicit judge reasoning
- adversarial critic stage
- confidence estimate
- JSON API and lightweight browser interface

## Technology

- Node.js
- Express
- vanilla HTML, CSS and JavaScript

## Run locally

```bash
npm install
npm start
```

Open `http://localhost:3000`.

## API example

```http
POST /chorus
Content-Type: application/json
```

```json
{
  "query": "Find me the best hotel in Manchester under £120"
}
```

## Status

Working V1 prototype. The decision flow is functional, but the bundled options are illustrative rather than live recommendations.

## Roadmap

- pluggable live-retrieval adapters
- source provenance and trust weighting
- dynamic price snapshots
- automated tests for ranking and budget extraction
- configurable scoring policies
- optional local-model roles for finder, judge and critic

## Privacy and safety

The current repository contains no credentials and performs no purchasing or booking. Any future live adapters should keep API credentials in environment variables and make uncertainty and source dates visible to users.
