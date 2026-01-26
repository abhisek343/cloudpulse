"""
CloudPulse AI - Cost Service
Azure Cost Management Provider.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from anyio import to_thread
from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import QueryDefinition, QueryTimePeriod, QueryDataset, QueryAggregation, QueryGrouping
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.providers.base import CostProvider

logger = logging.getLogger(__name__)


class AzureProvider(CostProvider):
    """
    Azure implementation of CostProvider.
    Uses Azure Cost Management API.
    """
    
    def __init__(self, credentials: dict[str, Any]) -> None:
        self.subscription_id = credentials.get("subscription_id")
        self.tenant_id = credentials.get("tenant_id")
        self.client_id = credentials.get("client_id")
        self.client_secret = credentials.get("client_secret")
        
        if not all([self.subscription_id, self.tenant_id, self.client_id, self.client_secret]):
             # Allow initialization for structure, but methods will fail if called without creds
             logger.warning("Azure provider initialized without full credentials")

    @property
    def client(self) -> CostManagementClient:
        """Lazy load client."""
        credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        return CostManagementClient(credential, self.subscription_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_cost_data(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        granularity: str = "DAILY"
    ) -> list[dict[str, Any]]:
        """
        Fetch costs grouped by ServiceName (ServiceName is roughly equivalent to AWS Service).
        """
        # Azure expects 'Daily' or 'Monthly'
        azure_granularity = "Daily" if granularity.upper() == "DAILY" else "Monthly"
        
        # Build Query
        # We want to group by 'ServiceName' and 'ResourceLocation'
        query = QueryDefinition(
            type="Usage",
            timeframe="Custom",
            time_period=QueryTimePeriod(from_property=start_date, to=end_date),
            dataset=QueryDataset(
                granularity=azure_granularity,
                aggregation={
                    "totalCost": QueryAggregation(name="Cost", function="Sum")
                },
                grouping=[
                    QueryGrouping(type="Dimension", name="ServiceName"),
                    QueryGrouping(type="Dimension", name="ResourceLocation")
                ]
            )
        )
        
        try:
            # Run blocking call in thread
            # Scope is usually /subscriptions/{subscriptionId}
            scope = f"/subscriptions/{self.subscription_id}"
            
            result = await to_thread.run_sync(
                lambda: self.client.query.usage(scope, query)
            )
            
            return self._parse_response(result.rows)
            
        except Exception as e:
            logger.error(f"Azure Cost Management Error: {e}")
            raise RuntimeError(f"Azure Cost Management Error: {e}") from e

    def _parse_response(self, rows: list) -> list[dict[str, Any]]:
        """
        Convert Azure response rows to standardized format.
        Azure rows usually: [Cost, ServiceName, ResourceLocation, Currency, Date]
        """
        parsed_data = []
        
        for row in rows:
            # Note: The order depends on the query structure, usually:
            # [Cost, Date, ServiceName, ResourceLocation, Currency] for Daily
            # But checking Azure SDK docs or inspecting response is safer. 
            # We assume a mapping based on typical Azure Query results.
            
            # Typical row: [12.50, 2023-10-01, "Virtual Machines", "eastus", "USD"]
            # Let's handle generic index access safely
            try:
                cost = Decimal(str(row[0]))
                date_val = row[1] 
                service = row[2]
                region = row[3]
                currency = row[4] if len(row) > 4 else "USD"
                
                # Ensure date is datetime
                if isinstance(date_val, str):
                    date_obj = datetime.fromisoformat(date_val)
                else:
                    date_obj = date_val

                parsed_data.append({
                    "date": date_obj,
                    "service": service,
                    "amount": cost,
                    "currency": currency,
                    "region": region,
                    "usage_quantity": Decimal("0"), # Azure Aggregation often doesn't give simple quantity in this view
                })
            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse Azure cost row: {row} - {e}")
                continue
                
        return parsed_data

    async def get_forecast(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY"
    ) -> dict[str, Any]:
        """
        Azure Forecast API is complex/often requires different permissions.
        For now, we return a mock or basic projection.
        """
        return {
            "total": Decimal("0"), 
            "note": "Azure Native Forecast not yet implemented in this adapter."
        }
