"""
CloudPulse AI - Cost Service
API router aggregating all endpoints.
"""
from fastapi import APIRouter

from app.api import costs, health, cloud_accounts

api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(cloud_accounts.router, prefix="/accounts", tags=["Cloud Accounts"])
api_router.include_router(costs.router, prefix="/costs", tags=["Costs"])
