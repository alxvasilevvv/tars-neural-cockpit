"""GitHub connector — token-based read surface (Wave 73 Feature 2).

Audit found Iter F (#136) closed in the task list with zero code on
disk. The frontend GitHub connector card promises "list repos / open
issues / pulls" but every call hit a 404. This router fixes that.

Endpoints (all require ``GITHUB_TOKEN``; otherwise 503):

- ``GET /api/connectors/github/health`` — verify the token by calling
  ``GET /user`` upstream. Returns ``{configured, login, scopes,
  rate_limit}`` so the cockpit's Status page can render a real badge.
- ``GET /api/connectors/github/repos`` — list the authed user's repos
  (``visibility=all``, sorted by ``updated``, capped at 100).
- ``GET /api/connectors/github/{owner}/{repo}/issues`` — issues for
  one repo. ``state`` query: ``open|closed|all`` (default open).
- ``GET /api/connectors/github/{owner}/{repo}/pulls`` — pull requests
  for one repo. Same ``state`` semantics.

Implementation notes:

- stdlib ``urllib`` only — same pattern as
  :mod:`backend.core.council.llm`. No new deps.
- 60-second in-process LRU cache keyed on the URL — keeps GH happy
  on the 5000 req/h authed quota when the cockpit polls aggressively.
- Errors map cleanly: 401/403 → 502 (upstream auth issue, not us);
  404 → 404; everything else → 502 with the GH error body relayed.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.vault import get_secret


log = logging.getLogger("tars.connectors.github")


router = APIRouter(prefix="/api/connectors/github", tags=["connectors"])


_GITHUB_API = "https://api.github.com"
_DEFAULT_TIMEOUT_S = 12.0
_CACHE_TTL_S = 60.0
_USER_AGENT = "TARS-cockpit/9.1.0 (+https://tars.meeet.world)"

# url -> (expires_at, payload_json, status, headers)
_CACHE: dict[str, tuple[float, Any, int, dict[str, str]]] = {}
_CACHE_LOCK = threading.Lock()


def _resolve_token() -> str | None:
    return (
        get_secret("TARS_GITHUB_TOKEN")
        or get_secret("GITHUB_TOKEN")
        or os.getenv("GITHUB_TOKEN")
    )


def _require_token() -> str:
    token = _resolve_token()
    if not token:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "github_not_configured",
                "hint": "set GITHUB_TOKEN (or TARS_GITHUB_TOKEN)",
            },
        )
    return token


def _cache_get(url: str) -> tuple[Any, int, dict[str, str]] | None:
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(url)
        if not hit:
            return None
        expires, payload, status, headers = hit
        if expires < now:
            _CACHE.pop(url, None)
            return None
        return payload, status, headers


def _cache_put(
    url: str, payload: Any, status: int, headers: dict[str, str]
) -> None:
    with _CACHE_LOCK:
        _CACHE[url] = (time.time() + _CACHE_TTL_S, payload, status, headers)


def _gh_get(path: str, *, token: str, params: dict[str, Any] | None = None) -> tuple[Any, int, dict[str, str]]:
    """GET against api.github.com; cache 60s on 2xx; raise on transport."""

    qs = ""
    if params:
        # Use only str-safe keys; GH pagination accepts ?per_page=100&state=open
        from urllib.parse import urlencode
        qs = "?" + urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{_GITHUB_API}{path}{qs}"

    cached = _cache_get(url)
    if cached is not None:
        return cached

    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "authorization": f"token {token}",
            "accept": "application/vnd.github+json",
            "user-agent": _USER_AGENT,
            "x-github-api-version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT_S) as resp:
            body = resp.read()
            status = resp.getcode()
            headers = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        # Surface GH error JSON so the cockpit can show why.
        try:
            err_body = exc.read().decode("utf-8")
            err_json = json.loads(err_body or "{}")
        except Exception:
            err_json = {"message": str(exc.reason)}
        if exc.code == 404:
            raise HTTPException(status_code=404, detail=err_json) from exc
        if exc.code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail={"error": "github_auth_rejected", "upstream": err_json},
            ) from exc
        raise HTTPException(
            status_code=502,
            detail={"error": "github_http_error", "code": exc.code, "upstream": err_json},
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "github_transport_error", "message": str(exc)},
        ) from exc

    try:
        payload = json.loads(body.decode("utf-8") or "null")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "github_invalid_json", "message": str(exc)},
        ) from exc
    _cache_put(url, payload, status, headers)
    return payload, status, headers


def _slim_repo(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": repo.get("id"),
        "name": repo.get("name"),
        "full_name": repo.get("full_name"),
        "private": repo.get("private"),
        "fork": repo.get("fork"),
        "description": repo.get("description"),
        "default_branch": repo.get("default_branch"),
        "html_url": repo.get("html_url"),
        "language": repo.get("language"),
        "stargazers_count": repo.get("stargazers_count"),
        "open_issues_count": repo.get("open_issues_count"),
        "updated_at": repo.get("updated_at"),
        "pushed_at": repo.get("pushed_at"),
        "owner": (repo.get("owner") or {}).get("login"),
    }


def _slim_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "user": (issue.get("user") or {}).get("login"),
        "labels": [l.get("name") for l in (issue.get("labels") or []) if isinstance(l, dict)],
        "html_url": issue.get("html_url"),
        "comments": issue.get("comments"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "is_pull_request": "pull_request" in issue,
    }


def _slim_pr(pr: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "state": pr.get("state"),
        "draft": pr.get("draft"),
        "user": (pr.get("user") or {}).get("login"),
        "html_url": pr.get("html_url"),
        "head": (pr.get("head") or {}).get("ref"),
        "base": (pr.get("base") or {}).get("ref"),
        "created_at": pr.get("created_at"),
        "updated_at": pr.get("updated_at"),
    }


@router.get("/health")
async def github_health() -> dict[str, Any]:
    """Probe ``/user`` so the cockpit knows the token is good.

    Returns a uniform envelope even when not configured so the
    Status page rendering stays simple.
    """

    token = _resolve_token()
    if not token:
        return {
            "ok": True,
            "configured": False,
            "reason": "no_token",
            "scopes": [],
        }
    try:
        user, _status, headers = _gh_get("/user", token=token)
    except HTTPException as exc:
        # surface GH's complaint without 503ing the health probe
        return {
            "ok": False,
            "configured": True,
            "error": exc.detail,
        }
    scope_header = headers.get("x-oauth-scopes") or ""
    scopes = [s.strip() for s in scope_header.split(",") if s.strip()]
    rate = {
        "limit": headers.get("x-ratelimit-limit"),
        "remaining": headers.get("x-ratelimit-remaining"),
        "reset": headers.get("x-ratelimit-reset"),
    }
    return {
        "ok": True,
        "configured": True,
        "login": user.get("login") if isinstance(user, dict) else None,
        "id": user.get("id") if isinstance(user, dict) else None,
        "name": user.get("name") if isinstance(user, dict) else None,
        "scopes": scopes,
        "rate_limit": rate,
    }


@router.get("/repos")
async def github_repos(
    per_page: int = Query(default=30, ge=1, le=100),
    sort: str = Query(default="updated"),
    visibility: str = Query(default="all"),
) -> dict[str, Any]:
    token = _require_token()
    payload, _status, headers = _gh_get(
        "/user/repos",
        token=token,
        params={
            "per_page": per_page,
            "sort": sort,
            "visibility": visibility,
        },
    )
    items = [_slim_repo(r) for r in payload if isinstance(r, dict)] if isinstance(payload, list) else []
    return {
        "ok": True,
        "count": len(items),
        "repos": items,
        "rate_limit_remaining": headers.get("x-ratelimit-remaining"),
    }


@router.get("/{owner}/{repo}/issues")
async def github_issues(
    owner: str,
    repo: str,
    state: str = Query(default="open"),
    per_page: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    if state not in ("open", "closed", "all"):
        raise HTTPException(status_code=400, detail="state_must_be_open_closed_all")
    token = _require_token()
    payload, _status, headers = _gh_get(
        f"/repos/{owner}/{repo}/issues",
        token=token,
        params={"state": state, "per_page": per_page},
    )
    raw = payload if isinstance(payload, list) else []
    # GH /issues includes PRs too — keep the flag, let caller filter.
    items = [_slim_issue(i) for i in raw if isinstance(i, dict)]
    return {
        "ok": True,
        "owner": owner,
        "repo": repo,
        "state": state,
        "count": len(items),
        "issues": items,
        "rate_limit_remaining": headers.get("x-ratelimit-remaining"),
    }


@router.get("/{owner}/{repo}/pulls")
async def github_pulls(
    owner: str,
    repo: str,
    state: str = Query(default="open"),
    per_page: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    if state not in ("open", "closed", "all"):
        raise HTTPException(status_code=400, detail="state_must_be_open_closed_all")
    token = _require_token()
    payload, _status, headers = _gh_get(
        f"/repos/{owner}/{repo}/pulls",
        token=token,
        params={"state": state, "per_page": per_page},
    )
    raw = payload if isinstance(payload, list) else []
    items = [_slim_pr(p) for p in raw if isinstance(p, dict)]
    return {
        "ok": True,
        "owner": owner,
        "repo": repo,
        "state": state,
        "count": len(items),
        "pulls": items,
        "rate_limit_remaining": headers.get("x-ratelimit-remaining"),
    }


__all__ = ["router"]
