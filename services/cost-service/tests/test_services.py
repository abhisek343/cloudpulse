from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

import app.services.providers.azure as azure_provider_module
import app.services.providers.gcp as gcp_provider_module
from app.services.providers.aws import AWSCostProvider
from app.services.providers.azure import AzureProvider
from app.services.providers.demo import DemoProvider
from app.services.providers.factory import ProviderFactory
from app.services.providers.gcp import GCPProvider


class TestAWSCostProvider:
    """Tests for AWS Cost Provider."""
    
    @patch("app.services.providers.aws.boto3.client")
    def test_provider_initialization(self, mock_boto_client):
        """Test provider can be initialized."""
        mock_boto_client.return_value = MagicMock()
        
        provider = AWSCostProvider({
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
        })
        assert provider.client is not None
        mock_boto_client.assert_called_once()
    
    def test_provider_factory_defaults_to_demo(self):
        """Test provider factory uses demo provider by default for safety."""
        provider = ProviderFactory.get_provider("aws", {})
        assert isinstance(provider, DemoProvider)
        assert provider.simulated_provider == "aws"

    def test_provider_factory_can_return_live_aws(self, monkeypatch):
        """Test factory returns AWS provider when live sync is explicitly enabled."""
        import app.services.providers.factory as provider_factory

        monkeypatch.setattr(provider_factory.settings, "cloud_sync_mode", "live")
        monkeypatch.setattr(provider_factory.settings, "allow_live_cloud_sync", True)

        with patch("app.services.providers.aws.boto3.client"):
            provider = ProviderFactory.get_provider(
                "aws",
                {"mode": "live", "access_key_id": "test", "secret_access_key": "test"},
            )
            assert isinstance(provider, AWSCostProvider)

    def test_provider_factory_returns_azure(self):
        """Test factory function returns Azure provider instance."""
        provider = ProviderFactory.get_provider("azure", {})
        assert isinstance(provider, DemoProvider)
        assert provider.simulated_provider == "azure"
    
    def test_provider_factory_returns_gcp(self):
        """Test factory function returns GCP provider instance."""
        provider = ProviderFactory.get_provider("gcp", {})
        assert isinstance(provider, DemoProvider)
        assert provider.simulated_provider == "gcp"

    def test_provider_factory_returns_explicit_demo(self):
        """Test explicit demo provider returns demo provider instance."""
        provider = ProviderFactory.get_provider("demo", {"scenario": "startup"})
        assert isinstance(provider, DemoProvider)
        assert provider.scenario == "startup"

    def test_azure_provider_uses_env_defaults(self, monkeypatch):
        """Azure live provider should fall back to env-backed settings."""
        monkeypatch.setattr(azure_provider_module.settings, "azure_subscription_id", "sub-123")
        monkeypatch.setattr(azure_provider_module.settings, "azure_tenant_id", "tenant-123")
        monkeypatch.setattr(azure_provider_module.settings, "azure_client_id", "client-123")
        monkeypatch.setattr(azure_provider_module.settings, "azure_client_secret", "secret-123")

        provider = AzureProvider({})

        assert provider.subscription_id == "sub-123"
        assert provider.tenant_id == "tenant-123"
        assert provider.client_id == "client-123"
        assert provider.client_secret == "secret-123"

    def test_gcp_provider_uses_env_json_defaults(self, monkeypatch):
        """GCP live provider should parse JSON credentials from env-backed settings."""
        monkeypatch.setattr(gcp_provider_module.settings, "gcp_project_id", "proj-123")
        monkeypatch.setattr(gcp_provider_module.settings, "gcp_billing_account_id", "billing-123")
        monkeypatch.setattr(
            gcp_provider_module.settings,
            "gcp_billing_export_table",
            "billing.dataset.gcp_export",
        )
        monkeypatch.setattr(
            gcp_provider_module.settings,
            "gcp_service_account_json",
            '{"type":"service_account","project_id":"proj-123","client_email":"demo@example.com"}',
        )
        monkeypatch.setattr(gcp_provider_module.settings, "gcp_service_account_file", None)

        provider = GCPProvider({})

        assert provider.project_id == "proj-123"
        assert provider.billing_account_id == "billing-123"
        assert provider.billing_export_table == "billing.dataset.gcp_export"
        assert provider.service_account_info["type"] == "service_account"

    def test_gcp_provider_normalizes_bigquery_rows(self):
        """GCP provider should map BigQuery export rows into cost records."""
        provider = GCPProvider(
            {
                "service_account_json": {
                    "type": "service_account",
                    "project_id": "proj-123",
                    "client_email": "demo@example.com",
                },
                "billing_export_table": "billing.dataset.gcp_export",
            }
        )

        rows = [
            {
                "usage_date": datetime(2026, 1, 1),
                "service_name": "Compute Engine",
                "region_name": "us-central1",
                "total_cost": "12.50",
                "currency": "USD",
            },
            {
                "usage_date": datetime(2026, 1, 2),
                "service_name": "Cloud Storage",
                "region_name": None,
                "total_cost": "0",
                "currency": "USD",
            },
        ]

        records = provider._parse_response(rows)

        assert len(records) == 1
        assert records[0]["service"] == "Compute Engine"
        assert records[0]["region"] == "us-central1"
        assert records[0]["amount"] == Decimal("12.50")

    def test_provider_factory_blocks_live_sync_when_disabled(self, monkeypatch):
        """Test live provider requests are rejected when live sync is disabled."""
        import app.services.providers.factory as provider_factory

        monkeypatch.setattr(provider_factory.settings, "cloud_sync_mode", "demo")
        monkeypatch.setattr(provider_factory.settings, "allow_live_cloud_sync", False)

        with pytest.raises(ValueError, match="Live cloud sync is disabled"):
            ProviderFactory.get_provider("aws", {"mode": "live"})
    
    def test_provider_factory_raises_on_unknown(self):
        """Test factory raises error for unknown provider."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            ProviderFactory.get_provider("unknown", {})
    
    @patch("app.services.providers.aws.boto3.client")
    def test_parse_response_with_groups(self, mock_boto_client):
        """Test parsing response with service groups."""
        mock_boto_client.return_value = MagicMock()
        provider = AWSCostProvider({})
        
        mock_response = [
            {
                "TimePeriod": {"Start": "2026-01-01", "End": "2026-01-02"},
                "Groups": [
                    {
                        "Keys": ["Amazon EC2"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "123.45", "Unit": "USD"},
                            "UsageQuantity": {"Amount": "100", "Unit": "N/A"},
                        },
                    },
                    {
                        "Keys": ["Amazon S3"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "45.67", "Unit": "USD"},
                            "UsageQuantity": {"Amount": "50", "Unit": "N/A"},
                        },
                    },
                ],
            },
        ]
        
        records = provider._parse_response(mock_response)
        
        assert len(records) == 2
        assert records[0]["service"] == "Amazon EC2"
        assert records[0]["amount"] == Decimal("123.45")
        assert records[1]["service"] == "Amazon S3"
    
    @patch("app.services.providers.aws.boto3.client")
    def test_parse_response_filters_zero_amounts(self, mock_boto_client):
        """Test that zero/negative amounts are filtered out."""
        mock_boto_client.return_value = MagicMock()
        provider = AWSCostProvider({})
        
        mock_response = [
            {
                "TimePeriod": {"Start": "2026-01-01", "End": "2026-01-02"},
                "Groups": [
                    {
                        "Keys": ["Zero Service"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "0.00", "Unit": "USD"},
                        },
                    },
                    {
                        "Keys": ["Valid Service"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "10.00", "Unit": "USD"},
                        },
                    },
                ],
            },
        ]
        
        records = provider._parse_response(mock_response)
        assert len(records) == 1
        assert records[0]["service"] == "Valid Service"


class TestCostSyncService:
    """Tests for cost sync service."""

    def test_sync_result_structure(self):
        """Test sync result has expected structure."""
        expected_keys = [
            "account_id",
            "records_created",
            "records_updated",
            "total_records",
            "sync_period",
        ]

        mock_result = {
            "account_id": "123",
            "records_created": 10,
            "records_updated": 5,
            "total_records": 15,
            "sync_period": {"start": "2026-01-01", "end": "2026-01-10"},
        }
        
        for key in expected_keys:
            assert key in mock_result


class TestDemoProvider:
    """Tests for demo provider behavior."""

    @pytest.mark.asyncio
    async def test_demo_provider_generates_cost_data(self):
        provider = DemoProvider(
            provider_type="demo",
            config={"scenario": "saas", "seed": 7, "simulated_provider": "aws"},
        )

        start = datetime(2026, 1, 1)
        end = start + timedelta(days=2)
        records = await provider.get_cost_data(start, end)

        assert len(records) == 15
        assert all(record["amount"] > Decimal("0") for record in records)
        assert {record["service"] for record in records}
        assert all(record["record_metadata"]["mode"] == "demo" for record in records)
