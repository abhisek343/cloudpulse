"""
CloudPulse AI - Cost Service
Notification channel CRUD API endpoints.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import NotificationChannel
from app.schemas import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationTestResult,
)
from app.services.notification_service import get_notification_service

router = APIRouter()


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def list_channels(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationChannelResponse]:
    """List all notification channels for the current organization."""
    org_id = user["organization_id"]
    result = await db.execute(
        select(NotificationChannel)
        .where(NotificationChannel.organization_id == org_id)
        .order_by(NotificationChannel.created_at.desc())
    )
    channels = result.scalars().all()
    return [NotificationChannelResponse.model_validate(ch) for ch in channels]


@router.post("/channels", response_model=NotificationChannelResponse, status_code=201)
async def create_channel(
    body: NotificationChannelCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationChannelResponse:
    """Create a new notification channel."""
    if "webhook_url" not in body.config:
        raise HTTPException(status_code=422, detail="config must include webhook_url")

    channel = NotificationChannel(
        organization_id=user["organization_id"],
        channel_type=body.channel_type,
        name=body.name,
        config=body.config,
        events=body.events,
        is_active=body.is_active,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return NotificationChannelResponse.model_validate(channel)


@router.patch("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_channel(
    channel_id: str,
    body: NotificationChannelUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationChannelResponse:
    """Update a notification channel."""
    channel = await _get_channel_or_404(db, channel_id, user["organization_id"])

    update_data = body.model_dump(exclude_unset=True)
    if "config" in update_data and "webhook_url" not in update_data["config"]:
        raise HTTPException(status_code=422, detail="config must include webhook_url")

    for key, value in update_data.items():
        setattr(channel, key, value)

    await db.commit()
    await db.refresh(channel)
    return NotificationChannelResponse.model_validate(channel)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a notification channel."""
    channel = await _get_channel_or_404(db, channel_id, user["organization_id"])
    await db.delete(channel)
    await db.commit()


@router.post("/channels/{channel_id}/test", response_model=NotificationTestResult)
async def test_channel(
    channel_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationTestResult:
    """Send a test notification to verify the channel works."""
    channel = await _get_channel_or_404(db, channel_id, user["organization_id"])
    svc = get_notification_service()
    ok = await svc.send_test(channel.channel_type, channel.config)
    return NotificationTestResult(
        success=ok,
        message="Test notification sent successfully." if ok else "Failed to deliver test notification.",
    )


async def _get_channel_or_404(
    db: AsyncSession, channel_id: str, org_id: str,
) -> NotificationChannel:
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.organization_id == org_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    return channel
