# TARS Operator Automation Guide

This is the guide for `tars-ops` — the one button you press to drive TARS without remembering a single git command.

## Why this exists

You got tired of typing the same six git, curl, and pytest commands every time something needed checking. You also wanted Claude (and the parallel Cursor session) to be able to read what happened in your last operator run without you having to copy-paste terminal output into a chat.

`tars-ops` solves both:

- **For you:** double-click, pick a number, done.
- **For the agents:** every run writes its full output to `.tars-ops-output.txt` next to the script. Next time Claude opens this project, it reads that file and knows exactly what state things are in.

No more guessing. No more "wait, did I push?" No more "is CI green right now?"

## First time setup

1. Open Terminal once and run:
   ```
   chmod +x scripts/tars-ops.command
   ```
   That makes it double-clickable. You only do this once.

2. In Finder, navigate to the `scripts/` folder inside the Jarvis project. You'll see `tars-ops.command` with a little Terminal icon next to it.

3. Two ways to launch it from now on:
   - **Finder:** double-click the file.
   - **Spotlight:** Cmd+Space, type `tars-ops`, hit Enter.

4. The first time you run it, macOS may say "this is from an unidentified developer." Right-click the file once and choose **Open** to whitelist it. After that, double-click works normally.

That's the whole setup.

## What happens when you run it

A small AppleScript dialog pops up with six numbered options. You click one. The script does the thing, prints what happened to the Terminal window, and also saves the same output to `.tars-ops-output.txt`. The output file is gitignored, so it won't pollute commits.

## The six options — when and what

### 1. Status
**When:** before stepping away from the keyboard, or when you sit back down and want a quick "where are we?"
**What:** prints the current git branch, uncommitted changes, latest CI run status from GitHub, and whether the prod site is responding. Five seconds, no surprises.

### 2. Push
**When:** right after you've edited code locally and want it live.
**What:** pushes `main` to `origin`, then watches for the Cloudflare Pages webhook to confirm the auto-rebuild has kicked off. If CF doesn't pick it up within 30 seconds, it tells you so you know to check the CF dashboard.

### 3. Verify
**When:** after a release, or when someone says "is it actually working?"
**What:** runs the full end-to-end check — pings all 6 download URLs, fetches `install.sh`, hits the version endpoint, and runs the pytest sweep. Takes about a minute. Green checkmarks if everything's fine, red X with the failing URL if not.

### 4. Diagnose
**When:** something feels off but you don't know what.
**What:** quick triage. Checks the obvious failure modes (DNS, cert expiry, last CI run, CF Pages last deploy time) and tells you which layer is broken so you don't waste time poking the wrong thing.

### 5. Tag release
**When:** you're ready to cut a new version.
**What:** tags the current `HEAD` as `v9.X.Y` (it prompts you for the X.Y), pushes the tag, and that triggers the CI release workflow. Don't use this unless you actually want a release to go out.

### 6. Cursor sync
**When:** you've made a change you want the parallel Cursor session to notice.
**What:** appends a `SYNC` marker line to `AGENT_HANDOFF.md` with a timestamp and a short note. Cursor reads that file on its next turn and picks up the change.

## When NOT to use tars-ops

Some things are operator-only and live outside this script on purpose. If you're doing any of these, you're in the right place but the wrong tool:

- **Apple Developer cert renewal** — that's a browser + Keychain task, not scriptable.
- **Cloudflare dashboard changes** — DNS records, page rules, env vars. Use the CF web UI.
- **GitHub Secrets** — adding or rotating tokens. Use the GitHub web UI under repo Settings.
- **Anything that needs your 1Password unlock or 2FA prompt.**

If you find yourself wanting to automate one of these, don't. They're manual on purpose so a runaway script can't burn down the account.

## How to extend it

Adding a seventh option is three lines. Open `scripts/tars-ops.command` and:

1. Add your label to the AppleScript `choose from list` array.
2. Add a `case` branch in the `case "$choice" in` block.
3. Write the command(s) you want it to run inside that branch.

That's it. The output capture wraps everything automatically, so your new option's logs land in `.tars-ops-output.txt` like the rest.

If you're not sure what to add, ask Claude — it can read this file and the script and propose the new branch.
