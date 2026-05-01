from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class BusinessPack(DomainPack):
    manifest = DomainManifest(
        slug="business",
        name="Business",
        short="A second brain for your operating cadence.",
        description=(
            "Deals, contacts, revenue and KPI nodes plugged into your daily "
            "mail / calendar / CRM, with a council-composed daily brief."
        ),
        color="#8b5cf6",
        capabilities=(
            "crm_awareness",
            "kpi_graph",
            "daily_brief",
            "outreach_drafts",
        ),
        audience="founders, operators, GTM leaders",
    )

    def auth_vault_keys(self) -> tuple[str, ...]:
        return (
            "HUBSPOT_API_KEY",
            "PIPEDRIVE_API_KEY",
            "MEEET_API_KEY",
            "SMTP_HOST",
            "SMTP_USER",
            "SMTP_PASSWORD",
            "SMTP_OAUTH_TOKEN",
            "SMTP_OAUTH_REFRESH_TOKEN",
            "SMTP_OAUTH_CLIENT_ID",
            "SMTP_OAUTH_CLIENT_SECRET",
            "SMTP_OAUTH_TOKEN_URL",
            "SMTP_OAUTH_TENANT",
            "SMTP_OAUTH_SCOPE",
            "SMTP_PROVIDER",
            "SMTP_FROM",
        )

    def actions(self):
        return ACTIONS

    def awareness(self):
        return SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT


register(BusinessPack())
