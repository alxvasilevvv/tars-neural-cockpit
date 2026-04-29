/**
 * Per-tab session id.
 *
 * The cockpit assigns one ses_<id> when the page mounts and reuses it
 * for every action invocation, deliberation, and SSE handshake. The
 * backend tags every emitted event with this id (via the
 * x-tars-session-id header → trace_scope), letting the cost ledger,
 * usage rollup, and meeet timeline filter by session.
 *
 * Persisted in sessionStorage so a hot reload keeps the same id; a
 * fresh tab gets a fresh one.
 */

const KEY = "tars.session_id";

function rand(): string {
  const buf = new Uint8Array(8);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(buf);
  } else {
    for (let i = 0; i < buf.length; i++) buf[i] = Math.floor(Math.random() * 256);
  }
  let out = "";
  for (let i = 0; i < buf.length; i++) {
    out += buf[i].toString(16).padStart(2, "0");
  }
  return out;
}

export function getSessionId(): string {
  if (typeof window === "undefined") return `ses_${rand()}`;
  let cur = window.sessionStorage.getItem(KEY);
  if (!cur) {
    cur = `ses_${rand()}`;
    window.sessionStorage.setItem(KEY, cur);
  }
  return cur;
}

export function rotateSessionId(): string {
  const fresh = `ses_${rand()}`;
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(KEY, fresh);
  }
  return fresh;
}
