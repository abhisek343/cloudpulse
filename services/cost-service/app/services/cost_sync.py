"""
CloudPulse AI - Cost Service
Cost data synchronization service.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RedisCache
from app.models import CloudAccount, CostRecord
from app.services.providers.factory import ProviderFactory
from app.services.audit_service import AuditService


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
        # Get AWS credentials from cloud account
        credentials = cloud_account.credentials or {}
        
        # Get generic provider
        try:
            provider = ProviderFactory.get_provider(
                cloud_account.provider,
                credentials
            )
        except ValueError:
            # Skip unsupported providers
            return {
                "account_id": cloud_account.id,
                "error": f"Unsupported provider: {cloud_account.provider}",
                "records_created": 0,
                "records_updated": 0,
            }

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Fetch normalized cost data from provider
        # get_cost_data returns List[Dict] with standardized keys (date, service, amount, etc.)
        parsed_records = await provider.get_cost_data(
            start_date=start_date,
            end_date=end_date,
            granularity="DAILY",
        )
        
        if not parsed_records:
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

        # Prepare values for bulk upsert
        values_to_insert = []
        for record_data in parsed_records:
            values_to_insert.append({
                "cloud_account_id": cloud_account.id,
                "date": record_data["date"],
                "granularity": "daily",
                "service": record_data["service"],
                "amount": record_data["amount"],
                "currency": record_data.get("currency", "USD"),
            })
            
        # Perform Bulk Upsert using PostgreSQL ON CONFLICT
        # We assume a unique constraint exists on (cloud_account_id, date, service, granularity)
        stmt = insert(CostRecord).values(values_to_insert)
        
        # Define what to do on conflict (update the amount and currency)
        # Note: We need the constraint name or index details, but typically we can infer from columns
        # If no explicit constraint is defined in models, we might need to rely on delete-then-insert or verify unique index
        
        # Ideally, there should be a unique constraint on these columns in the DB model.
        # Assuming one exists, we update the amount.
        stmt = stmt.on_conflict_do_update(
            index_elements=["cloud_account_id", "date", "service", "granularity"],
            set_={
                "amount": stmt.excluded.amount,
                "currency": stmt.excluded.currency,
            }
        )
        
        await self.db.execute(stmt)
        
        # Update last sync timestamp
        cloud_account.last_sync_at = datetime.now(timezone.utc)
        
        # Flush to database
        await self.db.flush()
        
        # Invalidate cache
        await self.cache.flush_pattern(f"cloudpulse:summary:{cloud_account.id}:*")
        await self.cache.flush_pattern(f"cloudpulse:trend:{cloud_account.id}:*")
        
        # Log Audit
        await AuditService.log(
            self.db,
            organization_id=cloud_account.organization_id,
            user_id=None, # System action (unless triggered by user, which we could propagate)
            action="SYNC",
            resource_type="cloud_account",
            resource_id=cloud_account.id,
            details={
                "provider": cloud_account.provider, 
                "records_processed": len(values_to_insert),
                "period": f"{start_date.date()} to {end_date.date()}"
            }
        )
        # Flush the audit log
        await self.db.flush()
        
        return {
            "account_id": cloud_account.id,
            "records_processed": len(values_to_insert),
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
                CloudAccount.is_active == True,
            )
        )
        accounts = result.scalars().all()
        
        results = []
        for account in accounts:
            # Sync for all supported providers
            if account.provider in ["aws", "azure", "gcp"]:
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
