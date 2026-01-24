"""
CloudPulse AI - Cost Service
Factory for creating Cost Providers.
"""
from typing import Dict, Any
from app.services.providers.base import CostProvider
from app.services.providers.aws import AWSCostProvider

# Stubs for other providers
class AzureCostProvider(CostProvider):
    def __init__(self, credentials: Dict[str, str]):
        self.credentials = credentials
        
    async def get_cost_data(self, start_date, end_date, granularity="DAILY"):
        # TODO: Implement Azure Cost Management API
        return []

    async def get_forecast(self, start_date, end_date, granularity="MONTHLY"):
        return {"total": 0, "unit": "USD", "forecast_by_time": []}

class GCPCostProvider(CostProvider):
    def __init__(self, credentials: Dict[str, str]):
        self.credentials = credentials
        
    async def get_cost_data(self, start_date, end_date, granularity="DAILY"):
        # TODO: Implement GCP Billing API
        return []

    async def get_forecast(self, start_date, end_date, granularity="MONTHLY"):
        return {"total": 0, "unit": "USD", "forecast_by_time": []}


class ProviderFactory:
    """Factory to get the correct Cost Provider instance."""
    
    @staticmethod
    def get_provider(provider_type: str, credentials: Dict[str, Any]) -> CostProvider:
        """
        Get a cost provider instance.
        
        Args:
            provider_type: 'aws', 'azure', or 'gcp'
            credentials: Dictionary of credentials
            
        Returns:
            Instance of CostProvider
        """
        provider_type = provider_type.lower()
        
        if provider_type == "aws":
            return AWSCostProvider(credentials)
        elif provider_type == "azure":
            return AzureCostProvider(credentials)
        elif provider_type == "gcp":
            return GCPCostProvider(credentials)
        else:
            raise ValueError(f"Unsupported provider: {provider_type}")
