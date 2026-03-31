"""
CloudPulse AI - Cost Service
Unit tests for core modules.
"""
import pytest
from datetime import datetime
from decimal import Decimal

from app.core.config import Settings, get_settings


class TestSettings:
    """Tests for Settings configuration."""
    
    def test_default_settings(self):
        """Test default settings values."""
        settings = get_settings()
        assert settings.app_name == "CloudPulse AI - Cost Service"
        assert settings.environment == "development"
        assert settings.api_prefix == "/api/v1"
    
    def test_settings_singleton(self):
        """Test settings is cached (singleton)."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
    
    def test_database_url_format(self):
        """Test database URL is properly formatted."""
        settings = get_settings()
        assert "postgresql" in str(settings.database_url)
    
    def test_redis_url_format(self):
        """Test Redis URL is properly formatted."""
        settings = get_settings()
        assert "redis" in str(settings.redis_url)


class TestSchemas:
    """Tests for Pydantic schemas."""
    
    def test_organization_create_validation(self):
        """Test OrganizationCreate schema validation."""
        from app.schemas import OrganizationCreate
        
        org = OrganizationCreate(name="Test Org", slug="test-org")
        assert org.name == "Test Org"
        assert org.slug == "test-org"
    
    def test_organization_create_invalid_slug(self):
        """Test OrganizationCreate rejects invalid slug."""
        from app.schemas import OrganizationCreate
        
        with pytest.raises(ValueError):
            OrganizationCreate(name="Test", slug="Invalid Slug!")
    
    def test_cloud_account_create(self):
        """Test CloudAccountCreate schema."""
        from app.schemas import CloudAccountCreate, CloudProvider
        
        account = CloudAccountCreate(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            account_name="Test Account",
        )
        assert account.provider == CloudProvider.AWS
        assert account.account_id == "123456789012"
    
    def test_cost_record_create(self):
        """Test CostRecordCreate schema."""
        from app.schemas import CostRecordCreate, CostGranularity
        
        record = CostRecordCreate(
            date=datetime.now(),
            granularity=CostGranularity.DAILY,
            service="Amazon EC2",
            amount=Decimal("123.45"),
        )
        assert record.service == "Amazon EC2"
        assert record.amount == Decimal("123.45")
    
    def test_budget_create_validation(self):
        """Test BudgetCreate with validation."""
        from app.schemas import BudgetCreate
        
        budget = BudgetCreate(
            name="Monthly Budget",
            amount=Decimal("1000.00"),
            period="monthly",
        )
        assert budget.name == "Monthly Budget"
        assert budget.alert_thresholds == [50, 80, 100]
    
    def test_budget_create_invalid_amount(self):
        """Test BudgetCreate rejects negative amount."""
        from app.schemas import BudgetCreate
        
        with pytest.raises(ValueError):
            BudgetCreate(
                name="Test",
                amount=Decimal("-100"),
            )
    
    def test_cost_summary_schema(self):
        """Test CostSummary schema."""
        from app.schemas import CostSummary
        
        summary = CostSummary(
            total_cost=Decimal("5000.00"),
            period_start=datetime.now(),
            period_end=datetime.now(),
            by_service={"EC2": Decimal("3000"), "RDS": Decimal("2000")},
        )
        assert summary.total_cost == Decimal("5000.00")
        assert summary.currency == "USD"
    
    def test_anomaly_severity_enum(self):
        """Test AnomalySeverity enum values."""
        from app.schemas import AnomalySeverity
        
        assert AnomalySeverity.LOW == "low"
        assert AnomalySeverity.CRITICAL == "critical"


class TestModels:
    """Tests for database models."""
    
    def test_organization_model(self):
        """Test Organization model attributes."""
        from app.models import Organization
        
        assert hasattr(Organization, "id")
        assert hasattr(Organization, "name")
        assert hasattr(Organization, "slug")
        assert hasattr(Organization, "is_active")
    
    def test_cloud_account_model(self):
        """Test CloudAccount model relationships."""
        from app.models import CloudAccount
        
        assert hasattr(CloudAccount, "organization_id")
        assert hasattr(CloudAccount, "provider")
        assert hasattr(CloudAccount, "cost_records")
    
    def test_cost_record_model(self):
        """Test CostRecord model attributes."""
        from app.models import CostRecord
        
        assert hasattr(CostRecord, "cloud_account_id")
        assert hasattr(CostRecord, "date")
        assert hasattr(CostRecord, "service")
        assert hasattr(CostRecord, "amount")
    
    def test_budget_model(self):
        """Test Budget model defaults."""
        from app.models import Budget
        
        assert hasattr(Budget, "alert_thresholds")
        assert hasattr(Budget, "filters")
    
    def test_cost_anomaly_model(self):
        """Test CostAnomaly model attributes."""
        from app.models import CostAnomaly
        
        assert hasattr(CostAnomaly, "severity")
        assert hasattr(CostAnomaly, "deviation_percent")
        assert hasattr(CostAnomaly, "recommendations")
    
    def test_cloud_provider_enum(self):
        """Test CloudProvider enum."""
        from app.models import CloudProvider
        
        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.GCP.value == "gcp"
        assert CloudProvider.AZURE.value == "azure"


class TestSecurityHelpers:
    """Tests for token and credential security helpers."""

    def test_refresh_token_contains_refresh_type(self):
        """Refresh tokens should carry a dedicated token type."""
        from jose import jwt

        from app.core.security import create_refresh_token

        token = create_refresh_token("user-123", csrf_token="csrf-token")
        payload = jwt.get_unverified_claims(token)
        assert payload["type"] == "refresh"
        assert payload["csrf"] == "csrf-token"

    def test_encrypt_credentials_is_passthrough_without_key(self):
        """Credential encryption should be optional in local development."""
        from app.core.security import decrypt_credentials, encrypt_credentials

        credentials = {"access_key_id": "abc", "secret_access_key": "xyz"}
        stored = encrypt_credentials(credentials)
        assert stored == credentials
        assert decrypt_credentials(stored) == credentials
