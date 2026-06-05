"""Auto-scaling service for model deployments."""
import time
import json
import sqlite3
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from services.error_handlers import AppError

logger = logging.getLogger("vllm-dashboard")

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "vllm_dashboard.db"


class ScalingPolicy:
    """Scaling policy configuration."""

    def __init__(
        self,
        model_name: str,
        min_replicas: int = 1,
        max_replicas: int = 10,
        target_cpu_percent: int = 70,
        target_memory_percent: int = 80,
        target_qps: int = 100,
        scale_up_cooldown: int = 60,  # seconds
        scale_down_cooldown: int = 300,  # seconds
        scale_up_threshold: float = 1.2,  # 120% of target
        scale_down_threshold: float = 0.5,  # 50% of target
        scale_up_increment: int = 1,
        scale_down_increment: int = 1,
        enabled: bool = True
    ):
        self.model_name = model_name
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.target_cpu_percent = target_cpu_percent
        self.target_memory_percent = target_memory_percent
        self.target_qps = target_qps
        self.scale_up_cooldown = scale_up_cooldown
        self.scale_down_cooldown = scale_down_cooldown
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.scale_up_increment = scale_up_increment
        self.scale_down_increment = scale_down_increment
        self.enabled = enabled


class ScalingMetrics:
    """Scaling metrics collector."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.cpu_usage = []
        self.memory_usage = []
        self.request_rate = []
        self.latency = []
        self.error_rate = []
        self.timestamp = datetime.utcnow()

    def add_metrics(
        self,
        cpu_percent: float,
        memory_percent: float,
        requests_per_second: float,
        avg_latency_ms: float,
        error_rate: float
    ):
        """Add metrics for the current interval."""
        self.cpu_usage.append(cpu_percent)
        self.memory_usage.append(memory_percent)
        self.request_rate.append(requests_per_second)
        self.latency.append(avg_latency_ms)
        self.error_rate.append(error_rate)
        self.timestamp = datetime.utcnow()

        # Keep only last 10 minutes of data (assuming 10s intervals)
        max_points = 60
        if len(self.cpu_usage) > max_points:
            self.cpu_usage = self.cpu_usage[-max_points:]
            self.memory_usage = self.memory_usage[-max_points:]
            self.request_rate = self.request_rate[-max_points:]
            self.latency = self.latency[-max_points:]
            self.error_rate = self.error_rate[-max_points:]

    def get_average_metrics(self) -> Dict[str, float]:
        """Get average metrics over the collection period."""
        if not self.cpu_usage:
            return {}

        return {
            "cpu_percent": sum(self.cpu_usage) / len(self.cpu_usage),
            "memory_percent": sum(self.memory_usage) / len(self.memory_usage),
            "requests_per_second": sum(self.request_rate) / len(self.request_rate),
            "avg_latency_ms": sum(self.latency) / len(self.latency),
            "error_rate": sum(self.error_rate) / len(self.error_rate)
        }


class AutoScalingService:
    def __init__(self):
        self._init_db()
        self.policies: Dict[str, ScalingPolicy] = {}
        self.metrics: Dict[str, ScalingMetrics] = {}
        self.scaling_history: List[Dict[str, Any]] = []
        self.last_scale_up: Dict[str, datetime] = {}
        self.last_scale_down: Dict[str, datetime] = {}
        self.current_replicas: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread = None

    def _init_db(self):
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            c.execute("CREATE TABLE IF NOT EXISTS scaling_policies ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "model_name TEXT UNIQUE NOT NULL, "
                "min_replicas INTEGER DEFAULT 1, "
                "max_replicas INTEGER DEFAULT 10, "
                "target_cpu_percent INTEGER DEFAULT 70, "
                "target_memory_percent INTEGER DEFAULT 80, "
                "target_qps INTEGER DEFAULT 100, "
                "scale_up_cooldown INTEGER DEFAULT 60, "
                "scale_down_cooldown INTEGER DEFAULT 300, "
                "scale_up_threshold REAL DEFAULT 1.2, "
                "scale_down_threshold REAL DEFAULT 0.5, "
                "scale_up_increment INTEGER DEFAULT 1, "
                "scale_down_increment INTEGER DEFAULT 1, "
                "enabled BOOLEAN DEFAULT 1, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

            c.execute("CREATE TABLE IF NOT EXISTS scaling_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "model_name TEXT NOT NULL, "
                "old_replicas INTEGER NOT NULL, "
                "new_replicas INTEGER NOT NULL, "
                "reason TEXT NOT NULL, "
                "metrics TEXT, "
                "triggered_by TEXT DEFAULT 'auto', "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

            c.execute("CREATE TABLE IF NOT EXISTS scaling_metrics ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "model_name TEXT NOT NULL, "
                "cpu_percent REAL, "
                "memory_percent REAL, "
                "requests_per_second REAL, "
                "avg_latency_ms REAL, "
                "error_rate REAL, "
                "replica_count INTEGER, "
                "timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

            conn.commit()

    def start_monitoring(self):
        """Start the auto-scaling monitor."""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Auto-scaling monitor started")

    def stop_monitoring(self):
        """Stop the auto-scaling monitor."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Auto-scaling monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_all_models()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)

    def _check_all_models(self):
        """Check all models for scaling needs."""
        with self._lock:
            for model_name, policy in self.policies.items():
                if not policy.enabled:
                    continue

                # Get current metrics
                metrics = self.metrics.get(model_name)
                if not metrics:
                    continue

                avg_metrics = metrics.get_average_metrics()
                if not avg_metrics:
                    continue

                # Check if we need to scale
                self._evaluate_scaling(model_name, policy, avg_metrics)

    def _evaluate_scaling(self, model_name: str, policy: ScalingPolicy, metrics: Dict[str, float]):
        """Evaluate if scaling is needed."""
        current_replicas = self.current_replicas.get(model_name, 1)

        # Check scale up conditions
        should_scale_up = False
        scale_up_reason = ""

        # CPU usage check
        if metrics["cpu_percent"] > policy.target_cpu_percent * policy.scale_up_threshold:
            should_scale_up = True
            scale_up_reason = f"CPU usage {metrics['cpu_percent']:.1f}% > threshold {policy.target_cpu_percent * policy.scale_up_threshold:.1f}%"

        # Memory usage check
        elif metrics["memory_percent"] > policy.target_memory_percent * policy.scale_up_threshold:
            should_scale_up = True
            scale_up_reason = f"Memory usage {metrics['memory_percent']:.1f}% > threshold {policy.target_memory_percent * policy.scale_up_threshold:.1f}%"

        # QPS check
        elif metrics["requests_per_second"] > policy.target_qps * policy.scale_up_threshold:
            should_scale_up = True
            scale_up_reason = f"QPS {metrics['requests_per_second']:.1f} > threshold {policy.target_qps * policy.scale_up_threshold:.1f}"

        # Check scale down conditions
        should_scale_down = False
        scale_down_reason = ""

        # Only consider scale down if we have more than min replicas
        if current_replicas > policy.min_replicas:
            # CPU usage check
            if metrics["cpu_percent"] < policy.target_cpu_percent * policy.scale_down_threshold:
                should_scale_down = True
                scale_down_reason = f"CPU usage {metrics['cpu_percent']:.1f}% < threshold {policy.target_cpu_percent * policy.scale_down_threshold:.1f}%"

            # Memory usage check
            elif metrics["memory_percent"] < policy.target_memory_percent * policy.scale_down_threshold:
                should_scale_down = True
                scale_down_reason = f"Memory usage {metrics['memory_percent']:.1f}% < threshold {policy.target_memory_percent * policy.scale_down_threshold:.1f}%"

            # QPS check
            elif metrics["requests_per_second"] < policy.target_qps * policy.scale_down_threshold:
                should_scale_down = True
                scale_down_reason = f"QPS {metrics['requests_per_second']:.1f} < threshold {policy.target_qps * policy.scale_down_threshold:.1f}"

        # Check cooldown periods
        now = datetime.utcnow()
        last_scale_up = self.last_scale_up.get(model_name)
        last_scale_down = self.last_scale_down.get(model_name)

        if should_scale_up and current_replicas < policy.max_replicas:
            if last_scale_up and (now - last_scale_up).total_seconds() < policy.scale_up_cooldown:
                logger.debug(f"Skipping scale up for {model_name}: in cooldown")
                return

            new_replicas = min(current_replicas + policy.scale_up_increment, policy.max_replicas)
            self._perform_scale(model_name, current_replicas, new_replicas, scale_up_reason, metrics)
            self.last_scale_up[model_name] = now

        elif should_scale_down and current_replicas > policy.min_replicas:
            if last_scale_down and (now - last_scale_down).total_seconds() < policy.scale_down_cooldown:
                logger.debug(f"Skipping scale down for {model_name}: in cooldown")
                return

            new_replicas = max(current_replicas - policy.scale_down_increment, policy.min_replicas)
            self._perform_scale(model_name, current_replicas, new_replicas, scale_down_reason, metrics)
            self.last_scale_down[model_name] = now

    def _perform_scale(self, model_name: str, old_replicas: int, new_replicas: int,
                      reason: str, metrics: Dict[str, float]):
        """Perform the actual scaling operation."""
        logger.info(f"Scaling {model_name}: {old_replicas} -> {new_replicas} replicas. Reason: {reason}")

        # In a real implementation, this would:
        # 1. Update Kubernetes deployment
        # 2. Update load balancer configuration
        # 3. Update service discovery
        # For now, we just log and update our state

        self.current_replicas[model_name] = new_replicas

        # Record in history
        history_entry = {
            "model_name": model_name,
            "old_replicas": old_replicas,
            "new_replicas": new_replicas,
            "reason": reason,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.scaling_history.append(history_entry)

        # Save to database
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO scaling_history (model_name, old_replicas, new_replicas, reason, metrics) "
                "VALUES (?, ?, ?, ?, ?)",
                (model_name, old_replicas, new_replicas, reason, json.dumps(metrics)))
            conn.commit()

        logger.info(f"Scaled {model_name} to {new_replicas} replicas")

    def set_policy(self, policy: ScalingPolicy) -> Dict[str, Any]:
        """Set or update a scaling policy."""
        with self._lock:
            self.policies[policy.model_name] = policy

            # Initialize metrics if not exists
            if policy.model_name not in self.metrics:
                self.metrics[policy.model_name] = ScalingMetrics(policy.model_name)

            # Initialize current replicas if not exists
            if policy.model_name not in self.current_replicas:
                self.current_replicas[policy.model_name] = policy.min_replicas

            # Save to database
            with sqlite3.connect(str(DB_PATH)) as conn:
                c = conn.cursor()

                # Check if exists
                c.execute("SELECT id FROM scaling_policies WHERE model_name = ?", (policy.model_name,))
                exists = c.fetchone()

                if exists:
                    c.execute(
                        "UPDATE scaling_policies SET "
                        "min_replicas = ?, max_replicas = ?, target_cpu_percent = ?, "
                        "target_memory_percent = ?, target_qps = ?, scale_up_cooldown = ?, "
                        "scale_down_cooldown = ?, scale_up_threshold = ?, "
                        "scale_down_threshold = ?, scale_up_increment = ?, "
                        "scale_down_increment = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP "
                        "WHERE model_name = ?",
                        (policy.min_replicas, policy.max_replicas, policy.target_cpu_percent,
                         policy.target_memory_percent, policy.target_qps, policy.scale_up_cooldown,
                         policy.scale_down_cooldown, policy.scale_up_threshold,
                         policy.scale_down_threshold, policy.scale_up_increment,
                         policy.scale_down_increment, policy.enabled, policy.model_name))
                else:
                    c.execute(
                        "INSERT INTO scaling_policies (model_name, min_replicas, max_replicas, "
                        "target_cpu_percent, target_memory_percent, target_qps, "
                        "scale_up_cooldown, scale_down_cooldown, scale_up_threshold, "
                        "scale_down_threshold, scale_up_increment, scale_down_increment, enabled) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (policy.model_name, policy.min_replicas, policy.max_replicas,
                         policy.target_cpu_percent, policy.target_memory_percent, policy.target_qps,
                         policy.scale_up_cooldown, policy.scale_down_cooldown, policy.scale_up_threshold,
                         policy.scale_down_threshold, policy.scale_up_increment,
                         policy.scale_down_increment, policy.enabled))

                conn.commit()

            return {
                "model_name": policy.model_name,
                "policy": self._policy_to_dict(policy),
                "message": "Policy updated successfully"
            }

    def get_policy(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get scaling policy for a model."""
        with self._lock:
            policy = self.policies.get(model_name)
            if policy:
                return self._policy_to_dict(policy)

            # Try to load from database
            with sqlite3.connect(str(DB_PATH)) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM scaling_policies WHERE model_name = ?", (model_name,))
                row = c.fetchone()

                if row:
                    policy = ScalingPolicy(
                        model_name=row["model_name"],
                        min_replicas=row["min_replicas"],
                        max_replicas=row["max_replicas"],
                        target_cpu_percent=row["target_cpu_percent"],
                        target_memory_percent=row["target_memory_percent"],
                        target_qps=row["target_qps"],
                        scale_up_cooldown=row["scale_up_cooldown"],
                        scale_down_cooldown=row["scale_down_cooldown"],
                        scale_up_threshold=row["scale_up_threshold"],
                        scale_down_threshold=row["scale_down_threshold"],
                        scale_up_increment=row["scale_up_increment"],
                        scale_down_increment=row["scale_down_increment"],
                        enabled=bool(row["enabled"])
                    )
                    self.policies[model_name] = policy
                    return self._policy_to_dict(policy)

            return None

    def delete_policy(self, model_name: str) -> bool:
        """Delete a scaling policy."""
        with self._lock:
            if model_name in self.policies:
                del self.policies[model_name]

            if model_name in self.metrics:
                del self.metrics[model_name]

            if model_name in self.current_replicas:
                del self.current_replicas[model_name]

            with sqlite3.connect(str(DB_PATH)) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM scaling_policies WHERE model_name = ?", (model_name,))
                conn.commit()

            return True

    def add_metrics(self, model_name: str, cpu_percent: float, memory_percent: float,
                   requests_per_second: float, avg_latency_ms: float, error_rate: float):
        """Add metrics for a model."""
        with self._lock:
            if model_name not in self.metrics:
                self.metrics[model_name] = ScalingMetrics(model_name)

            self.metrics[model_name].add_metrics(
                cpu_percent, memory_percent, requests_per_second, avg_latency_ms, error_rate
            )

            # Save to database
            with sqlite3.connect(str(DB_PATH)) as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO scaling_metrics (model_name, cpu_percent, memory_percent, "
                    "requests_per_second, avg_latency_ms, error_rate, replica_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (model_name, cpu_percent, memory_percent, requests_per_second,
                     avg_latency_ms, error_rate, self.current_replicas.get(model_name, 1)))
                conn.commit()

    def get_metrics(self, model_name: str, minutes: int = 10) -> Dict[str, Any]:
        """Get metrics for a model."""
        with self._lock:
            metrics_obj = self.metrics.get(model_name)
            if metrics_obj:
                avg_metrics = metrics_obj.get_average_metrics()
                return {
                    "model_name": model_name,
                    "current_replicas": self.current_replicas.get(model_name, 1),
                    "average_metrics": avg_metrics,
                    "timestamp": metrics_obj.timestamp.isoformat()
                }

            # Try to get from database
            cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(str(DB_PATH)) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT AVG(cpu_percent) as avg_cpu, AVG(memory_percent) as avg_memory, "
                    "AVG(requests_per_second) as avg_qps, AVG(avg_latency_ms) as avg_latency, "
                    "AVG(error_rate) as avg_error_rate, AVG(replica_count) as avg_replicas "
                    "FROM scaling_metrics WHERE model_name = ? AND timestamp > ?",
                    (model_name, cutoff))
                row = c.fetchone()

                if row:
                    return {
                        "model_name": model_name,
                        "current_replicas": self.current_replicas.get(model_name, 1),
                        "average_metrics": {
                            "cpu_percent": row["avg_cpu"] or 0,
                            "memory_percent": row["avg_memory"] or 0,
                            "requests_per_second": row["avg_qps"] or 0,
                            "avg_latency_ms": row["avg_latency"] or 0,
                            "error_rate": row["avg_error_rate"] or 0
                        },
                        "from_database": True
                    }

            return {}

    def get_scaling_history(self, model_name: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get scaling history."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            if model_name:
                c.execute(
                    "SELECT * FROM scaling_history WHERE model_name = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (model_name, limit))
            else:
                c.execute("SELECT * FROM scaling_history ORDER BY created_at DESC LIMIT ?", (limit,))

            rows = c.fetchall()
            history = []

            for row in rows:
                entry = dict(row)
                if entry.get("metrics"):
                    try:
                        entry["metrics"] = json.loads(entry["metrics"])
                    except json.JSONDecodeError:
                        entry["metrics"] = {}
                history.append(entry)

            return history

    def manual_scale(self, model_name: str, target_replicas: int, reason: str = "manual") -> Dict[str, Any]:
        """Manually scale a model."""
        with self._lock:
            current = self.current_replicas.get(model_name, 1)
            policy = self.policies.get(model_name)

            if policy:
                if target_replicas < policy.min_replicas:
                    target_replicas = policy.min_replicas
                elif target_replicas > policy.max_replicas:
                    target_replicas = policy.max_replicas

            self._perform_scale(model_name, current, target_replicas, reason, {})
            return {
                "model_name": model_name,
                "old_replicas": current,
                "new_replicas": target_replicas,
                "reason": reason,
                "message": "Manual scaling completed"
            }

    def get_status(self) -> Dict[str, Any]:
        """Get overall auto-scaling status."""
        with self._lock:
            return {
                "monitoring": self._running,
                "policies_count": len(self.policies),
                "models_monitored": list(self.policies.keys()),
                "total_scaling_events": len(self.scaling_history),
                "current_replicas": self.current_replicas
            }

    def _policy_to_dict(self, policy: ScalingPolicy) -> Dict[str, Any]:
        """Convert policy to dict."""
        return {
            "model_name": policy.model_name,
            "min_replicas": policy.min_replicas,
            "max_replicas": policy.max_replicas,
            "target_cpu_percent": policy.target_cpu_percent,
            "target_memory_percent": policy.target_memory_percent,
            "target_qps": policy.target_qps,
            "scale_up_cooldown": policy.scale_up_cooldown,
            "scale_down_cooldown": policy.scale_down_cooldown,
            "scale_up_threshold": policy.scale_up_threshold,
            "scale_down_threshold": policy.scale_down_threshold,
            "scale_up_increment": policy.scale_up_increment,
            "scale_down_increment": policy.scale_down_increment,
            "enabled": policy.enabled
        }


# Global instance
auto_scaling_service = AutoScalingService()