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
        raw_credentials = cloud_account.credentials or {}
        credentials = decrypt_credentials(raw_credentials)
        mode = str(credentials.get("mode", "live"))

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
            return {
                "account_id": cloud_account.id,
                "error": str(exc),
                "records_created": 0,
                "records_updated": 0,
            }

        # Calculate date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)
        
        parsed_records = await provider.get_cost_data(
            start_date=start_date,
            end_date=end_date,
            granularity="DAILY",
        )
        
        if not parsed_records:
            SYNC_DURATION.labels(
                provider=cloud_account.provider,
                mode=getattr(provider, "mode", mode),
                status="empty",
            ).observe(time.perf_counter() - started_at)
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
        
        cloud_account.last_sync_at = datetime.now(UTC)
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
            "total_records": record_count or 0,
            "is_active": account.is_active,
        }
