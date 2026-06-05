"""Dashboard service placeholder."""
from typing import Dict

class DashboardService:
    def __init__(self):
        self.metrics: Dict = {}
    
    async def get_metrics(self) -> Dict:
        return self.metrics

dashboard_service = DashboardService()