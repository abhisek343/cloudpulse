"""
CloudPulse AI - Cost Service
Tests for the Terraform cost estimation service and API.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.services.terraform_service import (
    estimate_plan,
    get_supported_resources,
    _estimate_resource_cost,
    RATE_TABLE,
)


# === Unit tests for terraform_service ===

class TestEstimateResourceCost:
    def test_known_instance_type(self):
        cost = _estimate_resource_cost("aws_instance", {"instance_type": "t3.micro"})
        assert cost == 7.59

    def test_unknown_instance_type_uses_default(self):
        cost = _estimate_resource_cost("aws_instance", {"instance_type": "x99.mega"})
        assert cost == 30.00

    def test_no_size_key(self):
        cost = _estimate_resource_cost("aws_s3_bucket", {})
        assert cost == 2.30

    def test_unsupported_resource_returns_none(self):
        cost = _estimate_resource_cost("aws_imaginary_thing", {})
        assert cost is None

    def test_azure_vm(self):
        cost = _estimate_resource_cost("azurerm_virtual_machine", {"vm_size": "Standard_B1s"})
        assert cost == 7.59

    def test_gcp_instance_with_full_path(self):
        cost = _estimate_resource_cost(
            "google_compute_instance",
            {"machine_type": "projects/my-proj/zones/us-central1-a/machineTypes/e2-micro"},
        )
        assert cost == 6.11


class TestEstimatePlan:
    def test_empty_plan(self):
        result = estimate_plan({"resource_changes": []})
        assert result["summary"]["total_resources"] == 0
        assert result["summary"]["net_monthly_delta"] == 0

    def test_create_resources(self):
        plan = {
            "resource_changes": [
                {
                    "address": "aws_instance.web",
                    "type": "aws_instance",
                    "name": "web",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {"instance_type": "t3.micro"},
                    },
                },
                {
                    "address": "aws_s3_bucket.data",
                    "type": "aws_s3_bucket",
                    "name": "data",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {},
                    },
                },
            ]
        }
        result = estimate_plan(plan)
        assert result["summary"]["total_resources"] == 2
        assert result["summary"]["estimated_monthly_increase"] == pytest.approx(7.59 + 2.30, rel=1e-2)
        assert result["summary"]["estimated_monthly_decrease"] == 0

    def test_delete_resource(self):
        plan = {
            "resource_changes": [
                {
                    "address": "aws_instance.old",
                    "type": "aws_instance",
                    "name": "old",
                    "change": {
                        "actions": ["delete"],
                        "before": {"instance_type": "m5.large"},
                        "after": None,
                    },
                },
            ]
        }
        result = estimate_plan(plan)
        assert result["summary"]["estimated_monthly_decrease"] == 69.12
        assert result["summary"]["net_monthly_delta"] == -69.12

    def test_update_resource(self):
        plan = {
            "resource_changes": [
                {
                    "address": "aws_instance.app",
                    "type": "aws_instance",
                    "name": "app",
                    "change": {
                        "actions": ["update"],
                        "before": {"instance_type": "t3.micro"},
                        "after": {"instance_type": "t3.large"},
                    },
                },
            ]
        }
        result = estimate_plan(plan)
        r = result["resources"][0]
        assert r["previous_cost"] == 7.59
        assert r["monthly_cost"] == 60.74
        assert result["summary"]["estimated_monthly_increase"] == pytest.approx(60.74 - 7.59, rel=1e-2)

    def test_noop_skipped(self):
        plan = {
            "resource_changes": [
                {
                    "address": "aws_instance.static",
                    "type": "aws_instance",
                    "name": "static",
                    "change": {"actions": ["no-op"], "before": {}, "after": {}},
                },
            ]
        }
        result = estimate_plan(plan)
        assert result["summary"]["total_resources"] == 0

    def test_unsupported_tracked(self):
        plan = {
            "resource_changes": [
                {
                    "address": "aws_iam_role.app",
                    "type": "aws_iam_role",
                    "name": "app",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {},
                    },
                },
            ]
        }
        result = estimate_plan(plan)
        assert "aws_iam_role.app" in result["unsupported_resources"]
        assert result["summary"]["unsupported_count"] == 1


class TestGetSupportedResources:
    def test_returns_all(self):
        supported = get_supported_resources()
        assert len(supported) == len(RATE_TABLE)
        types = {r["type"] for r in supported}
        assert "aws_instance" in types
        assert "google_compute_instance" in types


# === API endpoint tests ===

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_estimate_endpoint():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/terraform/estimate",
            json={
                "plan_json": {
                    "resource_changes": [
                        {
                            "address": "aws_instance.web",
                            "type": "aws_instance",
                            "name": "web",
                            "change": {
                                "actions": ["create"],
                                "before": None,
                                "after": {"instance_type": "t3.micro"},
                            },
                        }
                    ]
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_resources"] == 1


@pytest.mark.asyncio
async def test_supported_resources_endpoint():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/terraform/supported-resources")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert "type" in data[0]
