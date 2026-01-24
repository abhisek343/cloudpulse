"""
CloudPulse AI - Cost Service
Kubernetes Service for cost allocation via Prometheus.
"""
import logging
from typing import Any
from datetime import datetime

from prometheus_api_client import PrometheusConnect
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class KubernetesService:
    """
    Service for interacting with Prometheus to get Kubernetes metrics
    and attribute costs to Namespaces/Pods.
    """
    
    def __init__(self) -> None:
        self.prom = PrometheusConnect(url=settings.prometheus_url, disable_ssl=True)
        # Cost rates loaded from configuration
        self.cpu_hourly_rate = settings.k8s_cpu_hourly_rate
        self.memory_hourly_rate = settings.k8s_memory_hourly_rate

    def is_available(self) -> bool:
        try:
            return self.prom.check_prometheus_connection()
        except Exception as e:
            logger.warning(f"Prometheus connection check failed: {e}")
            return False

    def get_namespace_costs(self, window: str = "24h") -> list[dict[str, Any]]:
        """
        Calculate cost per namespace based on CPU usage.
        Formula: sum(container_cpu_usage_seconds_total) * CPU_RATE
        """
        if not self.is_available():
            logger.warning("Prometheus not available. Returning mock data.")
            return self._get_mock_data()

        try:
            # Query: Rate of CPU usage averaged over window, summed by namespace
            # We use '1d' or '1h' etc for the rate calculation context
            query = f'sum(rate(container_cpu_usage_seconds_total[{window}])) by (namespace)'
            
            # Get instantaneous vector
            result = self.prom.custom_query(query=query)
            
            costs = []
            for item in result:
                namespace = item["metric"].get("namespace")
                if not namespace:
                    continue
                    
                # usage_cores is the 'value' [timestamp, value]
                usage_cores = float(item["value"][1])
                
                # Simple Cost Model: cores * hourly_rate * 24 (if window is 1 day)
                # For simplicity, we assume the window defines the total duration we are looking at
                # If window is '24h', we estimate cost for that day
                hours = 24 if "d" in window or "24h" in window else 1
                
                cost = usage_cores * self.cpu_hourly_rate * hours
                
                costs.append({
                    "namespace": namespace,
                    "cost": round(cost, 4),
                    "cpu_cores": round(usage_cores, 4)
                })
                
            return sorted(costs, key=lambda x: x["cost"], reverse=True)

        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return self._get_mock_data()

    def _get_mock_data(self) -> list[dict[str, Any]]:
        """Fallback data for demonstration if Prometheus is unreachable."""
        return [
            {"namespace": "default", "cost": 12.50, "cpu_cores": 4.5},
            {"namespace": "kube-system", "cost": 8.20, "cpu_cores": 2.8},
            {"namespace": "monitoring", "cost": 5.40, "cpu_cores": 1.9},
            {"namespace": "payment-service", "cost": 15.30, "cpu_cores": 5.2},
            {"namespace": "frontend", "cost": 3.10, "cpu_cores": 1.1},
        ]


# Singleton
_k8s_service: KubernetesService | None = None


def get_kubernetes_service() -> KubernetesService:
    global _k8s_service
    if _k8s_service is None:
        _k8s_service = KubernetesService()
    return _k8s_service
