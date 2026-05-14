"""Composer planner — :func:`plan_from_transcript`.

Turns a voice/text transcript into a structured :class:`ComposerPlan`
by:

1. Building a context block from the project: recent files
   (``git log --name-only -5`` if available), top-of-tree directory
   listing, and any active rules (W239).
2. Calling the active LLM (model picked via W237 ``providers``
   active-model file) with a strict JSON schema for the response.
3. Parsing the response into ``EditOp`` objects, computing unified
   diffs against the on-disk file contents, and enforcing safety
   limits.

When no LLM key is available (offline mode, CI), the planner falls
back to a deterministic stub that parses simple imperative commands
("rename Customer to Account") so the surface still works for tests
and demos.
"""

from __future__ import annotations

import difflib
import fnmatch
import json
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .types import ComposerPlan, EditOp, SafetyError


# ---------------------------------------------------------------------------
# Safety limits
# ---------------------------------------------------------------------------


MAX_OPS: int = 50
MAX_DIFF_BYTES: int = 5 * 1024 * 1024  # 5 MiB

# Paths the planner refuses to touch unless the transcript includes
# the explicit ``--allow-secrets`` opt-in token.
FORBIDDEN_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    ".git",
    ".git/*",
    "*/.git/*",
    "*.pfx",
    "id_rsa",
    "id_ed25519",
)

_ALLOW_SECRETS_TOKEN = "--allow-secrets"

# Rough token estimate for the cost preview: chars / 4. Aligned with
# the W235 metering recorder so the cockpit shows consistent numbers
# pre- and post-apply.
_CHARS_PER_TOKEN = 4
_DEFAULT_RATE_IN = 3.0 / 1_000_000   # $3 / MTok (Claude Sonnet)
_DEFAULT_RATE_OUT = 15.0 / 1_000_000  # $15 / MTok (Claude Sonnet)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_forbidden(rel_path: str) -> bool:
    """Match against :data:`FORBIDDEN_PATTERNS` using fnmatch.

    Strips a single ``./`` prefix when present — we deliberately
    avoid ``lstrip("./")`` because that would chew leading dots off
    of files like ``.env`` and silently let the secrets fence through.
    """

    if not rel_path:
        return False
    norm = rel_path.replace("\\", "/")
    if norm.startswith("./"):
        norm = norm[2:]
    for pat in FORBIDDEN_PATTERNS:
        if fnmatch.fnmatch(norm, pat):
            return True
        # Match also bare filename for top-level .env / .key etc.
        base = norm.rsplit("/", 1)[-1]
        if fnmatch.fnmatch(base, pat):
            return True
    # Anything underneath a top-level .git/ directory is fenced.
    if norm.startswith(".git/") or norm == ".git":
        return True
    return False


def _git_recent(project_root: Path, n: int = 5) -> list[str]:
    """Return the N most recently changed files via ``git log``.

    Silent fallback to empty list if git isn't available or the
    directory isn't a repo. The planner only uses this as a context
    hint; absence is non-fatal.
    """

    try:
        out = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", f"-{int(n)}"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if out.returncode != 0:
            return []
        seen: list[str] = []
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line or line in seen:
                continue
            seen.append(line)
            if len(seen) >= n:
                break
        return seen
    except Exception:  # noqa: BLE001
        return []


def _tree_summary(project_root: Path, max_entries: int = 80) -> list[str]:
    """Top-of-tree directory listing, capped for prompt size."""

    out: list[str] = []
    try:
        for entry in sorted(project_root.iterdir()):
            if entry.name.startswith(".") and entry.name not in (".env.example",):
                continue
            kind = "d" if entry.is_dir() else "f"
            out.append(f"{kind} {entry.name}")
            if len(out) >= max_entries:
                break
    except OSError:
        pass
    return out


def _load_active_model() -> str | None:
    """Best-effort: read the active model id from W237's persisted file."""

    try:
        raw = os.environ.get("TARS_ACTIVE_MODEL_PATH") or "~/.tars/active_model"
        p = Path(os.path.expanduser(raw))
        if p.is_file():
            v = p.read_text(encoding="utf-8").strip()
            return v or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _load_rules_text() -> str:
    """Inline the operator's global rules (W239) for the system prompt.

    Silent fallback to empty string — rules are a hint, not a P0.
    """

    try:
        from backend.core.rules import load_global_rules  # noqa: PLC0415

        rules = [r for r in load_global_rules() if getattr(r, "enabled", True)]
        if not rules:
            return ""
        lines = [f"- {r.text}" for r in rules if getattr(r, "text", "").strip()]
        return "\n".join(lines)
    except Exception:  # noqa: BLE001
        return ""


def _read_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _unified_diff(
    old: str | None,
    new: str | None,
    *,
    a_label: str,
    b_label: str,
) -> str:
    a = (old or "").splitlines(keepends=True)
    b = (new or "").splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(a, b, fromfile=a_label, tofile=b_label, n=3)
    )


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _have_anthropic() -> bool:
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("TARS_ANTHROPIC_API_KEY")
    )


def _have_openrouter() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _build_prompt(
    transcript: str,
    project_root: Path,
    *,
    rules: str,
    tree: list[str],
    recent: list[str],
) -> str:
    """Compose the system+user prompt as a single string.

    Kept LLM-agnostic on purpose — the active model bridge wraps this
    in whatever envelope its API requires.
    """

    parts: list[str] = []
    parts.append(
        "You are TARS Composer — a multi-file code-edit planner."
        " Given a natural-language transcript from the operator,"
        " return a STRICT JSON object with this shape:"
    )
    parts.append(
        '{"summary": "<one-line intent>",'
        ' "ops": [{"op": "create|modify|delete|rename",'
        ' "path": "<repo-relative>",'
        ' "new_path": "<for rename>",'
        ' "new_content": "<full file content>"}]}'
    )
    parts.append("Constraints:")
    parts.append(f"- Maximum {MAX_OPS} ops.")
    parts.append(
        "- Never touch .env, *.pem, *.key, or .git/ unless the transcript"
        f" contains the literal token {_ALLOW_SECRETS_TOKEN!r}."
    )
    parts.append("- Paths must be repo-relative (no leading slash, no `..`).")
    parts.append(
        "- For ``modify``, return the FULL new file content, not a patch."
    )
    if rules:
        parts.append("Operator rules:")
        parts.append(rules)
    parts.append(f"Project root: {project_root}")
    if tree:
        parts.append("Top-level tree:")
        parts.append("\n".join(tree))
    if recent:
        parts.append("Recently changed files:")
        parts.append("\n".join(f"- {p}" for p in recent))
    parts.append("Transcript:")
    parts.append(transcript)
    parts.append("Respond with ONLY the JSON object, no prose, no markdown.")
    return "\n\n".join(parts)


def _call_llm(prompt: str, *, model: str | None) -> dict[str, Any] | None:
    """Try to call an available LLM provider.

    Returns the parsed JSON dict on success, or ``None`` on any
    failure (the caller falls back to the stub planner). Keep this
    function exception-free at the boundary — composer planning
    should never crash the request.
    """

    # Anthropic — preferred when key is present.
    if _have_anthropic():
        try:
            import httpx  # noqa: PLC0415

            key = (
                os.environ.get("TARS_ANTHROPIC_API_KEY")
                or os.environ["ANTHROPIC_API_KEY"]
            )
            anthropic_model = (
                model.split(":", 1)[-1] if model and model.startswith("anthropic:")
                else os.environ.get("TARS_ANTHROPIC_MODEL")
                or "claude-3-5-sonnet-20241022"
            )
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": anthropic_model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            if r.status_code >= 400:
                return None
            data = r.json()
            blocks = data.get("content") or []
            text = "".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            )
            return _extract_json(text)
        except Exception:  # noqa: BLE001
            return None

    if _have_openrouter():
        try:
            import httpx  # noqa: PLC0415

            key = os.environ["OPENROUTER_API_KEY"]
            or_model = (
                model.split(":", 1)[-1]
                if model and model.startswith("openrouter:")
                else "anthropic/claude-3.5-sonnet"
            )
            r = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "authorization": f"Bearer {key}",
                    "content-type": "application/json",
                },
                json={
                    "model": or_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4096,
                },
                timeout=60.0,
            )
            if r.status_code >= 400:
                return None
            data = r.json()
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return _extract_json(text)
        except Exception:  # noqa: BLE001
            return None

    return None


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort JSON parser tolerant of markdown fences."""

    if not text:
        return None
    candidates: list[str] = []
    for m in _JSON_BLOCK_RE.finditer(text):
        candidates.append(m.group(1))
    candidates.append(text)
    for c in candidates:
        c = c.strip()
        # Trim any leading non-JSON preamble.
        if not c.startswith("{"):
            idx = c.find("{")
            if idx < 0:
                continue
            c = c[idx:]
            depth = 0
            end = -1
            for i, ch in enumerate(c):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end > 0:
                c = c[: end + 1]
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# Stub planner (offline / no key path)
# ---------------------------------------------------------------------------


_RENAME_RE = re.compile(
    r"rename\s+([A-Za-z_][A-Za-z0-9_]*)\s+to\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_CREATE_RE = re.compile(
    # Accepts both regular paths (foo.py, src/bar.ts) and dot-prefixed
    # files (.env, .gitignore) — the latter is how the safety fence
    # gets exercised by transcripts asking to create secrets files.
    r"(?:create|add)\s+(?:file\s+)?[`\"']?([\w./\-]*\.[\w/.\-]+)[`\"']?",
    re.IGNORECASE,
)


def _stub_plan(transcript: str, project_root: Path) -> dict[str, Any]:
    """Tiny offline planner: rename-symbol + create-file commands.

    Doesn't try to be smart — it exists so the surface is testable
    without an LLM key, and so the "make changes" voice command
    degrades gracefully rather than erroring.
    """

    summary_bits: list[str] = []
    ops: list[dict[str, Any]] = []

    m = _RENAME_RE.search(transcript)
    if m:
        old, new = m.group(1), m.group(2)
        summary_bits.append(f"rename symbol {old} -> {new}")
        # Sweep text files in the tree (cap at 200 to bound cost).
        scanned = 0
        for p in project_root.rglob("*"):
            if scanned >= 200:
                break
            if not p.is_file():
                continue
            rel = p.relative_to(project_root).as_posix()
            if _is_forbidden(rel):
                continue
            if p.suffix.lower() not in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".md",
                ".txt",
                ".yml",
                ".yaml",
                ".html",
                ".css",
                ".json",
                ".rs",
                ".go",
            }:
                continue
            scanned += 1
            try:
                txt = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if old not in txt:
                continue
            new_txt = re.sub(rf"\b{re.escape(old)}\b", new, txt)
            if new_txt == txt:
                continue
            ops.append(
                {
                    "op": "modify",
                    "path": rel,
                    "new_content": new_txt,
                }
            )
    for m2 in _CREATE_RE.finditer(transcript):
        path = m2.group(1)
        if (project_root / path).exists():
            continue
        # NOTE: forbidden paths are emitted as ops here on purpose —
        # the post-processing validation loop in plan_from_transcript
        # turns them into a SafetyError. We never silently drop a
        # secrets-related op; the operator must see the refusal.
        ops.append(
            {
                "op": "create",
                "path": path,
                "new_content": (
                    f"# {path}\n# Stub created by TARS composer "
                    f"from transcript:\n# {transcript[:200]}\n"
                ),
            }
        )
        summary_bits.append(f"create {path}")
    summary = "; ".join(summary_bits) or (
        f"draft plan from transcript ({len(transcript)} chars)"
    )
    return {"summary": summary, "ops": ops}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def plan_from_transcript(
    transcript: str,
    project_root: Path | str,
    *,
    allow_llm: bool = True,
) -> ComposerPlan:
    """Build a :class:`ComposerPlan` from a free-form transcript.

    Parameters
    ----------
    transcript:
        Raw text from STT or chat input. May include the literal
        ``--allow-secrets`` token to bypass the secrets fence.
    project_root:
        Directory the planner treats as the repo root. Paths in the
        plan are stored relative to this root.
    allow_llm:
        When False, skip the LLM path entirely (used by tests). The
        stub planner is always invoked as a fallback when the LLM
        path returns ``None``.

    Returns
    -------
    ComposerPlan
        Always returns a plan; if the planner refuses everything the
        plan has zero ops and an ``intent_summary`` explaining why.

    Raises
    ------
    SafetyError
        If a returned op targets a forbidden path and the operator
        did not opt in via ``--allow-secrets``.
    """

    transcript = (transcript or "").strip()
    root = Path(project_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"project_root does not exist: {root}")

    allow_secrets = _ALLOW_SECRETS_TOKEN in transcript

    # ---- gather context ------------------------------------------------
    rules = _load_rules_text()
    tree = _tree_summary(root)
    recent = _git_recent(root)

    # ---- call LLM (best-effort) ---------------------------------------
    active_model = _load_active_model()
    raw: dict[str, Any] | None = None
    if allow_llm:
        prompt = _build_prompt(
            transcript, root, rules=rules, tree=tree, recent=recent
        )
        raw = _call_llm(prompt, model=active_model)

    if raw is None:
        raw = _stub_plan(transcript, root)

    summary = str(raw.get("summary") or "draft plan").strip()
    raw_ops = raw.get("ops") or []
    if not isinstance(raw_ops, list):
        raw_ops = []

    if len(raw_ops) > MAX_OPS:
        raise SafetyError(
            f"plan exceeds max ops ({len(raw_ops)} > {MAX_OPS})"
        )

    ops: list[EditOp] = []
    total_diff_bytes = 0
    for idx, raw_op in enumerate(raw_ops):
        if not isinstance(raw_op, dict):
            continue
        op_kind = str(raw_op.get("op") or "modify").lower().strip()
        path = str(raw_op.get("path") or "").strip().lstrip("/")
        new_path = raw_op.get("new_path")
        if new_path is not None:
            new_path = str(new_path).strip().lstrip("/") or None

        if not path or ".." in Path(path).parts:
            continue
        if _is_forbidden(path) and not allow_secrets:
            raise SafetyError(
                f"refused: would touch forbidden path {path!r}",
                op_index=idx,
            )
        if new_path and _is_forbidden(new_path) and not allow_secrets:
            raise SafetyError(
                f"refused: rename target {new_path!r} is forbidden",
                op_index=idx,
            )

        abs_path = (root / path).resolve()
        # Refuse to escape the project root.
        try:
            abs_path.relative_to(root)
        except ValueError:
            continue

        old_content: str | None = None
        if abs_path.exists() and abs_path.is_file():
            old_content = _read_file(abs_path)

        new_content = raw_op.get("new_content")
        if new_content is not None:
            new_content = str(new_content)
        # For rename without explicit new_content, carry old_content
        # through to the new path so the diff is empty (intentional).
        if op_kind == "rename" and new_content is None:
            new_content = old_content

        if op_kind == "delete":
            new_content = ""

        diff = _unified_diff(
            old_content if op_kind != "create" else "",
            new_content if op_kind != "delete" else "",
            a_label=path,
            b_label=new_path or path,
        )

        edit = EditOp(
            op=op_kind,
            path=path,
            new_path=new_path,
            old_content=old_content,
            new_content=new_content,
            diff_unified=diff,
        )
        total_diff_bytes += edit.size_bytes()
        if total_diff_bytes > MAX_DIFF_BYTES:
            raise SafetyError(
                f"plan exceeds max diff size "
                f"({total_diff_bytes} > {MAX_DIFF_BYTES} bytes)"
            )
        ops.append(edit)

    # Cost / token preview --------------------------------------------
    char_total = sum(
        len(e.diff_unified or "") + len(e.new_content or "") for e in ops
    )
    est_tokens = max(1, char_total // _CHARS_PER_TOKEN)
    # Symmetric in/out estimate, halved.
    est_cost = est_tokens * (_DEFAULT_RATE_IN + _DEFAULT_RATE_OUT) / 2

    plan_id = "cmp_" + uuid.uuid4().hex[:12]
    return ComposerPlan(
        plan_id=plan_id,
        transcript=transcript,
        intent_summary=summary,
        ops=ops,
        estimated_tokens=int(est_tokens),
        estimated_cost_usd=round(float(est_cost), 6),
        created_at=datetime.now(timezone.utc),
        state="draft",
        project_root=str(root),
        model=active_model,
    )
