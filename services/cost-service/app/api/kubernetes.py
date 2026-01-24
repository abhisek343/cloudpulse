"""
CloudPulse AI - Cost Service
Kubernetes API endpoints.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.services.kubernetes_service import KubernetesService, get_kubernetes_service

router = APIRouter()


@router.get("/namespaces/cost")
async def get_namespace_costs(
    window: str = "24h",
    settings: Settings = Depends(get_settings),
    k8s_service: KubernetesService = Depends(get_kubernetes_service),
) -> list[dict[str, Any]]:
    """
    Get cost breakdown by Kubernetes Namespace.
    
    Returns a list of namespaces sorted by cost descending.
    """
    if not settings.prometheus_url:
        raise HTTPException(
            status_code=503,
            detail="Prometheus URL not configured."
        )

    try:
        return k8s_service.get_namespace_costs(window=window)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch Kubernetes metrics: {str(e)}"
        )
