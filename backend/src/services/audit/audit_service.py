"""
BizVision AI — Cross-Module Audit Log Service

Append-only persistence + read-side aggregation over `audit_logs`. The
five module services call `AuditService.record(...)` after they've
written their owning row; this service handles the index entry + the
dashboard queries.

Read paths (all scoped to the calling user):
  • `list(user_id, module=None, risk_tier=None, page, page_size)`
  • `get(audit_id, user_id)`
  • `summary(user_id, since=None)` — counts by module + risk tier + most
    recent decision timestamp; the dashboard hot path.

The recording path is *non-raising* — if the audit insert fails for any
reason (DB blip, validation), the caller does **not** fail with it.
Phase-4 surfaces missing audit rows as a banner; module decisions
should never roll back because an audit row didn't write. This is the
standard "fire-and-forget telemetry" posture; ADR-031 captures it.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import AuditLog, AuditModule

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 1. record (non-raising — see module docstring) ─────────────
    async def record(
        self,
        *,
        user_id: UUID,
        module: AuditModule | str,
        action: str,
        model_version: str,
        latency_ms: float,
        reference_id: UUID | None = None,
        reference_type: str | None = None,
        request_summary: dict[str, Any] | None = None,
        response_summary: dict[str, Any] | None = None,
        explanation_summary: dict[str, Any] | None = None,
        fairness_summary: dict[str, Any] | None = None,
        risk_tier: str | None = None,
    ) -> AuditLog | None:
        """Append one audit row. Returns the row on success, None on failure.

        Failures are logged but never raised — see module docstring for
        the rationale.
        """
        try:
            mod = (
                module
                if isinstance(module, AuditModule)
                else AuditModule(module)
            )
            row = AuditLog(
                user_id=user_id,
                module=mod,
                action=action,
                reference_id=reference_id,
                reference_type=reference_type,
                request_summary=request_summary or {},
                response_summary=response_summary or {},
                explanation_summary=explanation_summary,
                fairness_summary=fairness_summary,
                risk_tier=risk_tier,
                model_version=model_version,
                latency_ms=float(latency_ms),
            )
            self.db.add(row)
            await self.db.flush()
            return row
        except Exception:  # noqa: BLE001 — fire-and-forget by design
            logger.exception(
                "audit_log_record_failed",
                extra={"user_id": str(user_id), "module": str(module), "action": action},
            )
            return None

    # ── 2. list (paged + filterable) ────────────────────────────────
    async def list(
        self,
        *,
        user_id: UUID,
        module: AuditModule | None = None,
        risk_tier: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        filters = [AuditLog.user_id == user_id]
        if module is not None:
            filters.append(AuditLog.module == module)
        if risk_tier is not None:
            filters.append(AuditLog.risk_tier == risk_tier)
        # Date-range filter (TASK-038).
        if since is not None:
            filters.append(AuditLog.created_at >= since)
        if until is not None:
            filters.append(AuditLog.created_at <= until)

        total = await self.db.scalar(
            select(func.count()).select_from(AuditLog).where(*filters)
        )
        rows = await self.db.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(rows.scalars())
        return {
            "items": items,
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
        }

    # ── 3. get one ──────────────────────────────────────────────────
    async def get(self, audit_id: UUID, user_id: UUID) -> AuditLog:
        result = await self.db.execute(
            select(AuditLog).where(
                AuditLog.id == audit_id,
                AuditLog.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audit log {audit_id} not found",
            )
        return row

    # ── 4. fairness aggregate (per-protected-attribute pass rates) ──
    async def fairness_aggregate(
        self,
        user_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """Per-attribute pass-rate aggregation across audit rows whose
        `fairness_summary.attributes[*]` carry a structured breakdown.

        Performed in Python rather than as a single JSONB GROUP BY
        because:
          • the JSONB shape uses an array of objects (one per
            attribute), so SQL would need `jsonb_array_elements` +
            `LATERAL` joins that are dialect-specific;
          • the per-attribute counts are typically O(#decisions) ≤
            single-digit thousands per user — well within Python's
            comfort zone;
          • keeping the aggregation in service code lets the
            `fairness_summary` shape evolve without coupling it to a
            stored SQL function.

        Audit rows whose `fairness_summary` is `None` or missing the
        `attributes` field are simply skipped (they don't contribute
        to the denominator either — only rows that *can* contribute
        to the rate are counted).
        """
        filters = [
            AuditLog.user_id == user_id,
            AuditLog.fairness_summary.is_not(None),
        ]
        # Date-range filter (TASK-038 extends the `since` from TASK-031).
        if since is not None:
            filters.append(AuditLog.created_at >= since)
        if until is not None:
            filters.append(AuditLog.created_at <= until)

        rows = await self.db.execute(
            select(AuditLog.fairness_summary).where(*filters)
        )

        per_attr: dict[str, dict[str, int]] = {}
        # Cell-level aggregation: keyed by (attribute, metric_name) for the
        # intersectional fairness heatmap (TASK-043, FE-017). Tracks
        # decision/pass counts AND the running mean of the metric value
        # so the UI can render both a pass-rate cell and an avg-value
        # cell against a constant threshold per metric.
        per_cell: dict[tuple[str, str], dict[str, Any]] = {}
        audited = 0
        for (payload,) in rows:
            if not isinstance(payload, dict):
                continue
            attributes = payload.get("attributes")
            if not isinstance(attributes, list) or not attributes:
                continue
            audited += 1
            for entry in attributes:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                if not isinstance(name, str) or not name:
                    continue
                bucket = per_attr.setdefault(
                    name, {"decision_count": 0, "pass_count": 0, "fail_count": 0}
                )
                bucket["decision_count"] += 1
                if entry.get("passed") is True:
                    bucket["pass_count"] += 1
                elif entry.get("passed") is False:
                    bucket["fail_count"] += 1

                metrics = entry.get("metrics")
                if not isinstance(metrics, list):
                    continue
                for m in metrics:
                    if not isinstance(m, dict):
                        continue
                    metric_name = m.get("metric_name")
                    if not isinstance(metric_name, str) or not metric_name:
                        continue
                    key = (name, metric_name)
                    cell = per_cell.setdefault(
                        key,
                        {
                            "decision_count": 0,
                            "pass_count": 0,
                            "value_sum": 0.0,
                            "value_count": 0,
                            "threshold": None,
                        },
                    )
                    cell["decision_count"] += 1
                    if m.get("passed") is True:
                        cell["pass_count"] += 1
                    raw_val = m.get("value")
                    if isinstance(raw_val, (int, float)):
                        cell["value_sum"] += float(raw_val)
                        cell["value_count"] += 1
                    raw_thresh = m.get("threshold")
                    if cell["threshold"] is None and isinstance(raw_thresh, (int, float)):
                        cell["threshold"] = float(raw_thresh)

        by_attribute = [
            {
                "attribute": name,
                "decision_count": b["decision_count"],
                "pass_count": b["pass_count"],
                "fail_count": b["fail_count"],
                "pass_rate": (
                    b["pass_count"] / b["decision_count"]
                    if b["decision_count"] > 0
                    else 0.0
                ),
            }
            for name, b in sorted(per_attr.items())
        ]

        by_attribute_metric = [
            {
                "attribute": attr,
                "metric_name": metric,
                "decision_count": c["decision_count"],
                "pass_count": c["pass_count"],
                "pass_rate": (
                    c["pass_count"] / c["decision_count"]
                    if c["decision_count"] > 0
                    else 0.0
                ),
                "avg_value": (
                    c["value_sum"] / c["value_count"]
                    if c["value_count"] > 0
                    else None
                ),
                "threshold": c["threshold"],
            }
            for (attr, metric), c in sorted(per_cell.items())
        ]

        return {
            "user_id": user_id,
            "window_start": since,
            "total_audited_decisions": audited,
            "by_attribute": by_attribute,
            "by_attribute_metric": by_attribute_metric,
        }

    # ── 5. summary (dashboard hot path) ─────────────────────────────
    async def summary(
        self,
        user_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        filters = [AuditLog.user_id == user_id]
        # Date-range filter (TASK-038 extends the `since` from TASK-028).
        if since is not None:
            filters.append(AuditLog.created_at >= since)
        if until is not None:
            filters.append(AuditLog.created_at <= until)

        total = await self.db.scalar(
            select(func.count()).select_from(AuditLog).where(*filters)
        )
        latest = await self.db.scalar(
            select(func.max(AuditLog.created_at)).where(*filters)
        )

        by_module_rows = await self.db.execute(
            select(AuditLog.module, func.count())
            .where(*filters)
            .group_by(AuditLog.module)
        )
        by_module = [
            {"module": m.value, "count": int(c)} for m, c in by_module_rows
        ]

        by_risk_rows = await self.db.execute(
            select(AuditLog.risk_tier, func.count())
            .where(*filters, AuditLog.risk_tier.is_not(None))
            .group_by(AuditLog.risk_tier)
        )
        by_risk = [{"risk_tier": r, "count": int(c)} for r, c in by_risk_rows]

        return {
            "user_id": user_id,
            "window_start": since,
            "total_decisions": int(total or 0),
            "by_module": by_module,
            "by_risk_tier": by_risk,
            "latest_decision_at": latest,
        }
