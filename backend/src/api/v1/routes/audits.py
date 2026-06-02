"""
BizVision AI — Cross-Module Audit Log Router

Read-only API surface. The audit log is **append-only** and the only
writes happen from inside the module services via
`AuditService.record(...)` — there is no `POST /audits` endpoint by
design (ADR-031).

Endpoints:
- GET  /audits             — Paged list of the caller's audit rows
                             (filterable by module + risk_tier)
- GET  /audits/summary     — Aggregated dashboard view
- GET  /audits/{audit_id}  — One row by id (caller-scoped)
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.audit import (
    AuditLogPage,
    AuditLogRead,
    AuditModuleName,
    AuditSummary,
    FairnessAggregate,
)
from src.core.database import get_db
from src.core.deps import get_current_user
from src.models.audit import AuditModule
from src.models.user import User
from src.services.audit.audit_service import AuditService

router = APIRouter()


@router.get(
    "",
    response_model=AuditLogPage,
    status_code=status.HTTP_200_OK,
    summary="List ML decision audit logs (paged)",
    description=(
        "Returns the caller's ML-decision audit trail across all 5 "
        "modules, newest first. Optionally filter by `module` "
        "(recruitment | pricing | forecasting | sustainability | "
        "chatbot) and/or `risk_tier` (low | medium | high | critical)."
    ),
)
async def list_audit_logs(
    module: Annotated[AuditModuleName | None, Query()] = None,
    risk_tier: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditLogPage:
    service = AuditService(db)
    page_data = await service.list(
        user_id=current_user.id,
        module=AuditModule(module.value) if module is not None else None,
        risk_tier=risk_tier,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )
    return AuditLogPage(
        items=[AuditLogRead.model_validate(r) for r in page_data["items"]],
        total=page_data["total"],
        page=page_data["page"],
        page_size=page_data["page_size"],
    )


@router.get(
    "/summary",
    response_model=AuditSummary,
    status_code=status.HTTP_200_OK,
    summary="Aggregated ML-decision summary for the dashboard",
    description=(
        "Returns total decision count, per-module decision histogram, "
        "and risk-tier histogram for the caller. Optionally restrict to "
        "decisions made after `since` (ISO-8601). Powers the Phase-4 "
        "fairness/XAI dashboards."
    ),
)
async def audit_summary(
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditSummary:
    service = AuditService(db)
    data = await service.summary(
        user_id=current_user.id, since=since, until=until
    )
    return AuditSummary.model_validate(data)


@router.get(
    "/fairness",
    response_model=FairnessAggregate,
    status_code=status.HTTP_200_OK,
    summary="Per-protected-attribute fairness aggregation",
    description=(
        "Aggregates audit rows whose `fairness_summary.attributes[*]` "
        "carry a per-attribute pass/fail breakdown (recruitment today) "
        "and returns one bucket per attribute with decision_count + "
        "pass_count + fail_count + pass_rate. Powers the Phase-4 "
        "Decision Feed's per-attribute fairness card. Optionally "
        "restrict to decisions made after `since` (ISO-8601)."
    ),
)
async def audit_fairness(
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FairnessAggregate:
    service = AuditService(db)
    data = await service.fairness_aggregate(
        user_id=current_user.id, since=since, until=until
    )
    return FairnessAggregate.model_validate(data)


@router.get(
    "/{audit_id}",
    response_model=AuditLogRead,
    status_code=status.HTTP_200_OK,
    summary="Get a single audit log entry",
    description=(
        "Returns one audit row by id. Returns 404 if the row does not "
        "belong to the calling user."
    ),
)
async def get_audit_log(
    audit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditLogRead:
    service = AuditService(db)
    row = await service.get(audit_id, current_user.id)
    return AuditLogRead.model_validate(row)
