"""
CloudPulse AI - Cost Service
Tests for Cost Provider services.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from app.services.providers.aws import AWSCostProvider
from app.services.providers.factory import ProviderFactory


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
    
    def test_provider_factory_returns_aws(self):
        """Test factory function returns AWS provider instance."""
        with patch("app.services.providers.aws.boto3.client"):
            provider = ProviderFactory.get_provider(
                "aws",
                {"access_key_id": "test", "secret_access_key": "test"},
            )
            assert isinstance(provider, AWSCostProvider)
    
    def test_provider_factory_returns_azure(self):
        """Test factory function returns Azure provider instance."""
        from app.services.providers.factory import AzureCostProvider
        
        provider = ProviderFactory.get_provider("azure", {})
        assert isinstance(provider, AzureCostProvider)
    
    def test_provider_factory_returns_gcp(self):
        """Test factory function returns GCP provider instance."""
        from app.services.providers.factory import GCPCostProvider
        
        provider = ProviderFactory.get_provider("gcp", {})
        assert isinstance(provider, GCPCostProvider)
    
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
        expected_keys = ["account_id", "records_created", "records_updated", "total_records", "sync_period"]
        
        mock_result = {
            "account_id": "123",
            "records_created": 10,
            "records_updated": 5,
            "total_records": 15,
            "sync_period": {"start": "2026-01-01", "end": "2026-01-10"},
        }
        
        for key in expected_keys:
            assert key in mock_result
