"""A/B testing service for model versions."""
import json
import random
import sqlite3
from typing import Dict, List, Optional
from pathlib import Path
from persistence import init_db

DB_PATH = Path(__file__).parent.parent / "data" / "vllm_dashboard.db"

class ABTestService:
    def __init__(self):
        init_db()

    def _get_conn(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def create_version(
        self,
        model_id: str,
        version_name: str,
        config: Dict,
        traffic_weight: int = 100
    ) -> str:
        """Create a new model version for A/B testing."""
        metrics = json.dumps({
            "total_requests": 0,
            "successful_requests": 0,
            "avg_latency_ms": 0,
            "error_rate": 0
        })
        version_id = f"{model_id}_{version_name}"
        
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO model_versions (id, model_id, version_name, config, traffic_weight, is_active, metrics)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (version_id, model_id, version_name, json.dumps(config), traffic_weight, 1, metrics))
            conn.commit()
        
        return version_id

    def get_version(self, model_id: str, version_name: Optional[str] = None) -> Optional[Dict]:
        """Get a specific version or select based on traffic weighting."""
        if version_name:
            return self._load_version(f"{model_id}_{version_name}")
        
        versions = self.list_versions(model_id, active_only=True)
        if not versions:
            return None
        
        total_weight = sum(v.get("traffic_weight", 100) for v in versions)
        if total_weight == 0:
            return versions[0]
        
        pick = random.uniform(0, total_weight)
        current = 0
        for version in versions:
            current += version.get("traffic_weight", 100)
            if pick <= current:
                return version
        
        return versions[0]

    def _load_version(self, version_id: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM model_versions WHERE id = ?", (version_id,))
            row = c.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def _row_to_dict(self, row) -> Dict:
        return {
            "id": row["id"],
            "model_id": row["model_id"],
            "version_name": row["version_name"],
            "config": json.loads(row["config"]) if row["config"] else {},
            "traffic_weight": row["traffic_weight"],
            "is_active": bool(row["is_active"]),
            "metrics": json.loads(row["metrics"]) if row["metrics"] else {},
            "created_at": row["created_at"],
        }

    def list_versions(self, model_id: str, active_only: bool = False) -> List[Dict]:
        """List all versions for a model."""
        with self._get_conn() as conn:
            c = conn.cursor()
            query = "SELECT * FROM model_versions WHERE model_id = ?"
            if active_only:
                query += " AND is_active = 1"
            query += " ORDER BY version_name"
            c.execute(query, (model_id,))
            return [self._row_to_dict(row) for row in c.fetchall()]

    def update_traffic_weights(self, model_id: str, weights: Dict[str, int]):
        """Update traffic weights for versions."""
        with self._get_conn() as conn:
            c = conn.cursor()
            for version_name, weight in weights.items():
                version_id = f"{model_id}_{version_name}"
                c.execute("UPDATE model_versions SET traffic_weight = ? WHERE id = ?", (weight, version_id))
            conn.commit()

    def record_metrics(
        self,
        model_id: str,
        version_name: str,
        success: bool,
        latency_ms: float
    ):
        """Record performance metrics for a version."""
        version_id = f"{model_id}_{version_name}"
        version = self._load_version(version_id)
        if not version:
            return
        
        metrics = version.get("metrics", {})
        metrics["total_requests"] = metrics.get("total_requests", 0) + 1
        
        if success:
            metrics["successful_requests"] = metrics.get("successful_requests", 0) + 1
        
        old_avg = metrics.get("avg_latency_ms", 0)
        old_count = metrics.get("total_requests", 1) - 1
        if old_count > 0:
            metrics["avg_latency_ms"] = (old_avg * old_count + latency_ms) / metrics["total_requests"]
        else:
            metrics["avg_latency_ms"] = latency_ms
        
        total = metrics["total_requests"]
        if total > 0:
            metrics["error_rate"] = 1 - (metrics.get("successful_requests", 0) / total)
        else:
            metrics["error_rate"] = 0
        
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("UPDATE model_versions SET metrics = ? WHERE id = ?", (json.dumps(metrics), version_id))
            conn.commit()

    def get_best_version(self, model_id: str) -> Optional[Dict]:
        """Get the best performing version based on metrics."""
        versions = self.list_versions(model_id, active_only=True)
        if not versions:
            return None
        
        def score_version(v):
            metrics = v.get("metrics", {})
            error_rate = metrics.get("error_rate", 0.5)
            latency = metrics.get("avg_latency_ms", 1000)
            total_req = metrics.get("total_requests", 0)
            score = error_rate * 0.7 + (latency / 1000) * 0.3
            if total_req < 10:
                score += 0.5
            return score
        
        return min(versions, key=score_version)

    def promote_version(self, model_id: str, version_name: str, weight: int = 100):
        """Promote a version to primary (set high weight)."""
        with self._get_conn() as conn:
            c = conn.cursor()
            # Reduce other versions
            versions = self.list_versions(model_id, active_only=True)
            for v in versions:
                if v.get("version_name") != version_name:
                    new_w = max(10, v.get("traffic_weight", 100) // 2)
                    c.execute("UPDATE model_versions SET traffic_weight = ? WHERE id = ?", 
                             (new_w, f"{model_id}_{v['version_name']}"))
            
            # Set promoted version weight
            c.execute("UPDATE model_versions SET traffic_weight = ? WHERE id = ?", 
                     (weight, f"{model_id}_{version_name}"))
            conn.commit()

# Global instance
ab_test_service = ABTestService()
