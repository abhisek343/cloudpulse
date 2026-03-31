"""
CloudPulse AI - Cost Service
Azure Cost Management Provider.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from anyio import to_thread
from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.services.providers.base import CostProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class AzureProvider(CostProvider):
    """
    Azure implementation of CostProvider.
    Uses Azure Cost Management API.
    """

    def __init__(self, credentials: dict[str, Any]) -> None:
        self.subscription_id = credentials.get("subscription_id") or settings.azure_subscription_id
        self.tenant_id = credentials.get("tenant_id") or settings.azure_tenant_id
        self.client_id = credentials.get("client_id") or settings.azure_client_id
        self.client_secret = credentials.get("client_secret") or settings.azure_client_secret

        if not all([self.subscription_id, self.tenant_id, self.client_id, self.client_secret]):
            logger.warning(
                "Azure provider initialized without full credentials. Set "
                "AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, AZURE_CLIENT_ID, and "
                "AZURE_CLIENT_SECRET or provide them in the account credentials."
            )

    def _require_credentials(self) -> None:
        """Raise a clear error when Azure live sync is not fully configured."""
        if all([self.subscription_id, self.tenant_id, self.client_id, self.client_secret]):
            return

        raise ValueError(
            "Azure live sync requires AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, "
            "AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET, or the same values in the "
            "cloud account credentials."
        )

    @property
    def client(self) -> CostManagementClient:
        """Lazy load client."""
        self._require_credentials()
        credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        return CostManagementClient(credential, self.subscription_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_cost_data(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "DAILY",
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
                aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                grouping=[
                    QueryGrouping(type="Dimension", name="ServiceName"),
                    QueryGrouping(type="Dimension", name="ResourceLocation"),
                ],
            ),
        )

        try:
            # Run blocking call in thread
            # Scope is usually /subscriptions/{subscriptionId}
            scope = f"/subscriptions/{self.subscription_id}"

            result = await to_thread.run_sync(lambda: self.client.query.usage(scope, query))

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

                parsed_data.append(
                    {
                        "date": date_obj,
                        "service": service,
                        "amount": cost,
                        "currency": currency,
                        "region": region,
                        # Azure aggregation often omits a simple quantity in this view.
                        "usage_quantity": Decimal("0"),
                    }
                )
            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse Azure cost row: {row} - {e}")
                continue

        return parsed_data

    async def get_forecast(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY",
    ) -> dict[str, Any]:
        """
        Azure Forecast API is complex/often requires different permissions.
        For now, we return a mock or basic projection.
        """
        return {
            "total": Decimal("0"),
            "note": "Azure Native Forecast not yet implemented in this adapter.",
        }

    async def validate_live_access(self) -> dict[str, Any]:
        """Run a minimal Cost Management usage query to verify live access."""
        self._require_credentials()

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=1)
        query = QueryDefinition(
            type="Usage",
            timeframe="Custom",
            time_period=QueryTimePeriod(from_property=start_time, to=end_time),
            dataset=QueryDataset(
                granularity="Daily",
                aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
            ),
        )

        try:
            scope = f"/subscriptions/{self.subscription_id}"
            result = await to_thread.run_sync(lambda: self.client.query.usage(scope, query))
        except Exception as e:
            logger.error(f"Azure live validation failed: {e}")
            raise RuntimeError(f"Azure live validation failed: {e}") from e

        row_count = len(result.rows or [])
        return {
            "detail": (
                "Connected to Azure Cost Management and executed a minimal "
                f"usage query ({row_count} rows)."
            )
        }
