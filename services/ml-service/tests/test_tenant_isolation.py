"""Regression tests for organization-scoped ML state."""

import asyncio
import pickle
from datetime import datetime, timedelta, timezone

import app.services.anomaly_detector as detector_module
from app.services.anomaly_detector import AnomalyDetector


def _series(base_amount: float, *, days: int = 30) -> list[dict[str, object]]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "date": start + timedelta(days=index),
            "amount": base_amount + float(index % 5),
            "currency": "USD",
            "service": "synthetic-service",
        }
        for index in range(days)
    ]


def test_detector_state_isolated_across_tenants_and_reload(tmp_path, monkeypatch):
    """Training one organization never changes another organization's artifact."""
    monkeypatch.setattr(detector_module.settings, "model_path", str(tmp_path))
    detector_module.clear_detector_registry()

    try:
        tenant_a = detector_module.get_detector("tenant-a")
        tenant_b = detector_module.get_detector("tenant-b")
        assert tenant_a is not tenant_b
        assert not tenant_a.is_fitted
        assert not tenant_b.is_fitted

        training_a = tenant_a.train(_series(100))
        assert training_a["success"] is True
        assert tenant_a.is_fitted
        assert not tenant_b.is_fitted
        assert tenant_a.detect(_series(100))["success"] is True
        baseline_a = dict(tenant_a.baseline_stats)

        training_b = tenant_b.train(_series(1_000))
        assert training_b["success"] is True
        assert tenant_b.is_fitted
        assert tenant_a.baseline_stats == baseline_a
        assert tenant_a.detect(_series(100))["success"] is True
        assert tenant_a.baseline_stats["mean_cost"] < tenant_b.baseline_stats["mean_cost"]

        state_a = tenant_a._state_path
        state_b = tenant_b._state_path
        assert state_a != state_b
        assert state_a.exists()
        assert state_b.exists()
        assert not (tmp_path / "anomaly_detector.pkl").exists()

        detector_module.clear_detector_registry()
        reloaded_a = detector_module.get_detector("tenant-a")
        reloaded_b = detector_module.get_detector("tenant-b")
        assert reloaded_a.is_fitted
        assert reloaded_b.is_fitted
        assert reloaded_a.baseline_stats == baseline_a
        assert reloaded_a.baseline_stats != reloaded_b.baseline_stats
    finally:
        detector_module.clear_detector_registry()


def test_concurrent_training_and_unknown_or_misowned_state_fail_safely(tmp_path, monkeypatch):
    """Concurrent tenant requests and invalid artifacts remain independently safe."""
    monkeypatch.setattr(detector_module.settings, "model_path", str(tmp_path))
    detector_module.clear_detector_registry()

    async def train_concurrently() -> None:
        await asyncio.gather(
            asyncio.to_thread(
                lambda: detector_module.get_detector("concurrent-a").train(_series(10))
            ),
            asyncio.to_thread(
                lambda: detector_module.get_detector("concurrent-b").train(_series(500))
            ),
        )

    try:
        asyncio.run(train_concurrently())
        concurrent_a = detector_module.get_detector("concurrent-a")
        concurrent_b = detector_module.get_detector("concurrent-b")
        assert concurrent_a.is_fitted and concurrent_b.is_fitted
        assert concurrent_a.baseline_stats["mean_cost"] < concurrent_b.baseline_stats["mean_cost"]

        owner_path = AnomalyDetector._build_state_path("misowned")
        owner_path.parent.mkdir(parents=True, exist_ok=True)
        with owner_path.open("wb") as handle:
            pickle.dump({"organization_id": "some-other-tenant"}, handle)

        misowned = AnomalyDetector("misowned")
        assert not misowned.is_fitted
        unknown = detector_module.get_detector("never-trained")
        assert unknown.detect(_series(20))["success"] is False
    finally:
        detector_module.clear_detector_registry()
