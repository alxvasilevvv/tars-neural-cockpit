# Analytics — `tars.<page|api|click>.<action>`

Status: **draft 1.0** · client implemented 2026-04-29 · server pending brother

The TARS marketing surface emits a small, well-named event stream so we
can answer four questions without integrating a heavyweight third party:

1. How many people land per day, where do they come from?
2. What's the funnel from landing → install copy → download click?
3. Which slide of `/pitch` makes people bounce?
4. Which `/build-with` badge variant gets copied most?

The frontend (`src/lib/analytics.ts`) batches events to **POST /api/log**.
Pre-launch the buffer lives in `localStorage["tars-analytics-buffer"]`
(capped at 200 events, oldest evicted) — the moment the brother stands
up `/api/log` on `tars.meeet.world`, the next batch drains.

## Wire shape

```http
POST /api/log
content-type: application/json

{
  "events": [
    {
      "name": "tars.click.install_copy_install",
      "props": { "os": "mac" },
      "ts": 1735689600123,
      "seq": 17,
      "session": "s_x7k4a9_lqj2dk",
      "page": "/install",
      "ref": "https://twitter.com/...",
      "product": "tars"
    },
    ...
  ]
}
```

- `name` — fully-qualified event name (see § Event names).
- `props` — flat key/value pairs, primitive types only. Optional.
- `ts` — client epoch ms.
- `seq` — monotonic per session. Server should re-order if needed.
- `session` — opaque random string (`s_<8hex>_<base36ts>`), regenerated
  per tab. Lives in `sessionStorage` only — wipes on tab close.
- `page` — `pathname + search` at the moment of emission.
- `ref` — `document.referrer` at first event of session.
- `product` — always `"tars"` from this surface; brother's hub may add
  events for `meeet`, `relayer`, etc. on the same endpoint.

The server **must** respond `2xx` to drain the client buffer; any other
status keeps the events queued (with backoff) so transient outages don't
lose data.

## Event names

| Event                                  | When                                              | Useful props                                         |
| -------------------------------------- | ------------------------------------------------- | ---------------------------------------------------- |
| `tars.page.view`                       | every route change in `<AppShell/>`               | `path`                                               |
| `tars.click.install_copy_install`      | user copies the curl install command              | `os`                                                 |
| `tars.click.install_copy_brew`         | user copies the Homebrew tap command              | `os`                                                 |
| `tars.click.badge_copy_html`           | user copies HTML embed in `/build-with`           | `size`, `theme`                                      |
| `tars.click.badge_copy_md`             | user copies Markdown embed in `/build-with`       | `size`, `theme`                                      |
| `tars.click.download_<os>_<arch>`      | user clicks an OS-specific download CTA           | `version`, `kind`                                    |
| `tars.click.cta_cockpit`               | "Open cockpit" CTA on Hero / Footer               | `surface`                                            |
| `tars.api.downloads_manifest_ok`       | `/api/product/downloads` returned 2xx             | `version`, `contract_version`                        |
| `tars.api.downloads_manifest_fail`     | `/api/product/downloads` errored                  | `status`                                             |
| `tars.api.health_ok`                   | `/health` ping succeeded                          | `latency_ms`                                         |
| `tars.api.health_fail`                 | `/health` ping failed                             | `reason`                                             |

New events MUST follow `tars.<page|api|click>.<snake_case_action>`. Add
them to this table when you wire them.

## What we never log

- No PII. No emails, wallet addresses, keystrokes, file contents.
- No URL query strings that contain tokens (`?token=…` is stripped
  client-side before the event fires — we only keep the path).
- No referrer if it contains `password`/`token`/`auth` substrings.
- No user-agent string. The server can read it from the request itself.

## Privacy alignment

This stream is what the cookie banner discloses as "no tracking, no
ads". The events are **functional** under GDPR Article 6(1)(f) — they
power our own product analytics, are not shared with third parties, and
contain no identifiable data. Retention is 90 days on the brother's
`/api/log` store, after which events are aggregated and the raw rows
pruned. Privacy policy § 9 already covers this.

## Brother's responsibilities

When implementing `/api/log` on `tars.meeet.world`:

1. Accept `POST` with the body shape above. Reject other methods 405.
2. Validate `name` matches `^tars\.(page|api|click)\.[a-z0-9_]+$`.
3. Drop events with `ts` more than 24h in the past or in the future.
4. Stamp server-side `received_at`, `country` (Cloudflare-Country), `ua`.
5. Persist to ClickHouse (or whatever the meeet.world hub uses).
6. Respond `204 No Content` on success.
