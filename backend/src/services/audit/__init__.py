"""Cross-module audit log service (ADR-031)."""

from src.services.audit.audit_service import AuditService

__all__ = ["AuditService"]
