"""
CloudPulse AI - Cost Service
API router aggregating all endpoints.
"""
from fastapi import APIRouter

from app.api import auth, cloud_accounts, costs, health, chat, kubernetes, admin

api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(cloud_accounts.router, prefix="/accounts", tags=["Cloud Accounts"])
api_router.include_router(costs.router, prefix="/costs", tags=["Costs"])
api_router.include_router(chat.router, prefix="/chat", tags=["AI Chat"])
api_router.include_router(kubernetes.router, prefix="/kubernetes", tags=["Kubernetes"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
