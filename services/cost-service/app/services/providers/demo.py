"""
CloudPulse AI - Cost Service
Demo provider for safe local experimentation.
"""
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.services.providers.base import CostProvider

settings = get_settings()

PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "aws": {
        "regions": ["us-east-1", "us-west-2", "eu-west-1"],
        "services": {
            "Amazon EC2": {"base": 150.0, "usage_multiplier": 9.5},
            "Amazon RDS": {"base": 72.0, "usage_multiplier": 5.0},
            "Amazon S3": {"base": 24.0, "usage_multiplier": 18.0},
            "AWS Lambda": {"base": 16.0, "usage_multiplier": 40.0},
            "Amazon CloudFront": {"base": 20.0, "usage_multiplier": 11.0},
        },
    },
    "azure": {
        "regions": ["eastus", "westeurope", "southeastasia"],
        "services": {
            "Virtual Machines": {"base": 148.0, "usage_multiplier": 9.0},
            "Azure SQL Database": {"base": 68.0, "usage_multiplier": 4.8},
            "Blob Storage": {"base": 21.0, "usage_multiplier": 17.5},
            "Functions": {"base": 12.0, "usage_multiplier": 36.0},
            "Azure CDN": {"base": 18.0, "usage_multiplier": 10.0},
        },
    },
    "gcp": {
        "regions": ["us-central1", "europe-west1", "asia-south1"],
        "services": {
            "Compute Engine": {"base": 145.0, "usage_multiplier": 9.2},
            "Cloud SQL": {"base": 64.0, "usage_multiplier": 4.5},
            "Cloud Storage": {"base": 19.0, "usage_multiplier": 17.0},
            "Cloud Functions": {"base": 11.0, "usage_multiplier": 35.0},
            "Cloud CDN": {"base": 17.0, "usage_multiplier": 9.0},
        },
    },
}

SCENARIO_PROFILES: dict[str, dict[str, Any]] = {
    "saas": {
        "growth": 0.0035,
        "weekend_multiplier": 0.88,
        "volatility": 0.10,
        "anomaly_rate": 0.02,
        "service_bias": {
            "compute": 1.0,
            "database": 1.0,
            "storage": 1.0,
            "serverless": 1.15,
            "delivery": 1.05,
        },
    },
    "startup": {
        "growth": 0.0065,
        "weekend_multiplier": 0.93,
        "volatility": 0.18,
        "anomaly_rate": 0.035,
        "service_bias": {
            "compute": 0.85,
            "database": 0.75,
            "storage": 0.70,
            "serverless": 1.35,
            "delivery": 1.20,
        },
    },
    "enterprise": {
        "growth": 0.0020,
        "weekend_multiplier": 0.83,
        "volatility": 0.06,
        "anomaly_rate": 0.012,
        "service_bias": {
            "compute": 1.20,
            "database": 1.15,
            "storage": 1.10,
            "serverless": 0.90,
            "delivery": 1.00,
        },
    },
    "incident": {
        "growth": 0.0030,
        "weekend_multiplier": 0.90,
        "volatility": 0.09,
        "anomaly_rate": 0.05,
        "service_bias": {
            "compute": 1.10,
            "database": 1.00,
            "storage": 1.00,
            "serverless": 1.10,
            "delivery": 1.25,
        },
    },
}


def _service_bucket(service_name: str) -> str:
    lowered = service_name.lower()
    if "lambda" in lowered or "function" in lowered:
        return "serverless"
    if "sql" in lowered or "rds" in lowered or "database" in lowered:
        return "database"
    if "storage" in lowered or "s3" in lowered or "blob" in lowered:
        return "storage"
    if "cdn" in lowered or "cloudfront" in lowered:
        return "delivery"
    return "compute"


class DemoProvider(CostProvider):
    """Synthetic provider that behaves like a safe stand-in for cloud billing APIs."""

    def __init__(self, provider_type: str, config: dict[str, Any]) -> None:
        requested_provider = provider_type.lower()
        simulated_provider = str(
            config.get(
                "simulated_provider",
                settings.default_demo_provider if requested_provider == "demo" else requested_provider,
            )
        ).lower()

        if simulated_provider not in PROVIDER_PROFILES:
            simulated_provider = settings.default_demo_provider

        self.provider_type = requested_provider
        self.simulated_provider = simulated_provider
        self.mode = "demo"
        self.scenario = str(config.get("scenario", settings.default_demo_scenario)).lower()
        if self.scenario not in SCENARIO_PROFILES:
            self.scenario = settings.default_demo_scenario

        self.seed = int(config.get("seed", settings.default_demo_seed))
        self.account_id = str(config.get("account_id", "demo-account"))

    def _rng_for_day(self, day_index: int, service_name: str) -> random.Random:
        return random.Random(f"{self.seed}:{self.account_id}:{self.simulated_provider}:{service_name}:{day_index}")

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _generate_amount(
        self,
        base_cost: float,
        service_name: str,
        current_date: datetime,
        start_date: datetime,
    ) -> Decimal:
        scenario = SCENARIO_PROFILES[self.scenario]
        service_group = _service_bucket(service_name)
        day_index = (current_date.date() - start_date.date()).days
        rng = self._rng_for_day(day_index, service_name)

        trend = 1 + (scenario["growth"] * day_index)
        weekend = scenario["weekend_multiplier"] if current_date.weekday() >= 5 else 1.0
        weekly_wave = 1 + (0.05 * ((current_date.weekday() - 3) / 3))
        volatility = scenario["volatility"]
        noise = rng.uniform(1 - volatility, 1 + volatility)
        anomaly_multiplier = (
            rng.uniform(1.8, 3.6) if rng.random() < scenario["anomaly_rate"] else 1.0
        )
        service_bias = scenario["service_bias"][service_group]

        amount = base_cost * service_bias * trend * weekend * weekly_wave * noise * anomaly_multiplier
        return Decimal(str(round(max(amount, 0.01), 4)))

    async def get_cost_data(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "DAILY",
    ) -> list[dict[str, Any]]:
        del granularity
        profile = PROVIDER_PROFILES[self.simulated_provider]
        services = profile["services"]
        regions = profile["regions"]
        records: list[dict[str, Any]] = []

        normalized_start = self._normalize_datetime(start_date)
        normalized_end = self._normalize_datetime(end_date)
        current = normalized_start.replace(hour=0, minute=0, second=0, microsecond=0)
        final = normalized_end.replace(hour=0, minute=0, second=0, microsecond=0)

        while current <= final:
            day_index = (current.date() - normalized_start.date()).days

            for service_name, service_profile in services.items():
                rng = self._rng_for_day(day_index, service_name)
                amount = self._generate_amount(service_profile["base"], service_name, current, normalized_start)
                usage_quantity = Decimal(
                    str(round(float(amount) * service_profile["usage_multiplier"], 2))
                )

                records.append(
                    {
                        "date": current,
                        "service": service_name,
                        "region": rng.choice(regions),
                        "amount": amount,
                        "currency": "USD",
                        "usage_quantity": usage_quantity,
                        "tags": {
                            "environment": "demo",
                            "scenario": self.scenario,
                            "provider": self.simulated_provider,
                        },
                        "record_metadata": {
                            "mode": "demo",
                            "scenario": self.scenario,
                            "simulated_provider": self.simulated_provider,
                        },
                    }
                )

            current += timedelta(days=1)

        return records

    async def get_forecast(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY",
    ) -> dict[str, Any]:
        del granularity
        forecast_data = await self.get_cost_data(start_date, end_date, granularity="DAILY")
        total = sum((record["amount"] for record in forecast_data), start=Decimal("0"))
        return {
            "total": total.quantize(Decimal("0.01")),
            "unit": "USD",
            "forecast_by_time": [
                {
                    "TimePeriod": {
                        "Start": start_date.strftime("%Y-%m-%d"),
                        "End": end_date.strftime("%Y-%m-%d"),
                    },
                    "MeanValue": str(total.quantize(Decimal("0.01"))),
                }
            ],
            "metadata": {
                "mode": "demo",
                "scenario": self.scenario,
                "simulated_provider": self.simulated_provider,
            },
        }
