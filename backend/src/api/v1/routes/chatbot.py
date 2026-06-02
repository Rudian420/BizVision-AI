"""
BizVision AI — Financial Advisory AI Chatbot Router

This is NOT a normal chatbot. It's an Executive AI Advisor with:
- Multi-agent LangGraph orchestration
- RAG over business knowledge + module outputs
- Tool use (calls other module APIs)
- Conversational memory
- Streaming responses via WebSocket
- Structured executive report generation
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.chatbot import (
    ChatbotExecutiveReportDetailResponse,
    ChatbotMessageDetailResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryResponse,
    ExecutiveReportRequest,
    ExecutiveReportResponse,
)
from src.core.database import AsyncSessionLocal, get_db
from src.core.deps import get_current_user
from src.models.user import User
from src.services.chatbot.chatbot_service import ChatbotService
from src.services.chatbot.ws_manager import WebSocketManager

router = APIRouter()
ws_manager = WebSocketManager()


@router.websocket("/ws/{conversation_id}")
async def chatbot_websocket(
    websocket: WebSocket,
    conversation_id: UUID,
    token: str,  # JWT passed as query param for WS auth
):
    """
    Primary chatbot interaction via WebSocket for real-time streaming.

    The LangGraph agent streams tokens as they're generated, creating
    a cinematic typewriter effect in the frontend.

    Message format (client → server):
    {
        "type": "message",
        "content": "What pricing strategy should I use for Q3?",
        "context": {"include_modules": ["pricing", "forecasting"]}
    }

    Message format (server → client):
    {
        "type": "token",        # Streaming token
        "content": "Based on...",
        "agent_step": "reasoning"
    }
    {
        "type": "tool_call",    # Agent using a tool
        "tool": "get_pricing_recommendation",
        "status": "executing"
    }
    {
        "type": "complete",     # Full response ready
        "content": "...",
        "reasoning_trace": [...],
        "sources": [...]
    }
    """
    user_id = await ws_manager.connect(websocket, conversation_id, token)
    if user_id is None:
        return  # socket already closed with policy-violation

    service = ChatbotService()

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") != "message":
                continue

            # A fresh DB session per turn — the WS connection outlives
            # any single request, so we cannot reuse the request-scoped
            # `get_db` dependency here.
            async with AsyncSessionLocal() as db:
                async for chunk in service.stream_response(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message=data["content"],
                    context=data.get("context", {}),
                    db=db,
                ):
                    await websocket.send_json(chunk)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, conversation_id)


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send message to Financial Advisory AI (REST fallback)",
    description="""
    REST endpoint for single-turn chatbot interaction.
    For production use, prefer the WebSocket endpoint for streaming.

    The AI advisor can:
    - Answer financial/business questions
    - Synthesize insights from all 5 AI modules
    - Generate executive reports and action plans
    - Reference historical analyses from the user's account
    - Use tools to fetch live data from module APIs
    """,
)
async def send_message(
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatbotService()
    return await service.send_message(
        request=request,
        user_id=current_user.id,
        db=db,
    )


@router.get(
    "/conversations",
    summary="List conversation history",
)
async def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatbotService()
    return await service.list_conversations(
        user_id=current_user.id,
        db=db,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationHistoryResponse,
    summary="Get conversation history",
)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatbotService()
    return await service.get_conversation(
        conversation_id=conversation_id,
        user_id=current_user.id,
        db=db,
    )


@router.get(
    "/messages/{message_id}",
    response_model=ChatbotMessageDetailResponse,
    summary="Resolve a chatbot message to its parent conversation",
    description=(
        "Returns one assistant message + its parent conversation_id + "
        "conversation_title + position. Backs the audit-feed deep-link "
        "from TASK-034 — the dashboard uses `conversation_id` to "
        "navigate the user to the chatbot workspace with the right "
        "conversation loaded. 404 if the message does not belong to "
        "the calling user."
    ),
)
async def get_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatbotService()
    return await service.get_message_detail(
        message_id=message_id,
        user_id=current_user.id,
        db=db,
    )


@router.get(
    "/executive-reports/{report_id}",
    response_model=ChatbotExecutiveReportDetailResponse,
    summary="Get a persisted executive report by id",
    description=(
        "Returns the persisted report row with its full response_payload "
        "(sections + recommendations + risks). Backs the audit-feed "
        "deep-link from TASK-034. 404 if the report does not belong to "
        "the calling user."
    ),
)
async def get_executive_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatbotService()
    return await service.get_executive_report_detail(
        report_id=report_id,
        user_id=current_user.id,
        db=db,
    )


@router.post(
    "/executive-report",
    response_model=ExecutiveReportResponse,
    summary="Generate comprehensive AI executive report",
    description="""
    Generates a structured executive intelligence report by orchestrating
    all 5 AI modules and synthesizing their outputs into a unified strategic analysis.

    Report sections:
    - Business Intelligence Summary
    - Talent & Hiring Insights (Recruitment module)
    - Pricing Strategy Recommendations (Pricing module)
    - Financial Outlook & Scenarios (Forecasting module)
    - ESG Risk & Opportunity Assessment (Sustainability module)
    - AI-Generated Strategic Recommendations
    - Key Risks & Mitigation Strategies
    """,
)
async def generate_executive_report(
    request: ExecutiveReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatbotService()
    return await service.generate_executive_report(
        request=request,
        user_id=current_user.id,
        db=db,
    )
