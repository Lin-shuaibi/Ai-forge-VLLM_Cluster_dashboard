"""GPU monitoring service."""
import subprocess
from typing import List, Dict, Optional
from database import get_db


class GPUMonitor:
    """Monitor GPU metrics via nvidia-smi."""

    def __init__(self):
        self._has_nvidia_smi = None

    def is_available(self):
        if self._has_nvidia_smi is None:
            try:
                subprocess.run(
                    ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
                    capture_output=True, timeout=5
                )
                self._has_nvidia_smi = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._has_nvidia_smi = False
        return self._has_nvidia_smi

    def get_metrics(self):
        if not self.is_available():
            return []

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,memory.free,power.draw,power.limit,fan.speed,clocks.sm,clocks.mem",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True, text=True, timeout=10
            )
            metrics = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 12:
                    metrics.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "temperature": float(parts[2]) if parts[2] != "[N/A]" else None,
                        "gpu_utilization": float(parts[3]) if parts[3] != "[N/A]" else None,
                        "memory_used_mb": float(parts[4]) if parts[4] != "[N/A]" else None,
                        "memory_total_mb": float(parts[5]) if parts[5] != "[N/A]" else None,
                        "memory_free_mb": float(parts[6]) if parts[6] != "[N/A]" else None,
                        "power_draw_w": float(parts[7]) if parts[7] != "[N/A]" else None,
                        "power_limit_w": float(parts[8]) if parts[8] != "[N/A]" else None,
                        "fan_speed": float(parts[9]) if parts[9] != "[N/A]" else None,
                        "sm_clock_mhz": float(parts[10]) if parts[10] != "[N/A]" else None,
                        "mem_clock_mhz": float(parts[11]) if parts[11] != "[N/A]" else None,
                    })
            return metrics
        except Exception as e:
            return [{"error": str(e)}]

    def get_summary(self):
        metrics = self.get_metrics()
        gpu_count = len(metrics)

        if gpu_count == 0:
            return {
                "available": False,
                "gpu_count": 0,
                "message": "nvidia-smi not available"
            }

        total_mem_used = sum(m.get("memory_used_mb", 0) or 0 for m in metrics)
        total_mem = sum(m.get("memory_total_mb", 0) or 0 for m in metrics)
        avg_temp = sum(m.get("temperature", 0) or 0 for m in metrics) / gpu_count if gpu_count else 0
        avg_util = sum(m.get("gpu_utilization", 0) or 0 for m in metrics) / gpu_count if gpu_count else 0

        return {
            "available": True,
            "gpu_count": gpu_count,
            "total_memory_used_mb": total_mem_used,
            "total_memory_mb": total_mem,
            "memory_usage_percent": round(total_mem_used / total_mem * 100, 1) if total_mem else 0,
            "avg_temperature": round(avg_temp, 1),
            "avg_utilization": round(avg_util, 1),
            "gpus": metrics,
        }

    def get_history(self, minutes=10):
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM alerts WHERE source='gpu' AND created_at > datetime('now', ?) ORDER BY created_at DESC",
            (f"-{minutes} minutes",)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


gpu_monitor = GPUMonitor()
