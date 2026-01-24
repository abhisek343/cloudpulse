"""
CloudPulse AI - Cost Service
Chat API endpoints for AI analyst features.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.services.llm_service import LLMService, get_llm_service
from app.services.providers.factory import ProviderFactory

router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat analysis."""
    message: str
    context_keys: dict = {} # e.g. {"provider": "aws", "account_id": "...", "region": "us-east-1"}
    time_range: str = "last_30_days"


class ChatResponse(BaseModel):
    """Response model for chat analysis."""
    response: str
    provider: str
    model: str


@router.post("/analyze", response_model=ChatResponse)
async def analyze_cost_chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
    llm_service: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    """
    Analyze cloud costs using AI based on user query.
    
    This endpoint:
    1. Fetches recent cost summary (context)
    2. Sends the context + user question to the LLM
    3. Returns the natural language response
    """
    if not settings.llm_api_key:
        raise HTTPException(
            status_code=503,
            detail="LLM service not configured. Please set LLM_API_KEY."
        )

    # 1. Fetch Context (Simple RAG-lite)
    # We use the Provider Factory to get the relevant cost data
    context = {}
    try:
        # Default to AWS if not specified (backward compatibility)
        provider_type = request.context_keys.get("provider", "aws")
        
        # In a real app, we'd look up credentials from DB using account_id
        # For this demo, we fall back to env vars (default settings)
        credentials = {} 
        
        provider = ProviderFactory.get_provider(provider_type, credentials)
        
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        # Get standardized cost data
        cost_data = await provider.get_cost_data(
            start_date=start_date, 
            end_date=end_date,
            granularity="DAILY"
        )
        
        # Calculate summaries for context
        total_cost = sum(r["amount"] for r in cost_data)
        
        # Top services
        services = {}
        for r in cost_data:
            s = r["service"]
            services[s] = services.get(s, 0.0) + float(r["amount"])
            
        top_services = sorted(
            [{"service": k, "amount": v} for k, v in services.items()], 
            key=lambda x: x["amount"], reverse=True
        )[:5]
        
        # Daily trend (last 7 days)
        # Group by date
        daily_map = {}
        for r in cost_data:
            d_str = r["date"].strftime("%Y-%m-%d")
            daily_map[d_str] = daily_map.get(d_str, 0.0) + float(r["amount"])
            
        daily_trend = sorted(
            [{"date": k, "amount": v} for k, v in daily_map.items()],
            key=lambda x: x["date"]
        )[-7:]
        
        context = {
            "period": "Last 30 Days",
            "provider": provider_type.upper(),
            "total_cost": float(total_cost),
            "top_services": top_services,
            "daily_trend": daily_trend
        }
        
    except Exception as e:
        context = {"error_fetching_data": str(e), "note": "Answering based on general knowledge only."}

    # 2. Get AI Response
    response_text = await llm_service.get_chat_response(
        message=request.message,
        context_data=context
    )
    
    return ChatResponse(
        response=response_text,
        provider=settings.llm_provider,
        model=settings.llm_model
    )
