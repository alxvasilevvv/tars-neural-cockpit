# Post-Deploy QA — v9.1.0 install funnel

> Run this 11-step probe pack **after** `git push origin main` triggers the
> Cloudflare Pages deploy and **before** the launch announcement goes out.
> Each step is a single curl/visual check; pass criteria explicit. Stop and
> escalate on any FAIL.

**Targets**

- Production landing: `https://tars.meeet.world`
- dl-proxy worker: `https://tars.meeet.world/dl/...`
- GitHub release tag (current): `v9.1.0`

**Setup**

```bash
export TARS_HOST="https://tars.meeet.world"
export TARS_TAG="v9.1.0"
```

---

## 1. Health — landing returns 200 + correct version banner

```bash
curl -sS -o /dev/null -w "http:%{http_code} time:%{time_total}s\n" "$TARS_HOST/"
curl -sS "$TARS_HOST/" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9]+)?' | sort -u | head -3
```

**Pass:** `http:200`, `time` < 1.5s, version banner contains `v9.1.0` or
`v10.0.0-rc.1` (current pre-launch label). FAIL if `503`, `404`, or version
older than `v9.1.0`.

## 2. Install funnel — Hero CTA points at dl-proxy

```bash
curl -sS "$TARS_HOST/" | grep -oE 'href="[^"]*dl/[^"]+"' | head -5
```

**Pass:** at least one `href="/dl/tars-mac-arm64.dmg"` (or equivalent installer
path) returned. FAIL if all install hrefs point at `coming-soon`, `/install`
without a path, or absolute github.com (means CTA hasn't been wired through
dl-proxy yet).

## 3. install.sh — one-line installer is reachable + signed

```bash
curl -sSL "$TARS_HOST/install.sh" | head -40
curl -sS -o /dev/null -w "http:%{http_code} ctype:%{content_type}\n" "$TARS_HOST/install.sh"
```

**Pass:** `http:200`, `ctype` contains `text/plain` or `application/x-sh`,
script body starts with `#!/usr/bin/env bash` and contains
`scripts/INSTALL-FRESH-TARS.command` reference. FAIL if 404 or returns
HTML (proxy mis-routed).

## 4. dl-proxy HEAD — installer exists at the expected path

```bash
curl -sSI "$TARS_HOST/dl/tars-mac-arm64.dmg" | head -10
```

**Pass:** `HTTP/2 200` (or 302 to a valid GitHub releases URL) + `content-type:
application/x-apple-diskimage` (or `application/octet-stream`) + non-zero
`content-length` (~50–80 MB). FAIL on 404, redirect to a draft release, or
zero content-length.

## 5. Partial GET — Range requests work for large installers

```bash
curl -sS -H "Range: bytes=0-1023" -o /tmp/tars_head.bin -w "http:%{http_code} size:%{size_download}\n" \
  "$TARS_HOST/dl/tars-mac-arm64.dmg"
file /tmp/tars_head.bin
```

**Pass:** `http:206`, `size:1024`. `file` reports `data` (binary header).
FAIL if `200` (range not honored) or `206` with wrong size — Cloudflare
edge config drift.

## 6. Allowlist guard — only known installer paths resolve

```bash
for P in tars-mac-arm64.dmg tars-mac-x64.dmg tars-windows.msi tars-linux.AppImage; do
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -I "$TARS_HOST/dl/$P")
  echo "$P → $CODE"
done
echo ""
# Out-of-allowlist should 404
for P in evil.sh ../../../etc/passwd random.zip tars-mac-arm64.dmg.bak; do
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -I "$TARS_HOST/dl/$P")
  echo "GUARD $P → $CODE"
done
```

**Pass:** known installers return `200` (or `302`); guard rows return `404`.
FAIL if any guard row returns `200` — open redirect / path traversal in the
worker.

## 7. Method guard — only GET/HEAD allowed

```bash
for M in POST PUT DELETE PATCH OPTIONS; do
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X "$M" "$TARS_HOST/dl/tars-mac-arm64.dmg")
  echo "$M → $CODE"
done
```

**Pass:** every non-GET/HEAD method returns `405` or `403`. FAIL on `200`
(installer worker accepting writes) or `500` (worker crashed).

## 8. Rosetta fallback — x64 dmg path resolves on Apple-Silicon

```bash
curl -sSI "$TARS_HOST/dl/tars-mac-x64.dmg" | head -10
```

**Pass:** `HTTP/2 200` (or 302). FAIL if 404 — we promised "Intel Mac users
get the x64 build" and that promise is broken.

## 9. W142 stability — dl-proxy still resolves draft releases correctly

```bash
# This is the regression that W142 fixed: dl-proxy looking up DRAFT releases
# instead of published. Re-probe to make sure CF Pages didn't regress it.
curl -sS "$TARS_HOST/dl/_meta?tag=$TARS_TAG" 2>/dev/null | head -20
```

**Pass:** JSON response with `"tag":"v9.1.0"`, `"draft":false`, `"published":true`.
FAIL on `draft:true` (proxy is grabbing draft instead of stable) — ping the
W142 owner before announcing.

## 10. Cache headers — installer + landing are cached correctly

```bash
curl -sSI "$TARS_HOST/" | grep -i 'cache-control\|cf-cache-status\|age'
echo "---"
curl -sSI "$TARS_HOST/dl/tars-mac-arm64.dmg" | grep -i 'cache-control\|cf-cache-status\|age'
```

**Pass for landing:** `cache-control` mentions `s-maxage` ≤ 600 (allow fast
landing-page redeploys). `cf-cache-status` = `HIT` or `EXPIRED` after a
deploy. **Pass for installer:** `cache-control` allows long edge cache
(`s-maxage=86400` or higher). FAIL if landing is over-cached (changes don't
appear) or installer is uncached (saturates origin).

## 11. Browser smoke — install funnel end-to-end in 60 seconds

Manual, **after** all curl probes pass:

1. Open `$TARS_HOST/` in a clean Chrome profile (incognito works).
2. Hero CTA: "Download for Mac" → install funnel page loads in < 1.5s.
3. Click install link → `.dmg` download starts immediately (don't open it).
4. Cancel the download (we just need to verify the link, not install).
5. Open the install.sh page in a new tab → readable bash script renders.
6. View source → confirm version banner shows current tag.

**Pass:** all 6 steps complete with no console errors, no broken styles
(Lighthouse perf 95+, accessibility 95+ on Hero). FAIL on any 4xx, JS error,
or layout shift.

---

## Sign-off

After all 11 steps PASS:

```bash
git tag -a v9.1.0-launch-ready -m "post-deploy QA passed; launch announcement clear to go"
git push origin v9.1.0-launch-ready
```

If any step fails, stop here, file an incident in `docs/INCIDENT_LOG.md`,
and **do not** send the launch announcement until the gating step is fixed
and this pack is re-run from step 1.
