# Domain packs — spec

`backend/core/domains/` is a plugin system that adapts the neural core for a
specific audience. A pack is a Python package that contributes:

- A **manifest** (static metadata: slug, color, audience, capabilities).
- A set of **awareness sources** the pack listens to.
- A set of **actions** the agent can invoke.
- A constrained **system prompt** for the council in this mode.

Built-ins: `traders`, `business`, `mlm`, `science`.

## Pack layout

```
backend/core/domains/packs/<slug>/
  __init__.py        # re-exports the pack class
  manifest.json      # static metadata, source of truth for tooling
  pack.py            # DomainPack subclass + register(...)
  actions.py         # ActionSpec tuple
  awareness.py       # AwarenessSource tuple
  prompts.py         # SYSTEM_PROMPT string
```

`pack.py` registers itself by calling
`backend.core.domains.registry.register(...)` at import time. Importing
`backend.core.domains.packs` triggers all built-ins.

## Types

```python
@dataclass(frozen=True)
class DomainManifest:
    slug: str
    name: str
    short: str
    description: str
    color: str          # hex
    capabilities: tuple[str, ...]
    audience: str

@dataclass(frozen=True)
class ActionSpec:
    id: str
    name: str
    description: str
    handler: Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]
    schema: Mapping[str, Any]   # JSON-Schema-ish

@dataclass(frozen=True)
class AwarenessSource:
    id: str
    name: str
    description: str
    kind: str                   # "stream" | "poll" | "webhook" | "local"
    config: Mapping[str, Any]
```

## Action handler contract

Handlers must:

- be `async`,
- accept a `Mapping[str, Any]` of arguments,
- return a `dict` (or other `Mapping`) with at least `ok: bool`,
- never raise on ordinary user input — return
  `{"ok": False, "error": "..."}` instead,
- never auto-execute destructive ops (trades, sends, deletions). Confirmation
  flows are added by the host app.

## HTTP

`web_extras/routers/domains.py` mounts at `/api/domains`:

| Method | Path                                       | What                |
| ------ | ------------------------------------------ | ------------------- |
| GET    | `/api/domains`                             | list all packs      |
| GET    | `/api/domains/{slug}`                      | describe one pack   |
| GET    | `/api/domains/{slug}/awareness`            | list sources        |
| GET    | `/api/domains/{slug}/prompt`               | system prompt       |
| POST   | `/api/domains/{slug}/actions/{action_id}`  | invoke action       |

## Adding a new pack

1. Copy any built-in pack folder, e.g. `traders/`, into
   `backend/core/domains/packs/<your_slug>/`.
2. Update `manifest.json` and the `DomainManifest` in `pack.py`.
3. Replace `actions.py`, `awareness.py`, `prompts.py` content.
4. Add the import to `backend/core/domains/packs/__init__.py`.
5. Extend `tests/test_domains.py` `EXPECTED_SLUGS`.
6. Add a row in `docs/CHANGELOG_AGENTS.md`.

## Tests

```
PYTHONPATH=. pytest tests/test_domains.py -q
```

The suite asserts every expected slug is registered, the `to_dict()` shape is
present, and that every action handler is safe with empty arguments.
