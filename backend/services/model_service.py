"""Model service placeholder."""
from typing import Dict, List, Optional

class ModelService:
    def __init__(self):
        self.models: Dict = {}
    
    async def list_models(self) -> List[dict]:
        return list(self.models.values())

model_service = ModelService()