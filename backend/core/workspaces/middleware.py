"""Workspace context middleware (Wave 110 — record-only).

The middleware extracts the requested workspace id from either the
``X-Workspace-Id`` header or the ``?workspace=`` query parameter and
records it in request scope so downstream handlers can opt in to
workspace-scoped behaviour. **It does not enforce fencing on any
existing endpoint** — that's deliberately deferred to v9.3 so this
wave stays additive.

Behaviour by call site:

- :func:`extract_workspace_id` — pure helper, returns the resolved
  workspace id or :data:`PERSONAL_WORKSPACE_ID` when the request did
  not name one. Suitable for direct call from handlers.
- :func:`record_requested_workspace` — same extraction but mutates
  ``request.state`` so the request-scoped logger / receipt writer can
  see the value.
- :func:`workspace_context_middleware` — Starlette/FastAPI
  middleware-shaped function. Wired into ``app.py`` opt-in: if the
  Workspaces store is disabled it short-circuits without setting
  state.

Header / param names are exported so tests + the FE fetch interceptor
can stay in sync.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional


WORKSPACE_HEADER = "X-Workspace-Id"
WORKSPACE_QUERY_PARAM = "workspace"
PERSONAL_WORKSPACE_ID = "personal"


def _coerce(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            return None
    value = value.strip()
    if not value:
        return None
    return value


def extract_workspace_id(request) -> str:
    """Return the workspace id requested by ``request``.

    Falls back to :data:`PERSONAL_WORKSPACE_ID` when neither the
    header nor the query param is set. The function is duck-typed
    against any object that exposes ``headers`` (Mapping-like) and
    ``query_params`` (Mapping-like) so the same helper works for
    Starlette / FastAPI / plain dicts in tests.
    """

    header_val: Optional[str] = None
    headers = getattr(request, "headers", None)
    if headers is not None:
        try:
            header_val = _coerce(headers.get(WORKSPACE_HEADER))
        except Exception:
            header_val = None
        if header_val is None:
            try:
                header_val = _coerce(headers.get(WORKSPACE_HEADER.lower()))
            except Exception:
                header_val = None

    if header_val:
        return header_val

    query_val: Optional[str] = None
    qp = getattr(request, "query_params", None)
    if qp is not None:
        try:
            query_val = _coerce(qp.get(WORKSPACE_QUERY_PARAM))
        except Exception:
            query_val = None

    if query_val:
        return query_val

    return PERSONAL_WORKSPACE_ID


def record_requested_workspace(request) -> str:
    """Resolve + stash the workspace id on ``request.state`` and return it.

    Best-effort: if ``request`` does not expose a mutable ``state``
    attribute (e.g. tests passing a plain dict) the function still
    returns the resolved id so the caller can use it.
    """

    workspace_id = extract_workspace_id(request)
    state = getattr(request, "state", None)
    if state is not None:
        try:
            setattr(state, "workspace_id", workspace_id)
        except Exception:
            pass
    return workspace_id


async def workspace_context_middleware(
    request,
    call_next: Callable[..., Awaitable],
):
    """ASGI middleware wrapper. Records the workspace then delegates.

    Wave 110: opt-in only, doesn't block requests. Wave 9.3 will
    promote this to an enforcing gate that 403s missing / unauthorised
    workspaces.
    """

    record_requested_workspace(request)
    response = await call_next(request)
    return response


__all__ = [
    "PERSONAL_WORKSPACE_ID",
    "WORKSPACE_HEADER",
    "WORKSPACE_QUERY_PARAM",
    "extract_workspace_id",
    "record_requested_workspace",
    "workspace_context_middleware",
]
