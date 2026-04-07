"""
CloudPulse AI - Cost Service
Google Cloud Platform (GCP) Cost Provider.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from anyio import to_thread
from google.cloud import billing_v1
from google.oauth2 import service_account
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.services.providers.base import CostProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class GCPProvider(CostProvider):
    """
    GCP implementation of CostProvider.
    Uses Google Cloud Billing API (Cloud Billing Catalog & Budget API).
    Note: ideally this uses a billing export for granular incurred-cost queries.
    """

    def __init__(self, credentials: dict[str, Any]) -> None:
        self.project_id = credentials.get("project_id") or settings.gcp_project_id
        self.billing_account_id = (
            credentials.get("billing_account_id") or settings.gcp_billing_account_id
        )
        self.billing_export_table = (
            credentials.get("billing_export_table") or settings.gcp_billing_export_table
        )
        self.service_account_info = self._load_service_account_info(credentials)

        if not self.service_account_info:
            logger.warning(
                "GCP provider initialized without service account credentials. Set "
                "GCP_SERVICE_ACCOUNT_JSON or GCP_SERVICE_ACCOUNT_FILE, or provide "
                "service_account_json in the account credentials."
            )

    def _load_service_account_info(
        self,
        credentials: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Load service account info from account credentials or env-backed config."""
        credential_value = credentials.get("service_account_json")
        if isinstance(credential_value, dict):
            return credential_value
        if isinstance(credential_value, str) and credential_value.strip():
            return json.loads(credential_value)

        env_json = settings.gcp_service_account_json
        if env_json:
            return json.loads(env_json)

        env_file = settings.gcp_service_account_file
        if env_file:
            return json.loads(Path(env_file).read_text(encoding="utf-8"))

        return None

    def _require_credentials(self) -> None:
        """Raise a clear error when GCP live sync is not fully configured."""
        if self.service_account_info:
            return

        raise ValueError(
            "GCP live sync requires GCP_SERVICE_ACCOUNT_JSON or "
            "GCP_SERVICE_ACCOUNT_FILE, or service_account_json in the cloud "
            "account credentials."
        )

    def _require_billing_export(self) -> None:
        """Require a BigQuery billing export table for incurred-cost queries."""
        if self.billing_export_table:
            return

        raise ValueError(
            "GCP live sync requires GCP_BILLING_EXPORT_TABLE or "
            "billing_export_table in the cloud account credentials."
        )

    @property
    def client(self) -> billing_v1.CloudBillingClient:
        """Lazy load client."""
        self._require_credentials()
        creds = service_account.Credentials.from_service_account_info(self.service_account_info)
        return billing_v1.CloudBillingClient(credentials=creds)

    @property
    def bigquery_client(self) -> Any:
        """Lazy load BigQuery client for billing export queries."""
        self._require_credentials()
        self._require_billing_export()

        from google.cloud import bigquery

        creds = service_account.Credentials.from_service_account_info(self.service_account_info)
        return bigquery.Client(project=self.project_id, credentials=creds)

    def _build_bigquery_query(self) -> str:
        """Build the standard billing export aggregation query."""
        return f"""
SELECT
  DATE(usage_start_time) AS usage_date,
  COALESCE(service.description, 'Unknown') AS service_name,
  COALESCE(location.region, location.location, location.zone, 'global') AS region_name,
  SUM(cost) AS total_cost,
  ANY_VALUE(currency) AS currency
FROM `{self.billing_export_table}`
WHERE usage_start_time >= @start_time
  AND usage_start_time < @end_time
GROUP BY usage_date, service_name, region_name
ORDER BY usage_date ASC, service_name ASC
"""

    def _build_bigquery_validation_query(self) -> str:
        """Build a minimal validation query against the billing export."""
        return f"""
SELECT COUNT(1) AS row_count
FROM `{self.billing_export_table}`
WHERE usage_start_time >= @start_time
  AND usage_start_time < @end_time
"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_cost_data(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "DAILY",
    ) -> list[dict[str, Any]]:
        """
        Fetch incurred costs from a standard GCP billing export in BigQuery.
        """
        del granularity

        from google.cloud import bigquery

        logger.info("GCP Cost Fetch triggered via BigQuery billing export")
        query = self._build_bigquery_query()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", start_date),
                bigquery.ScalarQueryParameter("end_time", "TIMESTAMP", end_date),
            ]
        )

        rows = await to_thread.run_sync(
            lambda: list(self.bigquery_client.query(query, job_config=job_config).result())
        )
        return self._parse_response(rows)

    def _parse_response(self, rows: list[Any]) -> list[dict[str, Any]]:
        """Normalize BigQuery billing-export rows into standard cost records."""
        records: list[dict[str, Any]] = []
        for row in rows:
            usage_date = row["usage_date"]
            if hasattr(usage_date, "year") and not isinstance(usage_date, datetime):
                date_obj = datetime(
                    year=usage_date.year,
                    month=usage_date.month,
                    day=usage_date.day,
                )
            else:
                date_obj = usage_date

            amount = Decimal(str(row["total_cost"]))
            if amount == Decimal("0"):
                continue

            records.append(
                {
                    "date": date_obj,
                    "service": row["service_name"],
                    "region": row["region_name"] or "global",
                    "amount": amount,
                    "currency": row["currency"] or "USD",
                    "usage_quantity": Decimal("0"),
                }
            )

        return records

    async def get_forecast(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY",
    ) -> dict[str, Any]:
        """
        Generate a cost forecast using historical data and Chronos (ML service).

        GCP does not expose a native billing forecast API, so we fetch
        recent actuals from the BigQuery billing export and delegate
        prediction to the ML service which uses Amazon Chronos (zero-shot).
        """
        from app.services.providers._forecast import chronos_forecast_fallback

        return await chronos_forecast_fallback(
            provider=self,
            start_date=start_date,
            end_date=end_date,
        )

    async def validate_live_access(self) -> dict[str, Any]:
        """Run a minimal BigQuery validation query against the billing export."""
        from google.cloud import bigquery

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=30)
        query = self._build_bigquery_validation_query()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", start_time),
                bigquery.ScalarQueryParameter("end_time", "TIMESTAMP", end_time),
            ]
        )

        try:
            rows = await to_thread.run_sync(
                lambda: list(self.bigquery_client.query(query, job_config=job_config).result())
            )
        except Exception as e:
            logger.error(f"GCP live validation failed: {e}")
            raise RuntimeError(f"GCP live validation failed: {e}") from e

        row_count = 0
        if rows:
            row_count = int(rows[0]["row_count"] or 0)

        return {
            "detail": (
                "Connected to the GCP billing export in BigQuery and executed a "
                f"minimal validation query ({row_count} rows in the last 30 days)."
            )
        }
