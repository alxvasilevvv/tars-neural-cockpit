# VS Code Marketplace launch — tars-tab v0.1.0

This runbook walks a fresh operator from zero to a live
`meeet-world.tars-tab` listing on the Visual Studio Marketplace.
Wave W259 deliverable; pairs with
[`vscode-extension/CHANGELOG.md`](../vscode-extension/CHANGELOG.md)
and [`vscode-extension/scripts/PUBLISH-EXTENSION.command`](../vscode-extension/scripts/PUBLISH-EXTENSION.command).

**Estimated time end-to-end: ~25 min** (most of it is one-time
publisher onboarding).

---

## 1. Create an Azure DevOps Personal Access Token (PAT)

VS Code Marketplace authentication piggybacks on Azure DevOps.
You'll need a PAT scoped to **Marketplace > Manage**.

1. Sign in to <https://dev.azure.com>. If you don't have an
   organisation yet, create one — the name doesn't matter, it's
   only used to host the PAT.
2. Open the user-settings menu (top-right) → **Personal access
   tokens**.
3. Click **+ New Token**.
4. Settings:
   - **Name**: `tars-vsce-publish`
   - **Organization**: *All accessible organizations*
   - **Expiration**: 90 days (rotate before expiry; calendar
     reminder lives in [`docs/AUTOMATION.md`](AUTOMATION.md))
   - **Scopes**: click *Show all scopes* → tick
     **Marketplace → Manage** (do not grant broader scopes).
5. Click **Create**, copy the PAT immediately (Azure shows it
   exactly once), and store it in 1Password under
   "TARS / VS Code Marketplace PAT".

> If a previous PAT exists for a teammate, prefer rotating yours
> over reusing theirs — Marketplace audit log uses the PAT owner
> as the publishing identity.

---

## 2. Register the `meeet-world` publisher

This step is **one-time** for the whole project. Skip if the
publisher already exists at
<https://marketplace.visualstudio.com/manage/publishers/meeet-world>.

1. Open <https://marketplace.visualstudio.com/manage>.
2. Click **+ Create publisher**.
3. Fields:
   - **ID**: `meeet-world` (must match `publisher` in
     `vscode-extension/package.json` — already set).
   - **Display name**: `meeet.world`
   - **Email**: support@meeet.world
   - **Website**: <https://tars.meeet.world>
4. Accept the Marketplace Publisher Agreement and click
   **Create**.

After creation, verify the PAT works:

```bash
npx --yes @vscode/vsce login meeet-world
# Paste the PAT when prompted.
```

`vsce login` is optional when publishing via the
`PUBLISH-EXTENSION.command` script (the script passes the PAT
inline via `-p`), but doing it once confirms the credentials
work before you run the real publish.

---

## 3. Prepare the icon

The Marketplace listing requires a **128×128 PNG** at
`vscode-extension/icon.png`. The repo ships a placeholder text
file with the same name and the publish script will refuse to
proceed until it sees a real PNG.

Quickest paths:

```bash
cd vscode-extension

# librsvg (Homebrew):
brew install librsvg
rsvg-convert -w 128 -h 128 media/tars-icon.svg -o icon.png

# ImageMagick:
brew install imagemagick
magick convert -background none -resize 128x128 \
    media/tars-icon.svg icon.png
```

Or design a custom icon at 128×128 in Figma / Sketch / Affinity
and export as PNG to `vscode-extension/icon.png`. Background can
be transparent or solid; the Marketplace renders both on white
*and* dark gallery pages.

After dropping the file in, sanity-check the magic bytes:

```bash
head -c 8 vscode-extension/icon.png | od -An -tx1
# expected: 89 50 4e 47 0d 0a 1a 0a
```

---

## 4. Run the publish script

```bash
cd vscode-extension
export VSCODE_PUBLISH_TOKEN="...the PAT from step 1..."
./scripts/PUBLISH-EXTENSION.command          # publish current version
# or bump-on-publish:
./scripts/PUBLISH-EXTENSION.command patch    # 0.1.0 -> 0.1.1
./scripts/PUBLISH-EXTENSION.command minor    # 0.1.0 -> 0.2.0
./scripts/PUBLISH-EXTENSION.command major    # 0.1.0 -> 1.0.0
```

What the script does:

1. Checks `VSCODE_PUBLISH_TOKEN` is set.
2. Sniffs `icon.png` magic bytes — aborts if it's still the
   placeholder text file.
3. `npm install --no-fund --no-audit`.
4. `tsc -p ./` (compile TypeScript to `out/`).
5. `vsce publish [bump] -p $VSCODE_PUBLISH_TOKEN --no-dependencies`.
6. Echoes the live Marketplace URL.

A full log is written to
`vscode-extension/scripts/.PUBLISH-EXTENSION.txt` for postmortem
purposes.

### Exit codes (for CI integrations)

| Code | Meaning                                            |
|------|----------------------------------------------------|
| 0    | published successfully                             |
| 64   | `VSCODE_PUBLISH_TOKEN` unset                       |
| 65   | `icon.png` missing                                 |
| 66   | `icon.png` still the placeholder text file         |
| 67   | `node` not on PATH                                 |
| 68   | `npm` not on PATH                                  |
| 69   | `tsc` compile failed                               |
| 70   | unknown bump argument                              |
| rest | propagated from `vsce publish`                     |

---

## 5. Post-publish verification

1. Wait ~60 s for Marketplace indexing.
2. Open <https://marketplace.visualstudio.com/items?itemName=meeet-world.tars-tab>
   — version, README, and changelog should render.
3. From a clean VS Code instance:
   - **Extensions** sidebar → search **"tars-tab"** → **Install**.
   - Reload window. Confirm the TARS activity-bar icon appears
     and clicking it surfaces the Chat / Composer / Receipts
     views.
   - Start the local cockpit (`./scripts/RUN-COCKPIT.command` or
     equivalent), confirm the Chat view connects on
     `http://127.0.0.1:8765`.
4. Smoke-check on a second machine without TARS running — verify
   the extension shows the "backend offline" banner instead of
   crashing.

If anything is off:

- **404 / "publisher not found"**: registration in step 2 didn't
  complete or `package.json` `publisher` field drifted. Re-check
  both.
- **"Make sure to edit the README.md"**: vsce wants a non-empty
  README. The repo ships one already.
- **Icon rejected**: must be 128×128 and ≤500 KB. Re-export.
- **"Extension version is already published"**: bump with
  `./scripts/PUBLISH-EXTENSION.command patch` and retry.

---

## 6. Roll back (rare)

To unpublish a version (visible removal — extension stays in the
download mirror for users who already installed it):

```bash
npx --yes @vscode/vsce unpublish meeet-world.tars-tab@0.1.0 \
    -p "$VSCODE_PUBLISH_TOKEN"
```

To take the whole listing down:

```bash
npx --yes @vscode/vsce unpublish meeet-world.tars-tab \
    -p "$VSCODE_PUBLISH_TOKEN"
```

Use sparingly — Marketplace search ranking takes weeks to
recover from an unpublish.

---

## 7. What's still needed from the user

This launch is **almost** keyless. We need exactly two things
from a human:

1. **An Azure DevOps PAT** — see §1. Store in 1Password under
   "TARS / VS Code Marketplace PAT". Rotate every 90 days.
2. **A real `icon.png`** — see §3. The placeholder we ship is
   text; the script refuses to publish until you replace it.

Everything else (publisher registration, `package.json` metadata,
LICENSE, CHANGELOG, README, publish script) is already in the
repo and exercised by `PUBLISH-EXTENSION.command`.
