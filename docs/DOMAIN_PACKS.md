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

## Composite packs

`backend/core/domains/composite.py` stitches multiple existing packs
into a single virtual pack. Action and awareness ids are namespaced
as `<sub_slug>__<id>` so handlers don't collide; destructive flags
and auth keys propagate from the leaf. Two ship by default:

- **`research_lab`** = `science` + `business` (paper → pitch).
- **`ops_room`** = `traders` + `mlm` (markets + downline).

Composite packs surface through the same `/api/domains/...` endpoints
and through the playbook runner.

## Composite playbooks

`backend/core/playbooks/runner.py` resolves each step's slug from the
`step.action` prefix (not from the playbook's directory), so a
playbook in `playbooks/research_lab/<name>.json` may freely reference:

- a composite-namespaced action: `research_lab.business__kpi_snapshot`,
- a composite-namespaced awareness: `research_lab.awareness.science__local_papers.snapshot`,
- an atomic-pack action directly: `business.kpi_snapshot` (handler
  is the same; the namespaced form is just a different surface).

Built-in samples:

- `playbooks/research_lab/paper_to_pitch.json` — papers + KPI in
  parallel, then daily brief.
- `playbooks/ops_room/morning_standup.json` — market summary +
  downline + news in parallel.

Tests pinning the cross-sub-pack flow live in
`tests/test_composite_playbooks.py` (8 cases: loader, awareness
parsing, sequential + parallel composite execution, destructive
flag propagation through the policy gate, cross-sub-pack templating).

## Tests

```
PYTHONPATH=. pytest tests/test_domains.py tests/test_composite_playbooks.py -q
```

The suite asserts every expected slug is registered, the `to_dict()` shape is
present, every action handler is safe with empty arguments, and composite
playbooks dispatch sub-pack actions + awareness through one trace.
