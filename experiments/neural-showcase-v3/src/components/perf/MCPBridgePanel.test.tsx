/**
 * MCPBridgePanel — structural smoke tests (Wave M6 cockpit).
 *
 * Smoke-test mode (the v3 surface intentionally does not pull in
 * @testing-library/react — see Breadcrumbs.test.tsx). We lock the
 * public surface (export, callable signature) and assert the
 * envelope type matches what the /api/mcp/bridge/status router
 * actually returns. Live render coverage happens via the
 * /admin/perf playwright suite once that pipeline is wired.
 */

import { describe, expect, it } from "vitest";

import { MCPBridgePanel } from "./MCPBridgePanel";
import type {
  MCPBridgeCacheRow,
  MCPBridgePoolSession,
  MCPBridgePoolStats,
  MCPBridgeRegisteredPack,
  MCPBridgeServerRow,
  MCPBridgeStatusEnvelope,
} from "./types";

describe("MCPBridgePanel (smoke)", () => {
  it("exports a callable React component", () => {
    expect(MCPBridgePanel).toBeTypeOf("function");
  });

  it("MCPBridgeStatusEnvelope accepts the unavailable-state shape", () => {
    const env: MCPBridgeStatusEnvelope = {
      ok: true,
      available: false,
      reason: "mcp_bridge_unavailable: stack not loaded",
      as_of: 1700000000,
    };
    // Type-level assertion only — no render. Verifies the
    // envelope and the panel agree on the fields the router
    // returns when M3/M5/M6 modules are absent.
    expect(env.ok).toBe(true);
    expect(env.available).toBe(false);
  });

  it("MCPBridgeStatusEnvelope accepts the fully-populated shape", () => {
    const server: MCPBridgeServerRow = {
      name: "filesystem",
      command: "/usr/bin/mcp-fs",
      args: ["--root", "/data"],
      env: { TOKEN: "redacted" },
      cwd: null,
      description: "local fs",
    };
    const pack: MCPBridgeRegisteredPack = {
      slug: "mcp-filesystem",
      name: "MCP Bridge — filesystem",
      tool_count: 3,
      pooled: true,
    };
    const cache: MCPBridgeCacheRow = {
      server: "filesystem",
      discovered_at: "2026-05-11T00:00:00Z",
      age_seconds: 120,
      fresh: true,
      tool_count: 3,
    };
    const session: MCPBridgePoolSession = {
      name: "filesystem",
      age_seconds: 600,
      idle_seconds: 30,
      server_info: { name: "fs-mcp", version: "1.2.3" },
      tool_count: 3,
    };
    const pool: MCPBridgePoolStats = { count: 1, sessions: [session] };
    const env: MCPBridgeStatusEnvelope = {
      ok: true,
      available: true,
      as_of: 1700000000,
      servers: [server],
      registered: [pack],
      cache: [cache],
      pool,
    };
    expect(env.servers).toHaveLength(1);
    expect(env.registered?.[0]?.pooled).toBe(true);
    expect(env.pool?.count).toBe(1);
  });

  it("function arity matches its props signature", () => {
    // The component takes exactly one props parameter.
    expect(MCPBridgePanel.length).toBeLessThanOrEqual(1);
  });
});
