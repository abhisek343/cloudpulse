"""Reusable demo data generation helpers."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.config import get_settings
from app.models import CostRecord
from app.services.providers.demo import DemoProvider, _service_bucket

settings = get_settings()

DEFAULT_LOOKBACK_DAYS = 180
DEFAULT_DEMO_SEED = settings.default_demo_seed
DEFAULT_DEMO_ACCOUNT_ID = "demo-saas-001"
DEFAULT_DEMO_ACCOUNT_NAME = "Demo SaaS Workspace"


@dataclass(frozen=True)
class DemoAccountProfile:
    """Preset account shape for demo seeding."""

    account_name: str
    account_id: str
    scenario: str
    simulated_provider: str


DEFAULT_DEMO_ACCOUNT_PROFILES: tuple[DemoAccountProfile, ...] = (
    DemoAccountProfile(
        account_name=DEFAULT_DEMO_ACCOUNT_NAME,
        account_id=DEFAULT_DEMO_ACCOUNT_ID,
        scenario="saas",
        simulated_provider="aws",
    ),
    DemoAccountProfile(
        account_name="Demo Startup Sandbox",
        account_id="demo-startup-001",
        scenario="startup",
        simulated_provider="gcp",
    ),
    DemoAccountProfile(
        account_name="Demo Enterprise Core",
        account_id="demo-enterprise-001",
        scenario="enterprise",
        simulated_provider="azure",
    ),
    DemoAccountProfile(
        account_name="Demo Incident Recovery",
        account_id="demo-incident-001",
        scenario="incident",
        simulated_provider="aws",
    ),
)


def build_demo_credentials(profile: DemoAccountProfile, seed: int) -> dict[str, str | int]:
    """Build credentials metadata for a demo account."""
    return {
        "mode": "demo",
        "scenario": profile.scenario,
        "simulated_provider": profile.simulated_provider,
        "seed": seed,
    }


def _stable_rng(seed: int, *parts: object) -> random.Random:
    """Return a deterministic RNG scoped to a logical record."""
    joined = ":".join(str(part) for part in parts)
    return random.Random(f"{seed}:{joined}")


def _service_slug(service_name: str) -> str:
    """Convert a service label into a stable slug."""
    return re.sub(r"[^a-z0-9]+", "-", service_name.lower()).strip("-")


def _apply_service_mix_shift(
    scenario: str,
    service_name: str,
    day_index: int,
    total_days: int,
) -> tuple[Decimal, list[str]]:
    """Apply deterministic scenario-specific mix shifts to base records."""
    bucket = _service_bucket(service_name)
    multiplier = Decimal("1.0")
    events: list[str] = []
    halfway = max(total_days // 2, 1)

    if scenario == "saas":
        if day_index >= halfway and bucket == "storage":
            multiplier *= Decimal("1.18")
            events.append("retention_growth")
        if day_index % 28 == 0 and bucket == "delivery":
            multiplier *= Decimal("1.12")
            events.append("launch_cycle")
    elif scenario == "startup":
        if day_index >= halfway and bucket == "serverless":
            multiplier *= Decimal("1.35")
            events.append("serverless_adoption")
        if day_index >= halfway and bucket == "compute":
            multiplier *= Decimal("0.78")
            events.append("rightsizing")
        if day_index % 21 == 0 and bucket in {"compute", "serverless"}:
            multiplier *= Decimal("1.25")
            events.append("release_spike")
    elif scenario == "enterprise":
        if day_index >= int(total_days * 0.66) and bucket == "database":
            multiplier *= Decimal("1.18")
            events.append("quarterly_capacity_step")
        if day_index % 30 in {0, 1} and bucket == "compute":
            multiplier *= Decimal("0.92")
            events.append("reserved_capacity_coverage")
    elif scenario == "incident":
        incident_start = max(10, int(total_days * 0.62))
        incident_end = min(total_days - 1, incident_start + 6)
        if incident_start <= day_index <= incident_end:
            if bucket == "delivery":
                multiplier *= Decimal("3.60")
                events.append("traffic_surge")
            elif bucket == "compute":
                multiplier *= Decimal("1.85")
                events.append("autoscaling_surge")
        elif day_index > incident_end and bucket == "delivery":
            multiplier *= Decimal("0.94")
            events.append("post_incident_normalization")

    return multiplier, events


def _apply_metadata_variation(
    *,
    seed: int,
    account_id: str,
    scenario: str,
    service_name: str,
    day_index: int,
    tags: dict | None,
    metadata: dict | None,
) -> tuple[dict | None, dict]:
    """Inject deterministic tagging and ingestion quirks."""
    rng = _stable_rng(seed, account_id, scenario, service_name, day_index, "metadata")
    updated_tags = dict(tags or {})
    updated_metadata = dict(metadata or {})

    updated_tags.setdefault("environment", "demo")
    updated_tags.setdefault("owner", "cloudpulse")
    updated_tags.setdefault("cost_center", scenario)
    updated_tags.setdefault("workload", account_id)

    if rng.random() < 0.09:
        updated_tags.pop("owner", None)
        updated_metadata["tag_gap"] = "missing_owner"

    if rng.random() < 0.03:
        updated_tags = None
        updated_metadata["tag_gap"] = "untagged"

    if rng.random() < 0.12:
        updated_metadata["ingestion_lag_hours"] = rng.choice([1, 3, 6, 12])
    else:
        updated_metadata["ingestion_lag_hours"] = 0

    return updated_tags, updated_metadata


def _build_adjustment_records(
    *,
    account_id: str,
    start_date: datetime,
    days: int,
    profile: DemoAccountProfile,
    seed: int,
) -> list[CostRecord]:
    """Create recurring credits, refunds, and incident-specific adjustments."""
    adjustments: list[CostRecord] = []

    if profile.scenario == "incident":
        incident_start = max(10, int(days * 0.62))
        support_day = start_date + timedelta(days=incident_start)
        support_rng = _stable_rng(seed, account_id, "incident-support")
        support_amount = Decimal(str(round(support_rng.uniform(140, 240), 4)))
        adjustments.append(
            CostRecord(
                cloud_account_id=account_id,
                date=support_day,
                granularity="daily",
                service="Incident Response Support",
                region="global",
                amount=support_amount,
                currency="USD",
                tags={"environment": "demo", "charge_type": "support", "workload": account_id},
                record_metadata={
                    "source": "seed-script",
                    "charge_type": "support",
                    "scenario": profile.scenario,
                    "simulated_provider": profile.simulated_provider,
                    "edge_case": "incident_support",
                },
                resource_id=f"{profile.simulated_provider}://{account_id}/support/incident",
            )
        )

        credit_day = min(days - 1, incident_start + 14)
        credit_rng = _stable_rng(seed, account_id, "incident-credit")
        credit_amount = Decimal(str(round(-credit_rng.uniform(35, 85), 4)))
        adjustments.append(
            CostRecord(
                cloud_account_id=account_id,
                date=start_date + timedelta(days=credit_day),
                granularity="daily",
                service="SLA Credit",
                region="global",
                amount=credit_amount,
                currency="USD",
                tags={"environment": "demo", "charge_type": "credit", "workload": account_id},
                record_metadata={
                    "source": "seed-script",
                    "charge_type": "credit",
                    "scenario": profile.scenario,
                    "simulated_provider": profile.simulated_provider,
                    "edge_case": "sla_credit",
                },
                resource_id=f"{profile.simulated_provider}://{account_id}/credit/sla",
            )
        )
        return adjustments

    adjustment_services = {
        "saas": "Savings Plan Discount",
        "startup": "Startup Promo Credit",
        "enterprise": "Enterprise Agreement Credit",
    }

    for offset in range(14, days, 30):
        rng = _stable_rng(seed, account_id, profile.scenario, offset, "credit")
        if profile.scenario == "saas":
            raw_amount = -rng.uniform(55, 110)
        elif profile.scenario == "startup":
            raw_amount = -rng.uniform(20, 55)
        else:
            raw_amount = -rng.uniform(95, 180)

        adjustments.append(
            CostRecord(
                cloud_account_id=account_id,
                date=start_date + timedelta(days=offset),
                granularity="daily",
                service=adjustment_services[profile.scenario],
                region="global",
                amount=Decimal(str(round(raw_amount, 4))),
                currency="USD",
                tags={"environment": "demo", "charge_type": "credit", "workload": account_id},
                record_metadata={
                    "source": "seed-script",
                    "charge_type": "credit",
                    "scenario": profile.scenario,
                    "simulated_provider": profile.simulated_provider,
                    "edge_case": "recurring_credit",
                },
                resource_id=f"{profile.simulated_provider}://{account_id}/credit/{offset}",
            )
        )

    return adjustments


async def build_demo_cost_records(
    account_id: str,
    days: int,
    *,
    profile: DemoAccountProfile,
    seed: int = DEFAULT_DEMO_SEED,
) -> list[CostRecord]:
    """Generate deterministic seeded billing history for a demo account."""
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end_date, datetime.min.time(), tzinfo=UTC)

    provider = DemoProvider(
        provider_type="demo",
        config={
            "scenario": profile.scenario,
            "seed": seed,
            "simulated_provider": profile.simulated_provider,
            "account_id": account_id,
        },
    )
    generated_records = await provider.get_cost_data(start_dt, end_dt)

    records: list[CostRecord] = []
    for generated in generated_records:
        record_date = generated["date"]
        day_index = (record_date.date() - start_date).days
        base_amount = Decimal(str(generated["amount"]))
        multiplier, events = _apply_service_mix_shift(
            profile.scenario,
            generated["service"],
            day_index,
            days,
        )
        amount = (base_amount * multiplier).quantize(Decimal("0.0001"))
        tags, metadata = _apply_metadata_variation(
            seed=seed,
            account_id=account_id,
            scenario=profile.scenario,
            service_name=generated["service"],
            day_index=day_index,
            tags=generated.get("tags"),
            metadata=generated.get("record_metadata"),
        )
        metadata["source"] = "seed-script"
        if events:
            metadata["seed_events"] = events

        records.append(
            CostRecord(
                cloud_account_id=account_id,
                date=record_date,
                granularity="daily",
                service=generated["service"],
                region=generated["region"],
                resource_id=(
                    f"{profile.simulated_provider}://{account_id}/"
                    f"{_service_slug(generated['service'])}/{day_index}"
                ),
                amount=amount,
                currency=str(generated["currency"]),
                tags=tags,
                record_metadata=metadata,
            )
        )

    records.extend(
        _build_adjustment_records(
            account_id=account_id,
            start_date=start_dt,
            days=days,
            profile=profile,
            seed=seed,
        )
    )
    return records
