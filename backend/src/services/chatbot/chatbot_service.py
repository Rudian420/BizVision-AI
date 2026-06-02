"""
BizVision AI — Financial Advisory AI Chatbot Service

Persistence-aware service. Every `/message` REST call and every
WebSocket `complete` event writes its user turn + assistant turn to
`chatbot_conversations` + `chatbot_messages`; every
`/executive-report` writes one row to `chatbot_executive_reports`.
`list_conversations` and `get_conversation` read from the DB with
per-user 404. The streamed token chunks themselves are NOT persisted
— the final assistant `content` is the row of record.

ML state (2026-05-30):
  • **Persistence is real.** Conversations, messages, and reports are
    written/read against Postgres; cross-user authorisation is enforced
    by 404 on `_find_conversation` / `_find_report`.
  • **Real-ML branch is real.** With `CHATBOT_USE_REAL_ML=True`,
    `/message` and the WebSocket `stream_response` delegate to the
    `ChatbotInferenceClient` (mirror of ADR-024) which dispatches to
    `ml.chatbot` (HashEmbedder + NumpyVectorStore + KeywordRouter +
    RagResponder + AgentExecutor — wave 1 per ADR-030).
  • **Mock branch is preserved.** Same code paths, same persisted shape
    — the flag flip changes only the upstream agent, not the DB schema
    or response contract.
  • **Executive report stays closed-form** in both branches — same
    posture as pricing's `/elasticity`, forecasting's `/sensitivity`,
    and sustainability's `/benchmarks/{industry}`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.v1.schemas.chatbot import (
    ChatbotExecutiveReportDetailResponse,
    ChatbotMessageDetailResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatTurn,
    ConversationHistoryResponse,
    ExecutiveReportRequest,
    ExecutiveReportResponse,
    ReportSection,
    SourceReference,
)
from src.core.config import settings
from src.models.audit import AuditModule
from src.models.chatbot import (
    ChatbotConversation,
    ChatbotExecutiveReport,
    ChatbotMessage,
    ChatbotMessageRole,
)
from src.services.audit.audit_service import AuditService

_MOCK_MODEL_VERSION = "chatbot-mock-0.1"
_REAL_MODEL_VERSION = "chatbot-real-0.1"


def _current_model_version() -> str:
    """Resolve the active chatbot model version at write-time.

    Reading the flag here (rather than at module import) means flipping
    `CHATBOT_USE_REAL_ML` between requests is reflected in the
    persisted `model_version` column without a process restart — same
    pattern as pricing's / forecasting's / sustainability's
    `_current_model_version()`.
    """
    return _REAL_MODEL_VERSION if settings.CHATBOT_USE_REAL_ML else _MOCK_MODEL_VERSION

_CANNED_ANSWER = (
    "Based on the latest signals across your modules, I'd prioritise a modest "
    "price increase on inelastic SKUs while holding headcount flat this quarter. "
    "Your ESG risk is low, so there's no near-term regulatory drag on the forecast."
)
_REASONING_TRACE = [
    "Interpreted the executive question",
    "Folded in requested module contexts",
    "Generated a synthesised recommendation",
]
_TOKENS_USED = 128


def _source_to_api(source_dict: dict) -> dict:
    """Project a persisted source-payload dict down to the API's
    `SourceReference` shape.

    The real-ML branch persists extra `rank` + `score` fields for
    downstream re-rendering; the API contract only exposes
    `module` + `reference_id` + `summary`. Filter here so both
    branches produce identical response shapes.
    """
    return {
        "module": source_dict["module"],
        "reference_id": source_dict["reference_id"],
        "summary": source_dict["summary"],
    }


def _derive_title(content: str) -> str:
    """First 8 words of the first user message, capped at 200 chars."""
    snippet = " ".join(content.strip().split()[:8])
    return (snippet[:197] + "…") if len(snippet) > 200 else snippet or "New conversation"


class ChatbotService:
    """Persistence-aware chatbot service.

    The DB session is passed per call (rather than held on the instance)
    so the WebSocket handler — which lives across many requests — can
    open a fresh session per turn without leaking the previous one.
    """

    # ── 1. REST send_message ────────────────────────────────────────
    async def send_message(
        self,
        request: ChatMessageRequest,
        user_id: UUID,
        db: AsyncSession,
    ) -> ChatMessageResponse:
        conversation = await self._get_or_create_conversation(
            conversation_id=request.conversation_id,
            user_id=user_id,
            db=db,
            seed_title_from=request.content,
        )

        # Persist the user turn (same shape across both branches).
        user_position = conversation.message_count
        db.add(
            ChatbotMessage(
                id=uuid4(),
                conversation_id=conversation.id,
                role=ChatbotMessageRole.USER,
                position=user_position,
                content=request.content,
                include_modules=request.include_modules,
                reasoning_trace=[],
                sources=[],
                tokens_used=0,
            )
        )

        # Generate the assistant turn — real-ML or mock based on flag.
        assistant_message_id = uuid4()
        assistant_position = user_position + 1
        content, reasoning_trace, sources_payload, tokens_used = self._build_assistant_turn(
            content=request.content,
            include_modules=tuple(request.include_modules),
            user_id=user_id,
        )

        db.add(
            ChatbotMessage(
                id=assistant_message_id,
                conversation_id=conversation.id,
                role=ChatbotMessageRole.ASSISTANT,
                position=assistant_position,
                content=content,
                include_modules=request.include_modules,
                reasoning_trace=reasoning_trace,
                sources=sources_payload,
                tokens_used=tokens_used,
            )
        )

        # Bump conversation aggregates.
        conversation.message_count = assistant_position + 1
        conversation.total_tokens_used += tokens_used
        conversation.modules_in_scope = sorted(
            set(conversation.modules_in_scope) | set(request.include_modules)
        )
        await db.flush()

        # Cross-module audit log (ADR-031). One row per /message — the
        # assistant_message_id is the soft FK; sources_payload's
        # `module` + `reference_id` per source are echoed into
        # `response_summary` so Phase-4 dashboards can see which
        # other-module records the chatbot pulled into context.
        await AuditService(db).record(
            user_id=user_id,
            module=AuditModule.CHATBOT,
            action="message",
            reference_id=assistant_message_id,
            reference_type="chatbot_message",
            request_summary={
                "conversation_id": str(conversation.id),
                "include_modules": list(request.include_modules),
                "content_length": len(request.content),
            },
            response_summary={
                "tokens_used": tokens_used,
                "source_count": len(sources_payload),
                "source_modules": sorted({s["module"] for s in sources_payload}),
                "reasoning_steps": len(reasoning_trace),
            },
            explanation_summary=(
                {"reasoning_trace": reasoning_trace[:5]} if reasoning_trace else None
            ),
            risk_tier=None,  # chatbot has no fairness risk tier today
            model_version=_current_model_version(),
            latency_ms=0.0,
        )

        return ChatMessageResponse(
            conversation_id=conversation.id,
            message_id=assistant_message_id,
            content=content,
            created_at=datetime.now(timezone.utc),
            reasoning_trace=reasoning_trace,
            sources=[SourceReference(**_source_to_api(s)) for s in sources_payload],
            tokens_used=tokens_used,
        )

    # ── 2. WebSocket stream + persist ───────────────────────────────
    async def stream_response(
        self,
        conversation_id: UUID,
        user_id: UUID,
        message: str,
        context: dict[str, Any],
        db: AsyncSession,
    ) -> AsyncGenerator[dict, None]:
        """Yield WS chunks, then persist the user + final assistant turn.

        The WS path persists at the end so reconnecting clients can
        hydrate from `/chatbot/conversations/{id}` without missing turns.
        Streamed token chunks are reconstructed on the fly; only the
        final assistant `content` is durable.
        """
        include_modules = list(context.get("include_modules", []))

        conversation = await self._get_or_create_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            db=db,
            seed_title_from=message,
        )

        # Build the assistant turn — real-ML or mock based on flag.
        content, reasoning_trace, sources_payload, tokens_used, tool_chunks, token_chunks = (
            self._build_assistant_stream_chunks(
                content=message,
                include_modules=tuple(include_modules),
                user_id=user_id,
            )
        )

        # Stream first — the user sees tokens before we touch the DB.
        for chunk in tool_chunks:
            yield chunk
        for chunk in token_chunks:
            yield chunk

        # Persist both turns atomically, then emit `complete`.
        user_position = conversation.message_count
        db.add(
            ChatbotMessage(
                id=uuid4(),
                conversation_id=conversation.id,
                role=ChatbotMessageRole.USER,
                position=user_position,
                content=message,
                include_modules=include_modules,
                reasoning_trace=[],
                sources=[],
                tokens_used=0,
            )
        )
        assistant_message_id = uuid4()
        db.add(
            ChatbotMessage(
                id=assistant_message_id,
                conversation_id=conversation.id,
                role=ChatbotMessageRole.ASSISTANT,
                position=user_position + 1,
                content=content,
                include_modules=include_modules,
                reasoning_trace=reasoning_trace,
                sources=sources_payload,
                tokens_used=tokens_used,
            )
        )
        conversation.message_count = user_position + 2
        conversation.total_tokens_used += tokens_used
        conversation.modules_in_scope = sorted(
            set(conversation.modules_in_scope) | set(include_modules)
        )
        await db.flush()

        # Cross-module audit log (ADR-031). Recorded *before* commit so
        # the audit row + the message rows share a single transaction —
        # WS streaming persists atomically per turn. The action is
        # `stream_message` to distinguish the WS path from the REST
        # `message` action in dashboard aggregations.
        await AuditService(db).record(
            user_id=user_id,
            module=AuditModule.CHATBOT,
            action="stream_message",
            reference_id=assistant_message_id,
            reference_type="chatbot_message",
            request_summary={
                "conversation_id": str(conversation.id),
                "include_modules": include_modules,
                "content_length": len(message),
            },
            response_summary={
                "tokens_used": tokens_used,
                "source_count": len(sources_payload),
                "source_modules": sorted({s["module"] for s in sources_payload}),
                "reasoning_steps": len(reasoning_trace),
                "tool_calls": len(tool_chunks),
                "token_chunks": len(token_chunks),
            },
            explanation_summary=(
                {"reasoning_trace": reasoning_trace[:5]} if reasoning_trace else None
            ),
            risk_tier=None,
            model_version=_current_model_version(),
            latency_ms=0.0,
        )
        await db.commit()

        yield {
            "type": "complete",
            "conversation_id": str(conversation.id),
            "message_id": str(assistant_message_id),
            "content": content,
            "reasoning_trace": reasoning_trace,
            "sources": sources_payload,
        }

    # ── 3. list_conversations (reads from DB, paged) ────────────────
    async def list_conversations(
        self,
        user_id: UUID,
        db: AsyncSession,
        page: int,
        page_size: int,
    ) -> dict:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        total = await db.scalar(
            select(func.count())
            .select_from(ChatbotConversation)
            .where(ChatbotConversation.user_id == user_id)
        )
        rows = await db.execute(
            select(ChatbotConversation)
            .where(ChatbotConversation.user_id == user_id)
            .order_by(ChatbotConversation.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = [
            {
                "conversation_id": str(r.id),
                "title": r.title,
                "message_count": r.message_count,
                "total_tokens_used": r.total_tokens_used,
                "modules_in_scope": r.modules_in_scope,
                "model_version": r.model_version,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows.scalars()
        ]
        return {
            "items": items,
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
        }

    # ── 4. get_conversation (reads from DB) ─────────────────────────
    async def get_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> ConversationHistoryResponse:
        conv = await self._find_conversation(conversation_id, user_id, db)
        turns = [
            ChatTurn(
                role=m.role.value,
                content=m.content,
                created_at=m.created_at,
            )
            for m in conv.messages
        ]
        return ConversationHistoryResponse(
            conversation_id=conv.id,
            title=conv.title,
            turns=turns,
            created_at=conv.created_at,
        )

    # ── 4a. message detail (resolves to parent conversation) ───────
    async def get_message_detail(
        self,
        message_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> ChatbotMessageDetailResponse:
        """Resolve one assistant message to its parent conversation.

        Backs the audit-feed deep-link from TASK-034 — the audit log's
        `reference_id` for chatbot rows points at the assistant
        message; the dashboard needs `conversation_id` to navigate the
        user to the right conversation surface.

        Returns 404 if the message doesn't belong to the calling user.
        The cross-user isolation is enforced by joining through
        `ChatbotConversation.user_id`, mirroring the existing
        `_find_conversation` posture so a future tightening of one
        path tightens both.
        """
        stmt = (
            select(ChatbotMessage, ChatbotConversation)
            .join(
                ChatbotConversation,
                ChatbotConversation.id == ChatbotMessage.conversation_id,
            )
            .where(
                ChatbotMessage.id == message_id,
                ChatbotConversation.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        row = result.first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {message_id} not found",
            )
        message, conversation = row
        return ChatbotMessageDetailResponse(
            message_id=message.id,
            conversation_id=conversation.id,
            conversation_title=conversation.title,
            role=message.role.value,
            content=message.content,
            position=message.position,
            created_at=message.created_at,
        )

    # ── 5. executive report (persists its own row) ──────────────────
    async def generate_executive_report(
        self,
        request: ExecutiveReportRequest,
        user_id: UUID,
        db: AsyncSession,
    ) -> ExecutiveReportResponse:
        section_map = {
            "recruitment": (
                "Talent & Hiring",
                "Hiring pipeline is healthy with low fairness risk.",
            ),
            "pricing": (
                "Pricing Strategy",
                "Room to raise price on inelastic SKUs (+8% optimal).",
            ),
            "forecasting": (
                "Financial Outlook",
                "Base-case profit trends upward; bear case manageable.",
            ),
            "sustainability": (
                "ESG Risk",
                "Low regulatory risk; renewable-energy upside available.",
            ),
        }
        sections = [
            ReportSection(
                heading=section_map[m][0],
                body=section_map[m][1],
                highlights=[section_map[m][1]],
            )
            for m in request.include_modules
            if m in section_map
        ]
        response = ExecutiveReportResponse(
            report_id=uuid4(),
            title=request.title,
            generated_at=datetime.now(timezone.utc),
            sections=sections,
            strategic_recommendations=[
                "Raise price on inelastic SKUs by ~8%",
                "Hold headcount flat; revisit in Q+1",
                "Lock a renewable-energy contract to de-risk ESG",
            ],
            key_risks=[
                "Demand elasticity uncertainty on premium SKUs",
                "Supply-chain Scope 3 emissions exposure",
            ],
        )
        model_version = _current_model_version()
        db.add(
            ChatbotExecutiveReport(
                id=response.report_id,
                user_id=user_id,
                title=request.title,
                period_label=request.period_label,
                modules_included=list(request.include_modules),
                response_payload=response.model_dump(mode="json"),
                model_version=model_version,
            )
        )
        await db.flush()

        # Cross-module audit log (ADR-031). The executive report
        # synthesises signals across multiple modules — capture which
        # ones were folded in so Phase-4 dashboards can show this as a
        # cross-module decision.
        await AuditService(db).record(
            user_id=user_id,
            module=AuditModule.CHATBOT,
            action="executive_report",
            reference_id=response.report_id,
            reference_type="chatbot_executive_report",
            request_summary={
                "title": request.title,
                "period_label": request.period_label,
                "include_modules": list(request.include_modules),
            },
            response_summary={
                "section_count": len(response.sections),
                "recommendation_count": len(response.strategic_recommendations),
                "risk_count": len(response.key_risks),
                "modules_synthesised": [
                    s.heading for s in response.sections
                ],
            },
            explanation_summary=None,
            risk_tier=None,
            model_version=model_version,
            latency_ms=0.0,
        )
        return response

    # ── assistant-turn builders (mock / real-ML dispatch) ─────────
    def _build_assistant_turn(
        self,
        *,
        content: str,
        include_modules: tuple[str, ...],
        user_id: UUID,
    ) -> tuple[str, list[str], list[dict], int]:
        """Return `(content, reasoning_trace, sources_payload, tokens_used)`
        for the assistant turn.

        Mirrors ADR-024: when `CHATBOT_USE_REAL_ML` is set, delegate to
        `ChatbotInferenceClient.respond` and translate the result;
        otherwise use the deterministic mock.
        """
        if settings.CHATBOT_USE_REAL_ML:
            from src.services.chatbot.inference import get_inference_client
            from src.services.chatbot.ml_translation import (
                ml_response_to_sources_payload,
            )

            response = get_inference_client().respond(
                content=content,
                include_modules=include_modules,
                user_id=user_id,
            )
            return (
                response.content,
                list(response.reasoning_trace),
                ml_response_to_sources_payload(response),
                int(response.tokens_used),
            )

        # ── Mock path (unchanged) ──────────────────────────────────
        sources_payload = [
            {
                "module": m,
                "reference_id": str(uuid4()),
                "summary": f"Latest {m} analysis referenced.",
            }
            for m in include_modules
        ]
        return _CANNED_ANSWER, list(_REASONING_TRACE), sources_payload, _TOKENS_USED

    def _build_assistant_stream_chunks(
        self,
        *,
        content: str,
        include_modules: tuple[str, ...],
        user_id: UUID,
    ) -> tuple[str, list[str], list[dict], int, list[dict], list[dict]]:
        """Return the streaming-path variant: same four persistence
        fields plus pre-built `tool_chunks` + `token_chunks` lists.

        The WS handler yields the tool + token chunks before persisting,
        then emits the `complete` event after the DB commit — so a
        reconnecting client hydrates from `/conversations/{id}` without
        missing turns.
        """
        if settings.CHATBOT_USE_REAL_ML:
            from src.services.chatbot.inference import get_inference_client
            from src.services.chatbot.ml_translation import (
                chunk_content_for_streaming,
                ml_response_to_sources_payload,
            )

            response = get_inference_client().respond(
                content=content,
                include_modules=include_modules,
                user_id=user_id,
            )
            tool_chunks: list[dict] = [
                {"type": "tool_call", "tool": tc.name, "status": tc.status}
                for tc in response.tool_calls
            ]
            token_chunks: list[dict] = [
                {"type": "token", "content": tok, "agent_step": "reasoning"}
                for tok in chunk_content_for_streaming(response.content)
            ]
            return (
                response.content,
                list(response.reasoning_trace),
                ml_response_to_sources_payload(response),
                int(response.tokens_used),
                tool_chunks,
                token_chunks,
            )

        # ── Mock path (unchanged streaming shape) ──────────────────
        sources_payload = [
            {
                "module": m,
                "reference_id": str(uuid4()),
                "summary": f"Latest {m} analysis referenced.",
            }
            for m in include_modules
        ]
        tool_chunks = [
            {"type": "tool_call", "tool": "get_cross_module_context", "status": "executing"}
        ]
        token_chunks = [
            {"type": "token", "content": token + " ", "agent_step": "reasoning"}
            for token in _CANNED_ANSWER.split(" ")
        ]
        return (
            _CANNED_ANSWER,
            list(_REASONING_TRACE),
            sources_payload,
            _TOKENS_USED,
            tool_chunks,
            token_chunks,
        )

    # ── 6. executive report detail (reads from DB) ──────────────────
    async def get_executive_report_detail(
        self,
        report_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> ChatbotExecutiveReportDetailResponse:
        """Reconstruct one persisted executive report row. Backs the
        audit-feed deep-link from TASK-034
        (`reference_type='chatbot_executive_report'`). 404 if the
        report doesn't belong to the calling user."""
        result = await db.execute(
            select(ChatbotExecutiveReport).where(
                ChatbotExecutiveReport.id == report_id,
                ChatbotExecutiveReport.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Executive report {report_id} not found",
            )
        return ChatbotExecutiveReportDetailResponse(
            report_id=row.id,
            title=row.title,
            period_label=row.period_label,
            modules_included=list(row.modules_included or []),
            response_payload=row.response_payload or {},
            model_version=row.model_version,
            created_at=row.created_at,
        )

    # ── internals ──────────────────────────────────────────────────
    async def _get_or_create_conversation(
        self,
        *,
        conversation_id: UUID | None,
        user_id: UUID,
        db: AsyncSession,
        seed_title_from: str,
    ) -> ChatbotConversation:
        if conversation_id is not None:
            return await self._find_conversation(conversation_id, user_id, db)

        conv = ChatbotConversation(
            id=uuid4(),
            user_id=user_id,
            title=_derive_title(seed_title_from),
            modules_in_scope=[],
            message_count=0,
            total_tokens_used=0,
            model_version=_current_model_version(),
        )
        db.add(conv)
        await db.flush()
        return conv

    async def _find_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> ChatbotConversation:
        result = await db.execute(
            select(ChatbotConversation)
            .options(selectinload(ChatbotConversation.messages))
            .where(
                ChatbotConversation.id == conversation_id,
                ChatbotConversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found",
            )
        return conv
