"""
CloudPulse AI - Cost Service
Cost data synchronization service.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RedisCache
from app.models import CloudAccount, CostRecord
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
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Fetch normalized cost data from provider
        # get_cost_data returns List[Dict] with standardized keys (date, service, amount, etc.)
        parsed_records = await provider.get_cost_data(
            start_date=start_date,
            end_date=end_date,
            granularity="DAILY",
        )
        
        # Store records
        records_created = 0
        records_updated = 0
        
        for record_data in parsed_records:
            # Check if record already exists
            existing = await self.db.execute(
                select(CostRecord).where(
                    CostRecord.cloud_account_id == cloud_account.id,
                    CostRecord.date == record_data["date"],
                    CostRecord.service == record_data["service"],
                    CostRecord.granularity == "daily",
                )
            )
            existing_record = existing.scalar_one_or_none()
            
            if existing_record:
                # Update existing record
                existing_record.amount = record_data["amount"]
                existing_record.currency = record_data.get("currency", "USD")
                records_updated += 1
            else:
                # Create new record
                new_record = CostRecord(
                    cloud_account_id=cloud_account.id,
                    date=record_data["date"],
                    granularity="daily",
                    service=record_data["service"],
                    amount=record_data["amount"],
                    currency=record_data.get("currency", "USD"),
                )
                self.db.add(new_record)
                records_created += 1
        
        # Update last sync timestamp
        cloud_account.last_sync_at = datetime.utcnow()
        
        # Flush to database
        await self.db.flush()
        
        # Invalidate cache
        await self.cache.flush_pattern(f"cloudpulse:summary:{cloud_account.id}:*")
        await self.cache.flush_pattern(f"cloudpulse:trend:{cloud_account.id}:*")
        
        return {
            "account_id": cloud_account.id,
            "records_created": records_created,
            "records_updated": records_updated,
            "total_records": records_created + records_updated,
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
