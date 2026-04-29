"""TARS agent surface.

This package hosts long-lived "agent" types that sit alongside the
chat orchestrator. The first inhabitant is :mod:`vision_agent`
(Phase M / P8) — it inspects image attachments and produces a
text payload the orchestrator can fold into the prompt context.
"""

from .vision_agent import (
    VisionAgent,
    VisionPayload,
    VisionAttachmentSummary,
    is_image_attachment,
)

__all__ = [
    "VisionAgent",
    "VisionPayload",
    "VisionAttachmentSummary",
    "is_image_attachment",
]
