"""
BizVision AI — Financial Advisory AI Chatbot Schemas
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Requests ───────────────────────────────────────────────────────


class ChatMessageRequest(BaseModel):
    conversation_id: UUID | None = Field(
        default=None, description="Omit to start a new conversation"
    )
    content: str = Field(..., min_length=1, max_length=4000)
    include_modules: list[str] = Field(
        default_factory=list,
        description="Module contexts to fold in: recruitment|pricing|forecasting|sustainability",
    )


class ExecutiveReportRequest(BaseModel):
    title: str = Field(default="Executive Intelligence Report")
    include_modules: list[str] = Field(
        default_factory=lambda: [
            "recruitment",
            "pricing",
            "forecasting",
            "sustainability",
        ]
    )
    period_label: str = Field(default="Current Quarter")


# ── Responses ──────────────────────────────────────────────────────


class SourceReference(BaseModel):
    module: str
    reference_id: str
    summary: str


class ChatMessageResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    content: str
    created_at: datetime
    reasoning_trace: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    tokens_used: int = 0


class ChatTurn(BaseModel):
    role: str = Field(..., description="'user' | 'assistant'")
    content: str
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    conversation_id: UUID
    title: str
    turns: list[ChatTurn] = Field(default_factory=list)
    created_at: datetime


class ReportSection(BaseModel):
    heading: str
    body: str
    highlights: list[str] = Field(default_factory=list)


class ExecutiveReportResponse(BaseModel):
    report_id: UUID
    title: str
    generated_at: datetime
    sections: list[ReportSection]
    strategic_recommendations: list[str]
    key_risks: list[str]


# ── Detail / record-view (TASK-034) ────────────────────────────────


class ChatbotMessageDetailResponse(BaseModel):
    """Lightweight detail returned by `GET /chatbot/messages/{message_id}`.

    Backs the audit-feed deep-link from TASK-034
    (`reference_type='chatbot_message'`). The audit log row references
    one assistant message; this endpoint resolves that id to its
    parent `conversation_id` so the frontend can navigate to the
    conversation surface with that conversation loaded.

    Does NOT return the full conversation — only the fields the
    deep-link landing page needs to render a transition card +
    redirect into the chatbot workspace.
    """

    message_id: UUID
    conversation_id: UUID
    conversation_title: str
    role: str = Field(..., description="'user' | 'assistant' | 'system'")
    content: str
    position: int = Field(..., ge=0)
    created_at: datetime


class ChatbotExecutiveReportDetailResponse(BaseModel):
    """Persisted-row reconstruction returned by
    `GET /chatbot/executive-reports/{report_id}`. Backs the audit-feed
    deep-link from TASK-034 (`reference_type='chatbot_executive_report'`).

    The executive report row IS the unit of audit, unlike chatbot
    messages which live inside conversations. So the report has its
    own detail page that renders the persisted shape directly via
    the shared `<PersistedAnalysisDetail />` layout.
    """

    model_config = ConfigDict(protected_namespaces=())

    report_id: UUID
    title: str
    period_label: str
    modules_included: list[str]
    response_payload: dict
    model_version: str
    created_at: datetime
