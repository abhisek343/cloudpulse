"""
CloudPulse AI - Cost Service
Kubernetes API endpoints.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.services.kubernetes_service import KubernetesService, get_kubernetes_service

router = APIRouter()


@router.get("/namespaces/cost")
async def get_namespace_costs(
    window: str = Query("24h", pattern=r"^\d+(h|d)$"),
    settings: Settings = Depends(get_settings),
    k8s_service: KubernetesService = Depends(get_kubernetes_service),
) -> list[dict[str, Any]]:
    """
    Get cost breakdown by Kubernetes namespace.
    Includes CPU, memory, and network cost components.
    """
    if not settings.prometheus_url:
        raise HTTPException(status_code=503, detail="Prometheus URL not configured.")

    try:
        return await k8s_service.get_namespace_costs(window=window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Kubernetes metrics: {str(e)}")


@router.get("/namespaces/{namespace}/pods")
async def get_pod_costs(
    namespace: str,
    window: str = Query("24h", pattern=r"^\d+(h|d)$"),
    settings: Settings = Depends(get_settings),
    k8s_service: KubernetesService = Depends(get_kubernetes_service),
) -> list[dict[str, Any]]:
    """Get cost breakdown by pod within a namespace."""
    if not settings.prometheus_url:
        raise HTTPException(status_code=503, detail="Prometheus URL not configured.")

    try:
        return await k8s_service.get_pod_costs(namespace=namespace, window=window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pod metrics: {str(e)}")


@router.get("/namespaces/trend")
async def get_namespace_trend(
    days: int = Query(7, ge=1, le=30),
    settings: Settings = Depends(get_settings),
    k8s_service: KubernetesService = Depends(get_kubernetes_service),
) -> list[dict[str, Any]]:
    """Get historical daily cost per namespace."""
    if not settings.prometheus_url:
        raise HTTPException(status_code=503, detail="Prometheus URL not configured.")

    try:
        return await k8s_service.get_namespace_trend(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch namespace trend: {str(e)}")


@router.get("/namespaces/labels")
async def get_label_costs(
    label: str = Query("app", min_length=1, max_length=63),
    window: str = Query("24h", pattern=r"^\d+(h|d)$"),
    settings: Settings = Depends(get_settings),
    k8s_service: KubernetesService = Depends(get_kubernetes_service),
) -> list[dict[str, Any]]:
    """Get cost grouped by a pod label (e.g. app, team)."""
    if not settings.prometheus_url:
        raise HTTPException(status_code=503, detail="Prometheus URL not configured.")

    try:
        return await k8s_service.get_label_costs(label=label, window=window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch label costs: {str(e)}")
