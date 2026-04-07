"""
CloudPulse AI - Cost Service
Cost data synchronization service.
"""
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RedisCache
from app.core.circuit_breaker import CircuitOpenError, get_breaker
from app.core.logging import sanitize_error
from app.core.observability import SYNC_DURATION
from app.core.security import decrypt_credentials
from app.models import CloudAccount, CostRecord
from app.services.audit_service import AuditService
from app.services.providers.factory import ProviderFactory


class CostSyncService:
    """Service for synchronizing cost data from cloud providers."""
    
    def __init__(
        self,
        db: AsyncSession,
        cache: RedisCache,
    ) -> None:
        self.db = db
        self.cache = cache
    
    async def sync_account_costs(
        self,
        cloud_account: CloudAccount,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Sync cost data from AWS for a cloud account.
        
        Args:
            cloud_account: The cloud account to sync
            days: Number of days to sync (default: 30)
            
        Returns:
            Sync result with record counts
        """
        started_at = time.perf_counter()
        sync_started_at = datetime.now(UTC)
        raw_credentials = cloud_account.credentials or {}
        credentials = decrypt_credentials(raw_credentials)
        mode = str(credentials.get("mode", "live"))

        cloud_account.last_sync_status = "syncing"
        cloud_account.last_sync_started_at = sync_started_at
        cloud_account.last_sync_completed_at = None
        cloud_account.last_sync_error = None
        cloud_account.last_sync_records_imported = None
        await self.db.flush()

        try:
            provider = ProviderFactory.get_provider(
                cloud_account.provider,
                credentials
            )
        except ValueError as exc:
            SYNC_DURATION.labels(
                provider=cloud_account.provider,
                mode=mode,
                status="rejected",
            ).observe(time.perf_counter() - started_at)
            cloud_account.last_sync_status = "error"
            cloud_account.last_sync_error = sanitize_error(exc)
            cloud_account.last_sync_completed_at = datetime.now(UTC)
            await self.db.flush()
            return {
                "account_id": cloud_account.id,
                "error": sanitize_error(exc),
                "records_created": 0,
                "records_updated": 0,
            }

        # Calculate date range
        end_date = datetime.now(UTC)
        start_date = (end_date - timedelta(days=days - 1)).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        breaker = get_breaker(cloud_account.provider)
        try:
            breaker.ensure_closed()
        except CircuitOpenError as exc:
            cloud_account.last_sync_status = "error"
            cloud_account.last_sync_error = sanitize_error(exc)
            cloud_account.last_sync_completed_at = datetime.now(UTC)
            await self.db.flush()
            return {
                "account_id": cloud_account.id,
                "error": sanitize_error(exc),
                "records_created": 0,
                "records_updated": 0,
            }

        try:
            parsed_records = await provider.get_cost_data(
                start_date=start_date,
                end_date=end_date,
                granularity="DAILY",
            )
            breaker.record_success()
        except Exception as exc:
            breaker.record_failure(exc)
            metric_mode = getattr(provider, "mode", mode)
            SYNC_DURATION.labels(
                provider=cloud_account.provider,
                mode=metric_mode,
                status="error",
            ).observe(time.perf_counter() - started_at)
            cloud_account.last_sync_status = "error"
            cloud_account.last_sync_error = sanitize_error(exc)
            cloud_account.last_sync_completed_at = datetime.now(UTC)
            cloud_account.last_sync_records_imported = 0
            await self.db.flush()
            return {
                "account_id": cloud_account.id,
                "error": sanitize_error(exc),
                "records_created": 0,
                "records_updated": 0,
            }
        
        if not parsed_records:
            SYNC_DURATION.labels(
                provider=cloud_account.provider,
                mode=getattr(provider, "mode", mode),
                status="empty",
            ).observe(time.perf_counter() - started_at)
            finished_at = datetime.now(UTC)
            cloud_account.last_sync_at = finished_at
            cloud_account.last_sync_status = "ready"
            cloud_account.last_sync_completed_at = finished_at
            cloud_account.last_sync_error = None
            cloud_account.last_sync_records_imported = 0
            await self.db.flush()
            return {
                "account_id": cloud_account.id,
                "records_created": 0,
                "records_updated": 0,
                "total_records": 0,
                "sync_period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
            }

        # Atomic delete + insert within an explicit transaction
        async with self.db.begin_nested():
            await self.db.execute(
                delete(CostRecord).where(
                    CostRecord.cloud_account_id == cloud_account.id,
                    CostRecord.date >= start_date,
                    CostRecord.date <= end_date,
                    CostRecord.granularity == "daily",
                )
            )

            records_to_insert = [
                CostRecord(
                    cloud_account_id=cloud_account.id,
                    date=record_data["date"],
                    granularity="daily",
                    service=record_data["service"],
                    region=record_data.get("region"),
                    resource_id=record_data.get("resource_id"),
                    amount=record_data["amount"],
                    currency=record_data.get("currency", "USD"),
                    tags=record_data.get("tags"),
                    record_metadata=record_data.get("record_metadata"),
                )
                for record_data in parsed_records
            ]

            self.db.add_all(records_to_insert)
        
        finished_at = datetime.now(UTC)
        cloud_account.last_sync_at = finished_at
        cloud_account.last_sync_status = "ready"
        cloud_account.last_sync_completed_at = finished_at
        cloud_account.last_sync_error = None
        cloud_account.last_sync_records_imported = len(records_to_insert)
        await self.db.flush()
        
        await self.cache.flush_pattern(
            self.cache.generate_key("summary", cloud_account.organization_id, "*")
        )
        await self.cache.flush_pattern(
            self.cache.generate_key("trend", cloud_account.organization_id, "*")
        )
        
        await AuditService.log(
            self.db,
            organization_id=cloud_account.organization_id,
            user_id=None,
            action="SYNC",
            resource_type="cloud_account",
            resource_id=cloud_account.id,
            details={
                "provider": cloud_account.provider, 
                "mode": getattr(provider, "mode", credentials.get("mode", "live")),
                "records_processed": len(records_to_insert),
                "period": f"{start_date.date()} to {end_date.date()}",
            }
        )
        await self.db.flush()

        metric_mode = getattr(provider, "mode", mode)
        SYNC_DURATION.labels(
            provider=cloud_account.provider,
            mode=metric_mode,
            status="success",
        ).observe(time.perf_counter() - started_at)

        return {
            "account_id": cloud_account.id,
            "records_processed": len(records_to_insert),
            "sync_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
        }
    
    async def sync_all_accounts(
        self,
        organization_id: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Sync costs for all active cloud accounts in an organization."""
        # Get all active accounts
        result = await self.db.execute(
            select(CloudAccount).where(
                CloudAccount.organization_id == organization_id,
                CloudAccount.is_active,
            )
        )
        accounts = result.scalars().all()
        
        results = []
        for account in accounts:
            if account.provider in ProviderFactory.get_supported_providers():
                sync_result = await self.sync_account_costs(account, days)
                results.append(sync_result)
        
        return results
    
    async def get_sync_status(
        self,
        cloud_account_id: str,
    ) -> dict[str, Any]:
        """Get the sync status for a cloud account."""
        result = await self.db.execute(
            select(CloudAccount).where(CloudAccount.id == cloud_account_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            return {"error": "Account not found"}
        
        # Count records
        from sqlalchemy import func
        record_count = await self.db.scalar(
            select(func.count(CostRecord.id)).where(
                CostRecord.cloud_account_id == cloud_account_id
            )
        )
        
        return {
            "account_id": cloud_account_id,
            "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
            "last_sync_status": account.last_sync_status,
            "last_sync_error": account.last_sync_error,
            "last_sync_started_at": (
                account.last_sync_started_at.isoformat() if account.last_sync_started_at else None
            ),
            "last_sync_completed_at": (
                account.last_sync_completed_at.isoformat() if account.last_sync_completed_at else None
            ),
            "last_sync_records_imported": account.last_sync_records_imported,
            "total_records": record_count or 0,
            "is_active": account.is_active,
        }
