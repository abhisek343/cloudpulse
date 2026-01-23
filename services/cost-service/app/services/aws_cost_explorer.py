"""
CloudPulse AI - Cost Service
AWS Cost Explorer integration for fetching cost data.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

settings = get_settings()


class AWSCostExplorerService:
    """Service for interacting with AWS Cost Explorer API."""
    
    def __init__(
        self,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session_token: str | None = None,
        region: str = "us-east-1",
    ) -> None:
        """Initialize AWS Cost Explorer client."""
        self.client = boto3.client(
            "ce",
            aws_access_key_id=access_key_id or settings.aws_access_key_id,
            aws_secret_access_key=secret_access_key or settings.aws_secret_access_key,
            aws_session_token=session_token or settings.aws_session_token,
            region_name=region,
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get_cost_and_usage(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "DAILY",
        group_by: list[dict[str, str]] | None = None,
        filter_expression: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch cost and usage data from AWS Cost Explorer.
        
        Args:
            start_date: Start of the time period
            end_date: End of the time period
            granularity: DAILY, MONTHLY, or HOURLY
            group_by: List of dimensions to group by (e.g., SERVICE, REGION)
            filter_expression: Optional filter expression
            
        Returns:
            List of cost records
        """
        params: dict[str, Any] = {
            "TimePeriod": {
                "Start": start_date.strftime("%Y-%m-%d"),
                "End": end_date.strftime("%Y-%m-%d"),
            },
            "Granularity": granularity,
            "Metrics": ["UnblendedCost", "UsageQuantity"],
        }
        
        if group_by:
            params["GroupBy"] = group_by
        
        if filter_expression:
            params["Filter"] = filter_expression
        
        results: list[dict[str, Any]] = []
        next_token: str | None = None
        
        while True:
            if next_token:
                params["NextPageToken"] = next_token
            
            try:
                response = self.client.get_cost_and_usage(**params)
            except ClientError as e:
                raise AWSCostExplorerError(f"Failed to fetch cost data: {e}") from e
            
            results.extend(response.get("ResultsByTime", []))
            next_token = response.get("NextPageToken")
            
            if not next_token:
                break
        
        return results
    
    async def get_cost_by_service(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "DAILY",
    ) -> list[dict[str, Any]]:
        """Get costs grouped by AWS service."""
        return await self.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
    
    async def get_cost_by_region(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "DAILY",
    ) -> list[dict[str, Any]]:
        """Get costs grouped by AWS region."""
        return await self.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            group_by=[{"Type": "DIMENSION", "Key": "REGION"}],
        )
    
    async def get_cost_by_tag(
        self,
        start_date: datetime,
        end_date: datetime,
        tag_key: str,
        granularity: str = "DAILY",
    ) -> list[dict[str, Any]]:
        """Get costs grouped by a specific tag."""
        return await self.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            group_by=[{"Type": "TAG", "Key": tag_key}],
        )
    
    async def get_cost_forecast(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY",
        metric: str = "UNBLENDED_COST",
    ) -> dict[str, Any]:
        """
        Get cost forecast from AWS Cost Explorer.
        
        Note: Forecast is only available for future dates.
        """
        try:
            response = self.client.get_cost_forecast(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity=granularity,
                Metric=metric,
            )
            return {
                "total": Decimal(response.get("Total", {}).get("Amount", "0")),
                "unit": response.get("Total", {}).get("Unit", "USD"),
                "forecast_by_time": response.get("ForecastResultsByTime", []),
            }
        except ClientError as e:
            raise AWSCostExplorerError(f"Failed to get forecast: {e}") from e
    
    async def get_budgets(self, account_id: str) -> list[dict[str, Any]]:
        """Get AWS Budgets for an account."""
        budgets_client = boto3.client(
            "budgets",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name="us-east-1",  # Budgets API only available in us-east-1
        )
        
        try:
            response = budgets_client.describe_budgets(AccountId=account_id)
            return response.get("Budgets", [])
        except ClientError as e:
            raise AWSCostExplorerError(f"Failed to fetch budgets: {e}") from e
    
    def parse_cost_response(
        self,
        response: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Parse AWS Cost Explorer response into standardized format."""
        records = []
        
        for time_period in response:
            start_date = datetime.strptime(
                time_period["TimePeriod"]["Start"],
                "%Y-%m-%d",
            )
            
            groups = time_period.get("Groups", [])
            
            if groups:
                for group in groups:
                    keys = group.get("Keys", [])
                    metrics = group.get("Metrics", {})
                    
                    amount = Decimal(
                        metrics.get("UnblendedCost", {}).get("Amount", "0")
                    )
                    
                    if amount > Decimal("0.001"):
                        records.append({
                            "date": start_date,
                            "service": keys[0] if keys else "Unknown",
                            "amount": amount,
                            "currency": metrics.get("UnblendedCost", {}).get("Unit", "USD"),
                            "usage_quantity": Decimal(
                                metrics.get("UsageQuantity", {}).get("Amount", "0")
                            ),
                        })
            else:
                # No grouping - total costs
                metrics = time_period.get("Total", {})
                amount = Decimal(
                    metrics.get("UnblendedCost", {}).get("Amount", "0")
                )
                
                if amount > Decimal("0.001"):
                    records.append({
                        "date": start_date,
                        "service": "Total",
                        "amount": amount,
                        "currency": metrics.get("UnblendedCost", {}).get("Unit", "USD"),
                    })
        
        return records


class AWSCostExplorerError(Exception):
    """Custom exception for AWS Cost Explorer errors."""
    pass


# Factory function for dependency injection
def get_aws_cost_explorer(
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
) -> AWSCostExplorerService:
    """Get AWS Cost Explorer service instance."""
    return AWSCostExplorerService(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )
