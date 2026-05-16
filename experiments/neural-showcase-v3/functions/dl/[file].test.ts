// Vitest contract for the `/dl/<file>` Pages Function — Wave 144.
//
// Covers the W142 fallback logic added to `fetchAsset()` for the
// case where v9.1.0 release assets live in a draft / untagged
// release (which is what happens when CI release runs are cancelled
// mid-publish — GitHub stores binaries under
// `untagged-<hash>` namespace until the tag-release association is
// finalised).
//
// Three primary cases:
//   1. by-tag lookup returns release with assets → asset hit
//   2. by-tag returns empty assets[] → fallback finds the asset in
//      a sibling release whose name matches the tag
//   3. neither path has the asset → null (proxy returns 404)
//
// Plus guards on the supporting helpers (allowlist, tagForFilename).
//
// We mock global fetch with vi.fn(). No `@cloudflare/vitest-pool-workers`
// — these are pure unit tests for the Function's internal logic.

import * as fs from "node:fs";
import * as path from "node:path";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
// eslint-disable-next-line @typescript-eslint/no-var-requires
import { __test } from "./[file]";

const {
  ALLOWED_FILENAMES,
  LATEST_TAG,
  SUPPORTED_VERSIONS,
  tagForFilename,
  fetchAsset,
} = __test;

// ── Minimal Env stub. The real PagesFunction Env has more fields but
// only GITHUB_RELEASE_TOKEN + GITHUB_REPO are read by fetchAsset.
const env = {
  GITHUB_RELEASE_TOKEN: "ghp_fake_test_token_just_for_unit_test",
  GITHUB_REPO: "alxvasilevvv/tars-neural-cockpit",
};

// ── Helpers to build canned GitHub Releases API responses.
function makeRelease(opts: {
  tagName: string;
  name?: string;
  assets?: Array<{ name: string; id?: number; url?: string }>;
}) {
  return {
    tag_name: opts.tagName,
    name: opts.name ?? `TARS ${opts.tagName}`,
    assets: (opts.assets ?? []).map((a, i) => ({
      id: a.id ?? 1000 + i,
      name: a.name,
      url: a.url ?? `https://api.github.com/repos/x/y/releases/assets/${1000 + i}`,
      size: 1024,
      content_type: "application/octet-stream",
    })),
  };
}

function mockFetchSequence(responses: Array<Response | { status: number; body: unknown }>) {
  const fetchMock = vi.fn();
  for (const r of responses) {
    if (r instanceof Response) {
      fetchMock.mockResolvedValueOnce(r);
    } else {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(r.body), {
          status: r.status,
          headers: { "content-type": "application/json" },
        }),
      );
    }
  }
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ── Static surface ────────────────────────────────────────────────

describe("ALLOWED_FILENAMES", () => {
  test("includes all 6 v9.1.0 cross-platform artifacts", () => {
    const v910 = [
      "TARS_9.1.0_aarch64.dmg",
      "TARS_9.1.0_x64.dmg",
      "TARS_9.1.0_amd64.AppImage",
      "TARS_9.1.0_amd64.deb",
      "TARS_9.1.0_x64-setup.exe",
      "TARS_9.1.0_x64_en-US.msi",
    ];
    for (const f of v910) {
      expect(ALLOWED_FILENAMES.has(f), `missing: ${f}`).toBe(true);
    }
  });

  test("includes the Tauri .app.tar.gz bundle + updater manifest", () => {
    expect(ALLOWED_FILENAMES.has("TARS_aarch64.app.tar.gz")).toBe(true);
    expect(ALLOWED_FILENAMES.has("latest.json")).toBe(true);
    expect(ALLOWED_FILENAMES.has("latest.json.sig")).toBe(true);
  });

  test("rejects path traversal + arbitrary filenames", () => {
    expect(ALLOWED_FILENAMES.has("../../etc/passwd")).toBe(false);
    expect(ALLOWED_FILENAMES.has("TARS_9.9.9_arbitrary.dmg")).toBe(false);
    expect(ALLOWED_FILENAMES.has("")).toBe(false);
  });
});

describe("tagForFilename", () => {
  test("derives v<X.Y.Z> from versioned filenames", () => {
    expect(tagForFilename("TARS_9.1.0_aarch64.dmg")).toBe("v9.1.0");
    expect(tagForFilename("TARS_9.1.0_amd64.AppImage")).toBe("v9.1.0");
    expect(tagForFilename("TARS_8.4.0_x64.dmg")).toBe("v8.4.0");
  });

  test("routes versionless tauri bundle + updater to LATEST_TAG", () => {
    expect(tagForFilename("TARS_aarch64.app.tar.gz")).toBe(LATEST_TAG);
    expect(tagForFilename("latest.json")).toBe(LATEST_TAG);
    expect(tagForFilename("latest.json.sig")).toBe(LATEST_TAG);
  });

  test("returns null for unrecognised shapes", () => {
    expect(tagForFilename("bogus.txt")).toBe(null);
    expect(tagForFilename("TARS.dmg")).toBe(null);
  });
});

// ── Fallback contract (W142) ──────────────────────────────────────

describe("fetchAsset() — happy path", () => {
  test("by-tag hit returns the asset and never lists releases", async () => {
    const release = makeRelease({
      tagName: "v9.1.0",
      assets: [{ name: "TARS_9.1.0_aarch64.dmg" }],
    });
    const fetchMock = mockFetchSequence([{ status: 200, body: release }]);

    const asset = await fetchAsset(env, "v9.1.0", "TARS_9.1.0_aarch64.dmg");

    expect(asset?.name).toBe("TARS_9.1.0_aarch64.dmg");
    // Single call — by-tag path satisfied; we did NOT fall through to /releases?per_page=30.
    expect(fetchMock.mock.calls.length).toBe(1);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/releases/tags/v9.1.0");
  });
});

describe("fetchAsset() — draft fallback (W142 core fix)", () => {
  test("by-tag returns empty assets[] → fallback finds asset in matching draft release", async () => {
    const byTagEmpty = makeRelease({ tagName: "v9.1.0", assets: [] });
    const draftRelease = makeRelease({
      tagName: "untagged-891bf1e8f4a8f7591346",
      name: "TARS v9.1.0",
      assets: [
        { name: "TARS_9.1.0_aarch64.dmg" },
        { name: "TARS_9.1.0_amd64.AppImage" },
      ],
    });
    const unrelatedRelease = makeRelease({
      tagName: "v8.4.0",
      assets: [{ name: "TARS_8.4.0_aarch64.dmg" }],
    });

    const fetchMock = mockFetchSequence([
      { status: 200, body: byTagEmpty }, // primary: by-tag
      { status: 200, body: [draftRelease, unrelatedRelease] }, // fallback: list
    ]);

    const asset = await fetchAsset(env, "v9.1.0", "TARS_9.1.0_aarch64.dmg");

    expect(asset?.name).toBe("TARS_9.1.0_aarch64.dmg");
    expect(fetchMock.mock.calls.length).toBe(2);
    expect(String(fetchMock.mock.calls[1][0])).toContain("/releases?per_page=30");
  });

  test("fallback prefers releases whose name mentions the target tag", async () => {
    const byTagEmpty = makeRelease({ tagName: "v9.1.0", assets: [] });
    // Two releases both contain the filename. The one whose NAME mentions
    // the target tag must win (ranking guarantee in W142).
    const wrongRelease = makeRelease({
      tagName: "untagged-aaaaaaa",
      name: "TARS v9.2.0 preview",
      assets: [{ name: "TARS_9.1.0_aarch64.dmg", id: 999 }],
    });
    const correctRelease = makeRelease({
      tagName: "untagged-bbbbbbb",
      name: "TARS v9.1.0",
      assets: [{ name: "TARS_9.1.0_aarch64.dmg", id: 7777 }],
    });

    mockFetchSequence([
      { status: 200, body: byTagEmpty },
      { status: 200, body: [wrongRelease, correctRelease] },
    ]);

    const asset = await fetchAsset(env, "v9.1.0", "TARS_9.1.0_aarch64.dmg");
    expect(asset?.id).toBe(7777);
  });
});

describe("fetchAsset() — total miss", () => {
  test("by-tag empty AND list has no matching asset → null", async () => {
    const byTagEmpty = makeRelease({ tagName: "v9.1.0", assets: [] });
    const unrelated = makeRelease({
      tagName: "v8.4.0",
      assets: [{ name: "TARS_8.4.0_aarch64.dmg" }],
    });

    mockFetchSequence([
      { status: 200, body: byTagEmpty },
      { status: 200, body: [unrelated] },
    ]);

    const asset = await fetchAsset(env, "v9.1.0", "TARS_9.1.0_aarch64.dmg");
    expect(asset).toBe(null);
  });

  test("by-tag 404 + list 500 → null (proxy will return 404 to caller)", async () => {
    mockFetchSequence([
      new Response("Not Found", { status: 404 }),
      new Response("Bad Gateway", { status: 500 }),
    ]);

    const asset = await fetchAsset(env, "v9.1.0", "TARS_9.1.0_aarch64.dmg");
    expect(asset).toBe(null);
  });
});

// ─── W291 sentinel ──────────────────────────────────────────────────────
// Cross-validates that every TARS_<ver>_<asset> filename the live
// `public/install.sh` can build is in `ALLOWED_FILENAMES`. If the
// install funnel ever bumps `version` past `SUPPORTED_VERSIONS`, this
// test fires before deploy — no silent `404 not_in_allowlist` in prod.
//
// install.sh uses `${version}` (derived from the live
// `/api/product/version` response), but historic / future variants
// may use `${VER}`. The regex below accepts BOTH forms.
describe("sentinel — install.sh ↔ allowlist sync (W291)", () => {
  test("every filename install.sh can build is in ALLOWED_FILENAMES", () => {
    // Read the live install.sh that CF Pages serves. If this path
    // changes, update the sentinel — but never let install.sh drift
    // out of sync with the allowlist silently.
    const installShPath = path.resolve(__dirname, "../../public/install.sh");
    const text = fs.readFileSync(installShPath, "utf-8");

    // install.sh derives `version` from `/api/product/version` at
    // runtime — there is no compile-time fallback string. We use the
    // newest SUPPORTED_VERSIONS entry as the substitution to verify
    // the proxy can serve whatever install.sh asks for at that
    // version. (Sentinel test #2 below pins LATEST_TAG into
    // SUPPORTED_VERSIONS, closing the loop.)
    const ver = SUPPORTED_VERSIONS[0];
    expect(ver, "SUPPORTED_VERSIONS must have at least one entry").toBeTruthy();

    // Match BOTH `TARS_${VER}_…` (operator-spec style) and
    // `TARS_${version}_…` (current install.sh style).
    const patterns = Array.from(
      text.matchAll(/TARS_\$\{(?:VER|version)\}_[A-Za-z0-9._\-]+/g),
    ).map((m) => m[0].replace(/\$\{(?:VER|version)\}/, ver));

    expect(
      patterns.length,
      "install.sh must reference at least one TARS_<ver>_* asset",
    ).toBeGreaterThanOrEqual(3);

    for (const name of patterns) {
      expect(
        ALLOWED_FILENAMES.has(name),
        `install.sh references "${name}" but ALLOWED_FILENAMES is missing it — bump SUPPORTED_VERSIONS in [file].ts`,
      ).toBe(true);
    }
  });

  test("SUPPORTED_VERSIONS includes the LATEST_TAG version", () => {
    const latestVer = LATEST_TAG.replace(/^v/, "");
    expect(
      SUPPORTED_VERSIONS.includes(latestVer),
      `LATEST_TAG=${LATEST_TAG} but SUPPORTED_VERSIONS=${JSON.stringify(SUPPORTED_VERSIONS)} — add "${latestVer}" to the list`,
    ).toBe(true);
  });
});
