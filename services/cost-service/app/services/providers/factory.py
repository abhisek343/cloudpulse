"""
CloudPulse AI - Cost Service
Factory for creating Cost Providers.
"""
import logging
from datetime import datetime
from typing import Any

from app.services.providers.base import CostProvider
from app.services.providers.aws import AWSCostProvider
from app.services.providers.azure import AzureProvider
from app.services.providers.gcp import GCPProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory to get the correct Cost Provider instance."""
    
    _providers: dict[str, type[CostProvider]] = {
        "aws": AWSCostProvider,
        "azure": AzureProvider,
        "gcp": GCPProvider,
    }
    
    @classmethod
    def get_provider(cls, provider_type: str, credentials: dict[str, Any]) -> CostProvider:
        """
        Get a cost provider instance.
        
        Args:
            provider_type: 'aws', 'azure', or 'gcp'
            credentials: Dictionary of credentials
            
        Returns:
            Instance of CostProvider
            
        Raises:
            ValueError: If provider_type is not supported
        """
        provider_type = provider_type.lower()
        
        provider_class = cls._providers.get(provider_type)
        if provider_class is None:
            supported = ", ".join(cls._providers.keys())
            raise ValueError(f"Unsupported provider: {provider_type}. Supported: {supported}")
        
        return provider_class(credentials)
    
    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider types."""
        return list(cls._providers.keys())
