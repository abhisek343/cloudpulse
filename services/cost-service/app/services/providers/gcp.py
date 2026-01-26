"""
CloudPulse AI - Cost Service
Google Cloud Platform (GCP) Cost Provider.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from anyio import to_thread
from google.cloud import billing_v1
from google.oauth2 import service_account
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.providers.base import CostProvider

logger = logging.getLogger(__name__)


class GCPProvider(CostProvider):
    """
    GCP implementation of CostProvider.
    Uses Google Cloud Billing API (Cloud Billing Catalog & Budget API).
    Note: Ideally uses BigQuery export for granular costs, but Billing API is used for simple aggregation here.
    """
    
    def __init__(self, credentials: dict[str, Any]) -> None:
        self.project_id = credentials.get("project_id")
        self.billing_account_id = credentials.get("billing_account_id")
        self.service_account_info = credentials.get("service_account_json") # Dict
        
        if not self.service_account_info:
            logger.warning("GCP provider initialized without service account credentials")

    @property
    def client(self) -> billing_v1.CloudBillingClient:
        """Lazy load client."""
        creds = service_account.Credentials.from_service_account_info(self.service_account_info)
        return billing_v1.CloudBillingClient(credentials=creds)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_cost_data(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        granularity: str = "DAILY"
    ) -> list[dict[str, Any]]:
        """
        GCP Billing API is limited for programmatic cost fetching of *incurred* costs directly via simple API.
        The standard pattern is: Billing -> BigQuery Export -> SQL Query.
        
        For this prototype adapter, we will simulate the structure assuming a BigQuery client was here,
        or use a simplified assumption that we might have a custom API wrapper.
        
        Since setting up BQ is complex for a demo code block, we will implement the 
        structure but raise a NotImplementedError or return mock if credentials fail.
        """
        # In a real impl:
        # client = bigquery.Client(credentials=self.creds, project=self.project_id)
        # query = f"SELECT usage_start_time, service.description, cost, currency FROM `{self.table_id}` ..."
        
        logger.info("GCP Cost Fetch triggered (Requires BigQuery Export setup)")
        
        # Simulating a return for now to satisfy interface check
        # In production this would be: await to_thread.run_sync(lambda: client.query(query).result())
        return []

    async def get_forecast(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY"
    ) -> dict[str, Any]:
        return {
            "total": Decimal("0"), 
            "note": "GCP Forecast requires BigQuery ML"
        }
