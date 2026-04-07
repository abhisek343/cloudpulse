"""
CloudPulse AI - Cost Service
Kubernetes Service for cost allocation via Prometheus.
"""
import logging
import re
from typing import Any

from anyio import to_thread
from prometheus_api_client import PrometheusConnect
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_WINDOW_RE = re.compile(r"^(\d+)(h|d)$")


def _window_to_hours(window: str) -> float:
    m = _WINDOW_RE.match(window)
    if not m:
        return 24.0
    value, unit = int(m.group(1)), m.group(2)
    return value * 24.0 if unit == "d" else float(value)


class KubernetesService:
    """
    Kubernetes cost attribution via Prometheus.

    Computes CPU, memory, and network costs per namespace/pod using
    live metrics.  Falls back to mock data when Prometheus is unreachable.
    """

    def __init__(self) -> None:
        self.prom = PrometheusConnect(url=settings.prometheus_url, disable_ssl=True)
        self.cpu_hourly_rate = settings.k8s_cpu_hourly_rate
        self.memory_hourly_rate = settings.k8s_memory_hourly_rate

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    async def is_available(self) -> bool:
        try:
            return await to_thread.run_sync(lambda: self.prom.check_prometheus_connection())
        except Exception as e:
            logger.warning(f"Prometheus connection check failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Namespace-level costs (CPU + memory + network)
    # ------------------------------------------------------------------

    async def get_namespace_costs(self, window: str = "24h") -> list[dict[str, Any]]:
        """Cost breakdown per namespace including CPU, memory, and network."""
        if not await self.is_available():
            logger.warning("Prometheus not available. Returning mock data.")
            return self._get_mock_data()

        hours = _window_to_hours(window)

        try:
            cpu_q = f"sum(rate(container_cpu_usage_seconds_total[{window}])) by (namespace)"
            mem_q = f"sum(avg_over_time(container_memory_working_set_bytes[{window}])) by (namespace)"
            net_rx_q = f"sum(rate(container_network_receive_bytes_total[{window}])) by (namespace)"
            net_tx_q = f"sum(rate(container_network_transmit_bytes_total[{window}])) by (namespace)"

            cpu_res, mem_res, net_rx_res, net_tx_res = await to_thread.run_sync(
                lambda: (
                    self.prom.custom_query(query=cpu_q),
                    self.prom.custom_query(query=mem_q),
                    self.prom.custom_query(query=net_rx_q),
                    self.prom.custom_query(query=net_tx_q),
                )
            )

            def _to_map(result: list) -> dict[str, float]:
                out: dict[str, float] = {}
                for item in result:
                    ns = item["metric"].get("namespace")
                    if ns:
                        out[ns] = float(item["value"][1])
                return out

            cpu_map = _to_map(cpu_res)
            mem_map = _to_map(mem_res)
            net_rx_map = _to_map(net_rx_res)
            net_tx_map = _to_map(net_tx_res)

            all_ns = sorted(set(cpu_map) | set(mem_map))

            costs: list[dict[str, Any]] = []
            for ns in all_ns:
                cpu_cores = cpu_map.get(ns, 0.0)
                mem_bytes = mem_map.get(ns, 0.0)
                mem_gb = mem_bytes / (1024 ** 3)
                net_bytes = net_rx_map.get(ns, 0.0) + net_tx_map.get(ns, 0.0)
                net_gb = (net_bytes * hours * 3600) / (1024 ** 3)

                cpu_cost = cpu_cores * self.cpu_hourly_rate * hours
                mem_cost = mem_gb * self.memory_hourly_rate * hours
                # Simple network cost: $0.01/GB
                net_cost = net_gb * 0.01
                total = cpu_cost + mem_cost + net_cost

                costs.append({
                    "namespace": ns,
                    "cost": round(total, 4),
                    "cpu_cost": round(cpu_cost, 4),
                    "memory_cost": round(mem_cost, 4),
                    "network_cost": round(net_cost, 4),
                    "cpu_cores": round(cpu_cores, 4),
                    "memory_gb": round(mem_gb, 4),
                    "network_gb": round(net_gb, 4),
                })

            return sorted(costs, key=lambda x: x["cost"], reverse=True)

        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return self._get_mock_data()

    # ------------------------------------------------------------------
    # Pod-level drill-down
    # ------------------------------------------------------------------

    async def get_pod_costs(self, namespace: str, window: str = "24h") -> list[dict[str, Any]]:
        """Cost breakdown per pod within a namespace."""
        if not await self.is_available():
            return self._get_mock_pod_data(namespace)

        hours = _window_to_hours(window)

        try:
            cpu_q = (
                f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[{window}])) by (pod)'
            )
            mem_q = (
                f'sum(avg_over_time(container_memory_working_set_bytes{{namespace="{namespace}"}}[{window}])) by (pod)'
            )

            cpu_res, mem_res = await to_thread.run_sync(
                lambda: (
                    self.prom.custom_query(query=cpu_q),
                    self.prom.custom_query(query=mem_q),
                )
            )

            def _to_map(result: list) -> dict[str, float]:
                out: dict[str, float] = {}
                for item in result:
                    pod = item["metric"].get("pod")
                    if pod:
                        out[pod] = float(item["value"][1])
                return out

            cpu_map = _to_map(cpu_res)
            mem_map = _to_map(mem_res)
            all_pods = sorted(set(cpu_map) | set(mem_map))

            pods: list[dict[str, Any]] = []
            for pod in all_pods:
                cpu_cores = cpu_map.get(pod, 0.0)
                mem_gb = mem_map.get(pod, 0.0) / (1024 ** 3)
                cpu_cost = cpu_cores * self.cpu_hourly_rate * hours
                mem_cost = mem_gb * self.memory_hourly_rate * hours

                pods.append({
                    "pod": pod,
                    "namespace": namespace,
                    "cpu_cores": round(cpu_cores, 4),
                    "memory_gb": round(mem_gb, 4),
                    "cpu_cost": round(cpu_cost, 4),
                    "memory_cost": round(mem_cost, 4),
                    "cost": round(cpu_cost + mem_cost, 4),
                })

            return sorted(pods, key=lambda x: x["cost"], reverse=True)

        except Exception as e:
            logger.error(f"Error querying pod costs: {e}")
            return self._get_mock_pod_data(namespace)

    # ------------------------------------------------------------------
    # Historical namespace cost trend
    # ------------------------------------------------------------------

    async def get_namespace_trend(
        self, days: int = 7, step: str = "1d",
    ) -> list[dict[str, Any]]:
        """Daily cost per namespace over the requested period."""
        if not await self.is_available():
            return self._get_mock_trend_data(days)

        try:
            import time as _time

            end = int(_time.time())
            start = end - days * 86400

            cpu_q = "sum(rate(container_cpu_usage_seconds_total[1h])) by (namespace)"
            mem_q = "sum(avg_over_time(container_memory_working_set_bytes[1h])) by (namespace)"

            cpu_res = await to_thread.run_sync(
                lambda: self.prom.custom_query_range(query=cpu_q, start_time=start, end_time=end, step=step)
            )
            mem_res = await to_thread.run_sync(
                lambda: self.prom.custom_query_range(query=mem_q, start_time=start, end_time=end, step=step)
            )

            # Build {timestamp -> {namespace -> {cpu, mem}}}
            from collections import defaultdict
            from datetime import datetime, timezone

            grid: dict[int, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"cpu": 0.0, "mem": 0.0}))

            for series in cpu_res:
                ns = series["metric"].get("namespace", "unknown")
                for ts, val in series["values"]:
                    grid[int(ts)][ns]["cpu"] = float(val)

            for series in mem_res:
                ns = series["metric"].get("namespace", "unknown")
                for ts, val in series["values"]:
                    grid[int(ts)][ns]["mem"] = float(val)

            trend: list[dict[str, Any]] = []
            for ts in sorted(grid):
                entry: dict[str, Any] = {
                    "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    "namespaces": {},
                }
                for ns, vals in grid[ts].items():
                    cpu_cost = vals["cpu"] * self.cpu_hourly_rate * 24
                    mem_cost = (vals["mem"] / (1024 ** 3)) * self.memory_hourly_rate * 24
                    entry["namespaces"][ns] = {
                        "cpu_cost": round(cpu_cost, 4),
                        "memory_cost": round(mem_cost, 4),
                        "cost": round(cpu_cost + mem_cost, 4),
                    }
                trend.append(entry)

            return trend

        except Exception as e:
            logger.error(f"Error querying namespace trend: {e}")
            return self._get_mock_trend_data(days)

    # ------------------------------------------------------------------
    # Label-based cost allocation
    # ------------------------------------------------------------------

    async def get_label_costs(
        self, label: str = "app", window: str = "24h",
    ) -> list[dict[str, Any]]:
        """Cost grouped by an arbitrary pod label (e.g. app, team)."""
        if not await self.is_available():
            return self._get_mock_label_data(label)

        hours = _window_to_hours(window)

        try:
            cpu_q = f"sum(rate(container_cpu_usage_seconds_total[{window}])) by (label_{label})"
            mem_q = f"sum(avg_over_time(container_memory_working_set_bytes[{window}])) by (label_{label})"

            cpu_res, mem_res = await to_thread.run_sync(
                lambda: (
                    self.prom.custom_query(query=cpu_q),
                    self.prom.custom_query(query=mem_q),
                )
            )

            def _to_map(result: list, lbl: str) -> dict[str, float]:
                out: dict[str, float] = {}
                for item in result:
                    val = item["metric"].get(lbl) or "unlabeled"
                    out[val] = float(item["value"][1])
                return out

            lbl_key = f"label_{label}"
            cpu_map = _to_map(cpu_res, lbl_key)
            mem_map = _to_map(mem_res, lbl_key)
            all_labels = sorted(set(cpu_map) | set(mem_map))

            items: list[dict[str, Any]] = []
            for lv in all_labels:
                cpu_cores = cpu_map.get(lv, 0.0)
                mem_gb = mem_map.get(lv, 0.0) / (1024 ** 3)
                cpu_cost = cpu_cores * self.cpu_hourly_rate * hours
                mem_cost = mem_gb * self.memory_hourly_rate * hours
                items.append({
                    "label": label,
                    "value": lv,
                    "cpu_cores": round(cpu_cores, 4),
                    "memory_gb": round(mem_gb, 4),
                    "cpu_cost": round(cpu_cost, 4),
                    "memory_cost": round(mem_cost, 4),
                    "cost": round(cpu_cost + mem_cost, 4),
                })

            return sorted(items, key=lambda x: x["cost"], reverse=True)

        except Exception as e:
            logger.error(f"Error querying label costs: {e}")
            return self._get_mock_label_data(label)

    # ------------------------------------------------------------------
    # Mock / fallback data
    # ------------------------------------------------------------------

    def _get_mock_data(self) -> list[dict[str, Any]]:
        """Fallback namespace data when Prometheus is unreachable."""
        return [
            {"namespace": "payment-service", "cost": 18.94, "cpu_cost": 12.48, "memory_cost": 6.14, "network_cost": 0.32, "cpu_cores": 5.2, "memory_gb": 6.4, "network_gb": 32.0},
            {"namespace": "default", "cost": 15.62, "cpu_cost": 10.80, "memory_cost": 4.50, "network_cost": 0.32, "cpu_cores": 4.5, "memory_gb": 4.7, "network_gb": 32.0},
            {"namespace": "kube-system", "cost": 10.34, "cpu_cost": 6.72, "memory_cost": 3.46, "network_cost": 0.16, "cpu_cores": 2.8, "memory_gb": 3.6, "network_gb": 16.0},
            {"namespace": "monitoring", "cost": 7.01, "cpu_cost": 4.56, "memory_cost": 2.28, "network_cost": 0.17, "cpu_cores": 1.9, "memory_gb": 2.4, "network_gb": 17.0},
            {"namespace": "frontend", "cost": 4.03, "cpu_cost": 2.64, "memory_cost": 1.23, "network_cost": 0.16, "cpu_cores": 1.1, "memory_gb": 1.3, "network_gb": 16.0},
        ]

    def _get_mock_pod_data(self, namespace: str) -> list[dict[str, Any]]:
        """Fallback pod data."""
        return [
            {"pod": f"{namespace}-api-7f8b9c-x1k2", "namespace": namespace, "cpu_cores": 1.2, "memory_gb": 2.1, "cpu_cost": 1.15, "memory_cost": 0.20, "cost": 1.35},
            {"pod": f"{namespace}-worker-5d4e3f-a9b8", "namespace": namespace, "cpu_cores": 0.8, "memory_gb": 1.5, "cpu_cost": 0.77, "memory_cost": 0.14, "cost": 0.91},
            {"pod": f"{namespace}-cache-2c1d0e-m3n4", "namespace": namespace, "cpu_cores": 0.3, "memory_gb": 0.5, "cpu_cost": 0.29, "memory_cost": 0.05, "cost": 0.34},
        ]

    def _get_mock_trend_data(self, days: int) -> list[dict[str, Any]]:
        """Fallback trend data."""
        from datetime import datetime, timedelta, timezone

        trend: list[dict[str, Any]] = []
        base = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        mock_ns = {"payment-service": 18.0, "default": 15.0, "kube-system": 10.0}
        for d in range(days):
            ts = base - timedelta(days=days - 1 - d)
            jitter = 1.0 + (d % 3 - 1) * 0.05
            entry: dict[str, Any] = {"timestamp": ts.isoformat(), "namespaces": {}}
            for ns, base_cost in mock_ns.items():
                cost = round(base_cost * jitter, 4)
                entry["namespaces"][ns] = {"cpu_cost": round(cost * 0.65, 4), "memory_cost": round(cost * 0.35, 4), "cost": cost}
            trend.append(entry)
        return trend

    def _get_mock_label_data(self, label: str) -> list[dict[str, Any]]:
        """Fallback label data."""
        return [
            {"label": label, "value": "checkout", "cpu_cores": 3.0, "memory_gb": 4.0, "cpu_cost": 2.88, "memory_cost": 0.38, "cost": 3.26},
            {"label": label, "value": "search", "cpu_cores": 2.1, "memory_gb": 3.2, "cpu_cost": 2.02, "memory_cost": 0.31, "cost": 2.33},
            {"label": label, "value": "unlabeled", "cpu_cores": 0.5, "memory_gb": 0.8, "cpu_cost": 0.48, "memory_cost": 0.08, "cost": 0.56},
        ]


# Singleton
_k8s_service: KubernetesService | None = None


def get_kubernetes_service() -> KubernetesService:
    global _k8s_service
    if _k8s_service is None:
        _k8s_service = KubernetesService()
    return _k8s_service
