# Chorus V1

Private prototype for Lee's shopping / travel / planning Chorus.

## What this version does
- accepts a natural-language query
- runs a 3-agent flow: Finder -> Judge -> Critic
- returns a best option, alternatives, caveats, and confidence
- includes a tiny web UI
- uses mocked data so the workflow can be proven before live retrieval is added

## Why Node here
- you already use Node in your local setup
- very fast to get a private prototype running
- easy to split later between EDGE1 and Beast

## Run
```bash
npm install
npm start
```

Then open:
```bash
http://localhost:3000
```

## API
### POST /chorus
```json
{
  "query": "Find me the best hotel in Manchester under £120"
}
```

## Example future upgrades
- replace mocked data with live retrieval adapters
- add source trust weighting
- add real dynamic pricing snapshots
- move UI/proxy to EDGE1 and keep compute on Beast
- add RTX4060E as adversarial verifier node
