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

**Pass:** at least one `href="/dl/TARS_9.1.0_aarch64.dmg"` (or equivalent installer
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

## 4. dl-proxy HEAD — все 9 артефактов отдают 200/302

```bash
ASSETS=(
  TARS_9.1.0_aarch64.dmg          # mac Apple Silicon
  TARS_9.1.0_x64.dmg              # mac Intel
  TARS_9.1.0_amd64.AppImage       # linux portable
  TARS_9.1.0_amd64.deb            # linux deb
  TARS_9.1.0_x64-setup.exe        # windows NSIS
  TARS_9.1.0_x64_en-US.msi        # windows MSI
  TARS_aarch64.app.tar.gz         # Tauri update bundle
  latest.json
  latest.json.sig
)
for F in "${ASSETS[@]}"; do
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -I "$TARS_HOST/dl/$F")
  echo "$F → $CODE"
done
```

**Pass:** все 9 артефактов отдают `200`, `302`, или `200` со streamed
octet-stream (см. `[file].ts:216 streamAsset`). FAIL если хотя бы один даёт
`404` — либо опечатка имени, либо релиз не пересобран, либо
`GITHUB_RELEASE_TOKEN` не задеплоен в Pages env.

## 5. Partial GET — Range работает для самого большого инсталлера

```bash
curl -sS -H "Range: bytes=0-1023" -o /tmp/tars_head.bin \
  -w "http:%{http_code} size:%{size_download}\n" \
  "$TARS_HOST/dl/TARS_9.1.0_aarch64.dmg"
file /tmp/tars_head.bin
```

**Pass:** `http:206`, `size:1024`. `file` reports `data`. FAIL `200` (Range
проигнорирован worker'ом) или `206` с другим размером (edge cache drift).

## 6. Allowlist guard — out-of-list дают `404 not_in_allowlist`

```bash
# Известные — должны проходить
for P in TARS_9.1.0_aarch64.dmg TARS_9.1.0_x64.dmg \
         TARS_9.1.0_x64_en-US.msi TARS_9.1.0_amd64.AppImage; do
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -I "$TARS_HOST/dl/$P")
  echo "OK    $P → $CODE"
done
echo "---"
# Out-of-allowlist — должны давать 404 + error body
for P in evil.sh ../../../etc/passwd random.zip \
         TARS_9.1.0_aarch64.dmg.bak TARS_9.9.9_arbitrary.dmg; do
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -I "$TARS_HOST/dl/$P")
  ERR=$(curl -sS "$TARS_HOST/dl/$P" | grep -o '"error":"[^"]*"' | head -1)
  echo "GUARD $P → $CODE ($ERR)"
done
```

**Pass:** OK-строки — `200`/`302`; GUARD-строки — `404` +
`"error":"not_in_allowlist"`. FAIL на любой `200` в GUARD.

## 7. Method guard — только GET/HEAD

```bash
for M in POST PUT DELETE PATCH OPTIONS; do
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X "$M" \
         "$TARS_HOST/dl/TARS_9.1.0_aarch64.dmg")
  echo "$M → $CODE"
done
```

**Pass:** все `405` + ответный header `allow: GET, HEAD` (см. `[file].ts:282`).
FAIL на `200` или `500`.

## 8. Rosetta fallback — x64 dmg редиректит на arm64 с диагностическим header

```bash
curl -sSI "$TARS_HOST/dl/TARS_9.1.0_x64.dmg" | grep -iE 'HTTP|location|x-tars-fallback'
```

**Pass:** `HTTP/2 302` + `location: /dl/TARS_9.1.0_aarch64.dmg` +
`x-tars-fallback: rosetta` + `x-tars-fallback-from: TARS_9.1.0_x64.dmg`
(см. `[file].ts:319-328`). FAIL если 404 — Intel-юзерам обещано "ставится
через Rosetta", и обещание сломано.

## 9. W142 smart-fallback — by-tag empty не приводит к 404

```bash
# Дёргаем артефакт дважды с salt'ом, чтобы CDN не кэшировал.
SALT=$(date +%s)
for I in 1 2; do
  CODE=$(curl -sS -o /dev/null -w "%{http_code}" -I \
         "$TARS_HOST/dl/TARS_9.1.0_aarch64.dmg?_=$SALT$I")
  echo "probe $I → $CODE"
done
```

**Pass:** оба пробинга — `200`/`302`. Косвенно подтверждает что Pages
Function успешно дотягивается до релиза (либо by-tag, либо через
draft-list fallback `[file].ts:181-213`). FAIL `404 asset_not_found_in_release`
— CI publish был отменён мид-flight, fallback не работает.

## 10. Cache headers — installer + landing are cached correctly

```bash
curl -sSI "$TARS_HOST/" | grep -i 'cache-control\|cf-cache-status\|age'
echo "---"
curl -sSI "$TARS_HOST/dl/TARS_9.1.0_aarch64.dmg" | grep -i 'cache-control\|cf-cache-status\|age'
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
