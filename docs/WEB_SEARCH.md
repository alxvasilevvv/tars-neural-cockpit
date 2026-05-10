# Web search domain pack

TARS ships an outbound web-search pack with three adapters and a
deterministic priority chain. Goal: make the cockpit useful on day-1
without any keys, while letting power users upgrade in 30 seconds.

## Default behaviour (no config)

`POST /api/domains/web_search/actions/search/invoke` with
`{"query": "latest pandas release"}` returns DuckDuckGo HTML results.
No keys, no quota counter, no telemetry. Fine for casual use; may be
rate-limited on bursty traffic.

## Upgrade to Brave (recommended)

Free tier ships **2 000 queries / month** — enough for daily
research without ever hitting a paywall.

1. Get a key at <https://api.search.brave.com/app/keys>.
2. Persist it in the vault:

   ```bash
   security add-generic-password \
     -a tars -s BRAVE_SEARCH_API_KEY -w "<token>" -U
   ```

   On Linux/Windows: `export BRAVE_SEARCH_API_KEY=<token>` (mirror
   into your shell rc / systemd unit).
3. Verify:

   ```bash
   curl -s -X POST http://127.0.0.1:8765/api/domains/web_search/actions/health/invoke \
     | jq .result.default_order
   # ["brave", "ddg"]
   ```

## Upgrade to SearXNG (max privacy)

Run a SearXNG instance locally (`docker run -d -p 8080:8080
searxng/searxng`) and point TARS at it:

```bash
export TARS_SEARXNG_URL=http://127.0.0.1:8080
```

Restart the backend. `health` should now report:

```json
{ "default_order": ["brave", "searxng", "ddg"] }
```

(or `["searxng", "ddg"]` if Brave isn't configured).

## Pinning an adapter

`{"query": "...", "adapter": "brave" | "searxng" | "ddg" | "auto"}`.
A pinned adapter does **not** fall through — useful for tests and
for benchmarking adapter quality.

## Response envelope

```jsonc
{
  "ok": true,
  "query": "…",
  "adapter": "brave",          // adapter that returned hits
  "tried": [                   // every backend consulted
    {"adapter": "brave", "ok": true, "error": null,
     "upstream_status": null, "count": 10}
  ],
  "count": 10,
  "results": [
    {
      "title": "…",
      "url":   "…",
      "snippet": "…",          // ≤ 360 chars, whitespace collapsed
      "source": "brave",       // tag = adapter that produced the row
      "extra":  {"age": "2 weeks ago"}  // optional, adapter-specific
    }
  ]
}
```

On total failure:

```jsonc
{
  "ok": false,
  "error": "all_adapters_failed",
  "query": "…",
  "tried": [...],
  "hint": "Set BRAVE_SEARCH_API_KEY for the highest-quality path…"
}
```

## Why three adapters

- **Brave** — best results, single header, generous free tier, no
  scraping fragility. Default once configured.
- **SearXNG** — query never leaves your network. Best for sensitive
  research and air-gapped deployments.
- **DuckDuckGo HTML** — no key required. Lets the pack ship a
  working "out of the box" experience and gives operators a fallback
  when their primary backend is down.

## Voice / system prompt

The pack ships a `system_prompt` that nudges the council to **cite
URLs**, **prefer authoritative primary sources**, and **flag
freshness** when the operator's question implies recency. See
`backend/core/domains/packs/web_search/prompts.py`.

## Limits

- `limit` is clamped to `[1, 25]` (default 10). Brave's free tier
  caps at `count=20` per call.
- Snippets ≤ 360 chars (whitespace collapsed). The dispatcher
  de-duplicates by URL (case-insensitive, trailing slash ignored).
- Pack is on-demand only — no background polling, no cron, no
  background queries against the operator's quota.
