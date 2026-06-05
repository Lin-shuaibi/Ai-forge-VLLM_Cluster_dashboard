"""Health check endpoints and monitoring."""
import time
import sqlite3
import psutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from services.auth_service import get_current_user, TokenData

logger = logging.getLogger("vllm-dashboard")

router = APIRouter(prefix="/health", tags=["health"])

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "vllm_dashboard.db"


class HealthStatus:
    """Health status constants."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthChecker:
    """Health check service."""
    
    def __init__(self):
        self.start_time = time.time()
        self.checks = {}
    
    def register_check(self, name: str, check_func, interval: int = 30):
        """Register a health check."""
        self.checks[name] = {
            "func": check_func,
            "interval": interval,
            "last_run": 0,
            "last_result": None
        }
    
    def check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            start = time.time()
            with sqlite3.connect(str(DB_PATH)) as conn:
                c = conn.cursor()
                c.execute("SELECT 1")
                result = c.fetchone()
                latency = time.time() - start
                
                if result and result[0] == 1:
                    return {
                        "status": HealthStatus.HEALTHY,
                        "latency_ms": round(latency * 1000, 2),
                        "message": "Database connection OK"
                    }
                else:
                    return {
                        "status": HealthStatus.UNHEALTHY,
                        "latency_ms": round(latency * 1000, 2),
                        "message": "Database query failed"
                    }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Database error: {str(e)}"
            }
    
    def check_disk_space(self) -> Dict[str, Any]:
        """Check disk space."""
        try:
            disk = psutil.disk_usage("/")
            percent_used = disk.percent
            free_gb = disk.free / (1024**3)
            
            if percent_used > 90:
                status = HealthStatus.UNHEALTHY
                message = f"Disk space critically low: {percent_used:.1f}% used"
            elif percent_used > 80:
                status = HealthStatus.DEGRADED
                message = f"Disk space low: {percent_used:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK: {percent_used:.1f}% used"
            
            return {
                "status": status,
                "percent_used": round(percent_used, 1),
                "free_gb": round(free_gb, 2),
                "message": message
            }
        except Exception as e:
            return {
                "status": HealthStatus.DEGRADED,
                "message": f"Disk check failed: {str(e)}"
            }
    
    def check_memory(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            mem = psutil.virtual_memory()
            percent_used = mem.percent
            available_gb = mem.available / (1024**3)
            
            if percent_used > 90:
                status = HealthStatus.UNHEALTHY
                message = f"Memory critically low: {percent_used:.1f}% used"
            elif percent_used > 80:
                status = HealthStatus.DEGRADED
                message = f"Memory high: {percent_used:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory OK: {percent_used:.1f}% used"
            
            return {
                "status": status,
                "percent_used": round(percent_used, 1),
                "available_gb": round(available_gb, 2),
                "message": message
            }
        except Exception as e:
            return {
                "status": HealthStatus.DEGRADED,
                "message": f"Memory check failed: {str(e)}"
            }
    
    def check_cpu(self) -> Dict[str, Any]:
        """Check CPU usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            
            if cpu_percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"CPU critically high: {cpu_percent:.1f}%"
            elif cpu_percent > 80:
                status = HealthStatus.DEGRADED
                message = f"CPU high: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU OK: {cpu_percent:.1f}%"
            
            return {
                "status": status,
                "cpu_percent": round(cpu_percent, 1),
                "message": message
            }
        except Exception as e:
            return {
                "status": HealthStatus.DEGRADED,
                "message": f"CPU check failed: {str(e)}"
            }
    
    def check_service(self) -> Dict[str, Any]:
        """Check service status."""
        uptime = time.time() - self.start_time
        return {
            "status": HealthStatus.HEALTHY,
            "uptime_seconds": round(uptime, 2),
            "uptime_human": str(timedelta(seconds=int(uptime))),
            "message": f"Service running for {str(timedelta(seconds=int(uptime)))}"
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        # Run basic checks
        checks = [
            ("database", self.check_database),
            ("disk_space", self.check_disk_space),
            ("memory", self.check_memory),
            ("cpu", self.check_cpu),
            ("service", self.check_service),
        ]
        
        for name, check_func in checks:
            try:
                result = check_func()
                results[name] = result
                
                # Update overall status
                if result["status"] == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif result["status"] == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
            except Exception as e:
                results[name] = {
                    "status": HealthStatus.UNHEALTHY,
                    "message": f"Check failed: {str(e)}"
                }
                overall_status = HealthStatus.UNHEALTHY
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results
        }


# Global health checker instance
health_checker = HealthChecker()


@router.get("/")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "vllm-dashboard"
    }


@router.get("/detailed")
async def detailed_health_check():
    """Detailed health check with system metrics."""
    return health_checker.run_all_checks()


@router.get("/readiness")
async def readiness_probe():
    """Readiness probe for Kubernetes/load balancers."""
    result = health_checker.run_all_checks()
    
    if result["status"] == HealthStatus.HEALTHY:
        return JSONResponse(
            content=result,
            status_code=200
        )
    elif result["status"] == HealthStatus.DEGRADED:
        return JSONResponse(
            content=result,
            status_code=206  # Partial content
        )
    else:
        return JSONResponse(
            content=result,
            status_code=503  # Service Unavailable
        )


@router.get("/liveness")
async def liveness_probe():
    """Liveness probe for Kubernetes."""
    try:
        # Quick check - just see if we can respond
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception:
        raise HTTPException(status_code=503, detail="Service not alive")


@router.get("/metrics")
async def health_metrics(current_user: TokenData = Depends(get_current_user)):
    """Get health metrics (requires authentication)."""
    result = health_checker.run_all_checks()
    
    # Add additional metrics
    result["request_count"] = 0  # Would come from request counter
    result["active_connections"] = 0  # Would come from connection pool
    result["version"] = "1.0.0"  # From config
    
    return result


@router.get("/history")
async def health_history(
    limit: int = 10,
    current_user: TokenData = Depends(get_current_user)
):
    """Get health check history (requires admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # In production, this would query a history table
    return {
        "history": [],
        "message": "History logging not yet implemented"
    }