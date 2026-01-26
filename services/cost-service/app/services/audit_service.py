"""
CloudPulse AI - Audit Service
Helper for creating audit logs.
"""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog


class AuditService:
    @staticmethod
    async def log(
        db: AsyncSession,
        organization_id: str,
        user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Create an audit log entry."""
        log_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(log_entry)
        # We don't commit here to allow transaction grouping, 
        # but in many cases we might want to flush if critical.
        # For now, rely on caller to commit.
