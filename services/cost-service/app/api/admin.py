"""
CloudPulse AI - Cost Service
Admin endpoints for system observability.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import AuditLog, User

router = APIRouter()


@router.get("/audit-logs")
async def get_audit_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    action: str | None = None,
):
    """
    Get system audit logs.
    Only accessible by admins.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    query = select(AuditLog).where(
        AuditLog.organization_id == current_user.organization_id
    )
    
    if action:
        query = query.where(AuditLog.action == action)
        
    # Sort by newest
    query = query.order_by(desc(AuditLog.created_at))
    
    # Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "action": log.action,
            "user_id": log.user_id,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at,
        }
        for log in logs
    ]
