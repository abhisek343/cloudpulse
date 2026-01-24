"""
CloudPulse AI - Cost Service
Abstract Base Class for Cost Providers.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List

class CostProvider(ABC):
    """
    Abstract interface for Cloud Cost Providers (AWS, Azure, GCP).
    All provider implementations must inherit from this class.
    """
    
    @abstractmethod
    async def get_cost_data(
        self, 
        start_date: datetime, 
        end_date: datetime,
        granularity: str = "DAILY"
    ) -> List[Dict[str, Any]]:
        """
        Fetch normalized cost data for the given period.
        
        Returns:
            List of dicts with keys:
            - date: datetime
            - service: str
            - amount: Decimal
            - currency: str
            - usage_quantity: Decimal (optional)
        """
        pass

    @abstractmethod
    async def get_forecast(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY"
    ) -> Dict[str, Any]:
        """
        Get cost forecast.
        """
        pass
