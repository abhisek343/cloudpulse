"""
CloudPulse AI - Cost Service
Terraform cost estimation API endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.core.logging import sanitize_error
from app.models import User
from app.services.terraform_service import estimate_plan, get_supported_resources

router = APIRouter()


class TerraformPlanRequest(BaseModel):
    """Request body containing terraform plan JSON output."""
    plan_json: dict = Field(..., description="Output of `terraform show -json <planfile>`")


class ResourceEstimate(BaseModel):
    address: str
    type: str
    name: str
    action: str
    monthly_cost: float | None = None
    previous_cost: float | None = None


class EstimateSummary(BaseModel):
    total_resources: int
    estimated_monthly_increase: float
    estimated_monthly_decrease: float
    net_monthly_delta: float
    unsupported_count: int


class TerraformEstimateResponse(BaseModel):
    resources: list[ResourceEstimate]
    summary: EstimateSummary
    unsupported_resources: list[str]


class SupportedResource(BaseModel):
    type: str
    provider: str
    description: str
    has_size_rates: bool


@router.post("/estimate", response_model=TerraformEstimateResponse)
async def estimate_terraform_plan(
    request: TerraformPlanRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Estimate monthly costs from a Terraform plan JSON."""
    try:
        result = estimate_plan(request.plan_json)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse plan: {sanitize_error(e)}")


@router.get("/supported-resources", response_model=list[SupportedResource])
async def list_supported_resources(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, str]]:
    """List all Terraform resource types supported for cost estimation."""
    return get_supported_resources()
