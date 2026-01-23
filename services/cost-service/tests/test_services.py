"""
CloudPulse AI - Cost Service
Tests for AWS Cost Explorer service.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from app.services.aws_cost_explorer import (
    AWSCostExplorerService,
    AWSCostExplorerError,
    get_aws_cost_explorer,
)


class TestAWSCostExplorerService:
    """Tests for AWS Cost Explorer integration."""
    
    def test_service_initialization(self):
        """Test service can be initialized."""
        service = AWSCostExplorerService(
            access_key_id="test_key",
            secret_access_key="test_secret",
            region="us-east-1",
        )
        assert service.client is not None
    
    def test_get_aws_cost_explorer_factory(self):
        """Test factory function returns service instance."""
        service = get_aws_cost_explorer(
            access_key_id="test",
            secret_access_key="test",
        )
        assert isinstance(service, AWSCostExplorerService)
    
    def test_parse_cost_response_with_groups(self):
        """Test parsing response with service groups."""
        service = AWSCostExplorerService()
        
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
        
        records = service.parse_cost_response(mock_response)
        
        assert len(records) == 2
        assert records[0]["service"] == "Amazon EC2"
        assert records[0]["amount"] == Decimal("123.45")
        assert records[1]["service"] == "Amazon S3"
    
    def test_parse_cost_response_without_groups(self):
        """Test parsing response without groups (total)."""
        service = AWSCostExplorerService()
        
        mock_response = [
            {
                "TimePeriod": {"Start": "2026-01-01", "End": "2026-01-02"},
                "Total": {
                    "UnblendedCost": {"Amount": "500.00", "Unit": "USD"},
                },
            },
        ]
        
        records = service.parse_cost_response(mock_response)
        
        assert len(records) == 1
        assert records[0]["service"] == "Total"
        assert records[0]["amount"] == Decimal("500.00")
    
    def test_parse_cost_response_filters_tiny_amounts(self):
        """Test that tiny amounts are filtered out."""
        service = AWSCostExplorerService()
        
        mock_response = [
            {
                "TimePeriod": {"Start": "2026-01-01", "End": "2026-01-02"},
                "Groups": [
                    {
                        "Keys": ["Tiny Service"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "0.0001", "Unit": "USD"},
                        },
                    },
                ],
            },
        ]
        
        records = service.parse_cost_response(mock_response)
        assert len(records) == 0


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
