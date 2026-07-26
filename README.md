# Chorus

Chorus is a small decision-support prototype that demonstrates a three-stage workflow:

1. **Finder** ranks candidate options.
2. **Judge** selects a leading option and alternatives.
3. **Critic** adds caveats and reduces confidence when risks are present.

The current V1 is deliberately limited. It uses fixed mock data and deterministic JavaScript scoring. It does **not** call a local or hosted language model.

## Current capabilities

- accepts a natural-language shopping or travel query
- extracts a simple numeric budget
- ranks mock options using price, rating, source status, refundability and distance
- returns a best option, alternatives, caveats and a confidence score
- includes a small local web interface and JSON API

## Safety boundaries

The published V1 has no capability to:

- execute shell commands or generated code
- read, write or delete local files
- browse arbitrary websites
- make purchases, bookings or payments
- control devices or external services
- call AI models or grant models tools
- act without a user request

The server binds to `127.0.0.1` by default, limits request size, limits query length and does not expose internal error details to clients.

Setting `HOST` to another address can expose the service to a network and should only be done deliberately behind appropriate access controls.

## Run locally

```bash
cd chorus-v1
npm install
npm start
```

Then open:

```text
http://127.0.0.1:3000
```

## API

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

This is a workflow demonstration, not a live recommendation or autonomous-agent system. Prices, ratings and availability are mock values and must not be treated as current facts.

## Future model integration

Any future connection to a local model should preserve a strict separation between **advice** and **action**. Model output should be treated as untrusted text. Tool access, network access, filesystem access and command execution should remain disabled unless separately designed, allow-listed, sandboxed and confirmed by a human.
