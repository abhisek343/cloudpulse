"""
CloudPulse AI - Cost Service
Tests for the Kubernetes cost attribution service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.kubernetes_service import KubernetesService, _window_to_hours


class TestWindowToHours:
    """Tests for window string → hours conversion."""

    def test_hours(self):
        assert _window_to_hours("1h") == 1.0
        assert _window_to_hours("6h") == 6.0
        assert _window_to_hours("24h") == 24.0

    def test_days(self):
        assert _window_to_hours("1d") == 24.0
        assert _window_to_hours("7d") == 168.0

    def test_invalid_fallback(self):
        assert _window_to_hours("bad") == 24.0


class TestKubernetesServiceMock:
    """Tests for KubernetesService using mock data fallbacks."""

    @pytest.fixture()
    def service(self):
        with patch("app.services.kubernetes_service.settings") as mock_settings:
            mock_settings.prometheus_url = "http://prometheus:9090"
            mock_settings.k8s_cpu_hourly_rate = 0.04
            mock_settings.k8s_memory_hourly_rate = 0.004
            svc = KubernetesService.__new__(KubernetesService)
            svc.prom = MagicMock()
            svc.cpu_hourly_rate = 0.04
            svc.memory_hourly_rate = 0.004
            return svc

    @pytest.mark.asyncio
    async def test_namespace_costs_fallback(self, service: KubernetesService):
        """When Prometheus is unreachable, returns mock data."""
        service.is_available = AsyncMock(return_value=False)
        result = await service.get_namespace_costs("24h")

        assert isinstance(result, list)
        assert len(result) > 0
        first = result[0]
        assert "namespace" in first
        assert "cost" in first
        assert "cpu_cost" in first
        assert "memory_cost" in first
        assert "network_cost" in first

    @pytest.mark.asyncio
    async def test_pod_costs_fallback(self, service: KubernetesService):
        """Pod drill-down returns mock data when Prometheus is down."""
        service.is_available = AsyncMock(return_value=False)
        result = await service.get_pod_costs("default", "24h")

        assert isinstance(result, list)
        assert len(result) > 0
        assert "pod" in result[0]
        assert "namespace" in result[0]
        assert "cost" in result[0]
        assert result[0]["namespace"] == "default"

    @pytest.mark.asyncio
    async def test_namespace_trend_fallback(self, service: KubernetesService):
        """Trend returns mock data when Prometheus is unreachable."""
        service.is_available = AsyncMock(return_value=False)
        result = await service.get_namespace_trend(days=3)

        assert isinstance(result, list)
        assert len(result) == 3
        entry = result[0]
        assert "timestamp" in entry
        assert "namespaces" in entry
        for ns_data in entry["namespaces"].values():
            assert "cost" in ns_data
            assert "cpu_cost" in ns_data

    @pytest.mark.asyncio
    async def test_label_costs_fallback(self, service: KubernetesService):
        """Label-based costs return mock data when Prometheus is down."""
        service.is_available = AsyncMock(return_value=False)
        result = await service.get_label_costs(label="app", window="24h")

        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]["label"] == "app"
        assert "value" in result[0]
        assert "cost" in result[0]

    @pytest.mark.asyncio
    async def test_namespace_costs_sorted_desc(self, service: KubernetesService):
        """Results should be sorted by cost descending."""
        service.is_available = AsyncMock(return_value=False)
        result = await service.get_namespace_costs("24h")

        costs = [r["cost"] for r in result]
        assert costs == sorted(costs, reverse=True)
