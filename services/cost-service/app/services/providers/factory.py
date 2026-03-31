"""
CloudPulse AI - Cost Service
Factory for creating Cost Providers.
"""
import logging
from typing import Any

from app.core.config import get_settings
from app.services.providers.base import CostProvider
from app.services.providers.aws import AWSCostProvider
from app.services.providers.azure import AzureProvider
from app.services.providers.demo import DemoProvider
from app.services.providers.gcp import GCPProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class ProviderFactory:
    """Factory to get the correct Cost Provider instance."""
    
    _providers: dict[str, type[CostProvider]] = {
        "demo": DemoProvider,
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
        
        credentials = credentials or {}
        requested_mode = str(credentials.get("mode", settings.cloud_sync_mode)).lower()

        if provider_type not in cls._providers:
            supported = ", ".join(cls._providers.keys())
            raise ValueError(f"Unsupported provider: {provider_type}. Supported: {supported}")

        if provider_type == "demo":
            return DemoProvider(provider_type="demo", config=credentials)

        if requested_mode == "demo":
            return DemoProvider(provider_type=provider_type, config=credentials)

        if not settings.allow_live_cloud_sync:
            raise ValueError(
                "Live cloud sync is disabled. Set ALLOW_LIVE_CLOUD_SYNC=true and "
                "CLOUD_SYNC_MODE=live to use real provider APIs."
            )

        provider_class = cls._providers.get(provider_type)
        return provider_class(credentials)
    
    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider types."""
        return list(cls._providers.keys())
