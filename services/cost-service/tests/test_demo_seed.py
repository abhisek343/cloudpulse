"""Tests for deterministic demo seed generation."""

from decimal import Decimal

import pytest

from app.services.demo_seed import (
    DEFAULT_DEMO_ACCOUNT_PROFILES,
    DemoAccountProfile,
    build_demo_cost_records,
)


class TestDemoSeedProfiles:
    """Tests for demo seed account presets."""

    def test_default_profiles_cover_multiple_scenarios_and_providers(self) -> None:
        """Seed presets should cover the core demo narratives."""
        scenarios = {profile.scenario for profile in DEFAULT_DEMO_ACCOUNT_PROFILES}
        providers = {profile.simulated_provider for profile in DEFAULT_DEMO_ACCOUNT_PROFILES}

        assert scenarios == {"saas", "startup", "enterprise", "incident"}
        assert len(providers) >= 3


class TestDemoSeedRecords:
    """Tests for seeded record generation."""

    @pytest.mark.asyncio
    async def test_seed_generation_is_deterministic(self) -> None:
        """Same inputs should generate identical seeded records."""
        profile = DemoAccountProfile(
            account_name="Demo Startup Sandbox",
            account_id="demo-startup-001",
            scenario="startup",
            simulated_provider="gcp",
        )

        first = await build_demo_cost_records(
            "account-1",
            45,
            profile=profile,
            seed=99,
        )
        second = await build_demo_cost_records(
            "account-1",
            45,
            profile=profile,
            seed=99,
        )

        first_projection = [
            (
                record.date,
                record.service,
                record.region,
                record.amount,
                record.tags,
                record.record_metadata,
            )
            for record in first
        ]
        second_projection = [
            (
                record.date,
                record.service,
                record.region,
                record.amount,
                record.tags,
                record.record_metadata,
            )
            for record in second
        ]

        assert first_projection == second_projection

    @pytest.mark.asyncio
    async def test_seed_generation_includes_adjustments_and_edge_cases(self) -> None:
        """Seeded records should include more than smooth positive spend lines."""
        profile = DemoAccountProfile(
            account_name="Demo Enterprise Core",
            account_id="demo-enterprise-001",
            scenario="enterprise",
            simulated_provider="azure",
        )

        records = await build_demo_cost_records(
            "account-2",
            60,
            profile=profile,
            seed=42,
        )

        assert any(record.amount < Decimal("0") for record in records)
        assert any(
            record.record_metadata and record.record_metadata.get("tag_gap")
            for record in records
        )
        assert any(
            record.record_metadata and record.record_metadata.get("edge_case")
            for record in records
        )
