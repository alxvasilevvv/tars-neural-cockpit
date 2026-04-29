"""Role registry — Phase M / P7.

A *role* is the operator's self-described position (Founder, Trader,
Researcher, Engineer, Operator, Marketer, or a free-form Custom one).
The orchestrator prepends the active role's overlay before any pack
prompt, so the assistant's voice tracks the operator's perspective
even when packs are switched mid-thread.

Roles are independent of:
- domain packs (those describe the *toolset*, not the *operator*),
- voice personas (those describe the *tone*, not the *position*).

Public surface:

    from backend.core.roles import (
        Role, RoleSlug, default_roles, get_active_role,
        set_active_role, create_custom_role, delete_custom_role,
        synthesise_overlay,
    )
"""

from .models import Role, RoleSlug
from .registry import (
    DEFAULT_ROLES,
    create_custom_role,
    default_roles,
    delete_custom_role,
    get_active_role,
    get_role,
    list_roles,
    set_active_role,
)
from .synthesis import synthesise_overlay

__all__ = [
    "Role",
    "RoleSlug",
    "DEFAULT_ROLES",
    "default_roles",
    "list_roles",
    "get_role",
    "get_active_role",
    "set_active_role",
    "create_custom_role",
    "delete_custom_role",
    "synthesise_overlay",
]
