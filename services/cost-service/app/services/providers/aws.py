"""
CloudPulse AI - Cost Service
AWS Cost Provider implementation.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.services.providers.base import CostProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class AWSCostProvider(CostProvider):
    """AWS implementation of CostProvider using Cost Explorer."""
    
    def __init__(self, credentials: dict[str, str]) -> None:
        self.client = boto3.client(
            "ce",
            aws_access_key_id=credentials.get("access_key_id") or settings.aws_access_key_id,
            aws_secret_access_key=credentials.get("secret_access_key") or settings.aws_secret_access_key,
            aws_session_token=credentials.get("session_token") or settings.aws_session_token,
            region_name="us-east-1",
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_cost_data(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        granularity: str = "DAILY"
    ) -> list[dict[str, Any]]:
        """
        Fetch costs grouped by Service.
        """
        params = {
            "TimePeriod": {
                "Start": start_date.strftime("%Y-%m-%d"),
                "End": end_date.strftime("%Y-%m-%d"),
            },
            "Granularity": granularity,
            "Metrics": ["UnblendedCost", "UsageQuantity"],
            "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}]
        }

        try:
            results: list[dict[str, Any]] = []
            next_token = None
            
            while True:
                if next_token:
                    params["NextPageToken"] = next_token
                
                response = self.client.get_cost_and_usage(**params)
                results.extend(response.get("ResultsByTime", []))
                next_token = response.get("NextPageToken")
                
                if not next_token:
                    break
            
            return self._parse_response(results)
            
        except ClientError as e:
            logger.error(f"AWS Cost Explorer Error: {e}")
            raise RuntimeError(f"AWS Cost Explorer Error: {e}") from e

    async def get_forecast(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY"
    ) -> dict[str, Any]:
        try:
            response = self.client.get_cost_forecast(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity=granularity,
                Metric="UNBLENDED_COST",
            )
            return {
                "total": Decimal(response.get("Total", {}).get("Amount", "0")),
                "unit": response.get("Total", {}).get("Unit", "USD"),
                "forecast_by_time": response.get("ForecastResultsByTime", []),
            }
        except ClientError as e:
            logger.error(f"AWS Forecast Error: {e}")
            raise RuntimeError(f"AWS Forecast Error: {e}") from e

    def _parse_response(self, raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize AWS response to standard format."""
        records: list[dict[str, Any]] = []
        for period in raw_data:
            start_str = period["TimePeriod"]["Start"]
            date_obj = datetime.strptime(start_str, "%Y-%m-%d")
            
            for group in period.get("Groups", []):
                service_name = group["Keys"][0] if group["Keys"] else "Unknown"
                metrics = group.get("Metrics", {})
                
                amount = Decimal(metrics.get("UnblendedCost", {}).get("Amount", "0"))
                if amount <= Decimal("0"):
                    continue

                records.append({
                    "date": date_obj,
                    "service": service_name,
                    "amount": amount,
                    "currency": metrics.get("UnblendedCost", {}).get("Unit", "USD"),
                    "usage_quantity": Decimal(metrics.get("UsageQuantity", {}).get("Amount", "0")),
                })
        return records
