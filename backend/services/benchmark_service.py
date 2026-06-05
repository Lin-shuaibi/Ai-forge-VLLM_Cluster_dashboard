"""Benchmark service placeholder."""
from typing import Dict, List, Optional

class BenchmarkService:
    def __init__(self):
        self.benchmarks: Dict = {}
    
    async def list_benchmarks(self) -> List[dict]:
        return list(self.benchmarks.values())

benchmark_service = BenchmarkService()