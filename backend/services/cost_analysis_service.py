"""Cost analysis dashboard service."""
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "vllm_dashboard.db"


class CostAnalysisService:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            c.execute("CREATE TABLE IF NOT EXISTS cost_records ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "model_name TEXT NOT NULL, "
                "resource_type TEXT NOT NULL, "  # gpu, cpu, memory, storage, network
                "usage_amount REAL NOT NULL, "
                "unit TEXT NOT NULL, "  # hours, gb, requests
                "unit_price REAL NOT NULL, "
                "total_cost REAL NOT NULL, "
                "currency TEXT DEFAULT 'CNY', "
                "record_date DATE NOT NULL, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

            c.execute("CREATE TABLE IF NOT EXISTS cost_budgets ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "model_name TEXT, "  # NULL = global budget
                "budget_type TEXT NOT NULL, "  # daily, weekly, monthly
                "amount REAL NOT NULL, "
                "currency TEXT DEFAULT 'CNY', "
                "is_active BOOLEAN DEFAULT 1, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

            c.execute("CREATE TABLE IF NOT EXISTS cost_alerts ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "budget_id INTEGER NOT NULL, "
                "alert_type TEXT NOT NULL, "  # warning, critical
                "threshold_percent REAL NOT NULL, "
                "message TEXT, "
                "is_triggered BOOLEAN DEFAULT 0, "
                "triggered_at TIMESTAMP, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (budget_id) REFERENCES cost_budgets(id) ON DELETE CASCADE)")

            conn.commit()

    def record_cost(self, model_name: str, resource_type: str, usage_amount: float,
                   unit: str, unit_price: float, record_date: str = None) -> Dict[str, Any]:
        """Record a cost entry."""
        total_cost = round(usage_amount * unit_price, 4)
        if not record_date:
            record_date = datetime.utcnow().strftime("%Y-%m-%d")

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute(
                "INSERT INTO cost_records (model_name, resource_type, usage_amount, "
                "unit, unit_price, total_cost, record_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (model_name, resource_type, usage_amount, unit, unit_price, total_cost, record_date))

            record_id = c.lastrowid
            conn.commit()

            # Check budget alerts
            self._check_budget_alerts(model_name)

            return {
                "id": record_id,
                "model_name": model_name,
                "resource_type": resource_type,
                "usage_amount": usage_amount,
                "unit": unit,
                "unit_price": unit_price,
                "total_cost": total_cost,
                "record_date": record_date
            }

    def get_cost_summary(self, model_name: str = None, start_date: str = None,
                        end_date: str = None, group_by: str = "day") -> Dict[str, Any]:
        """Get cost summary with grouping."""
        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Build query
            where_clauses = ["record_date BETWEEN ? AND ?"]
            params = [start_date, end_date]

            if model_name:
                where_clauses.append("model_name = ?")
                params.append(model_name)

            where_sql = " AND ".join(where_clauses)

            # Total cost
            c.execute(
                f"SELECT COALESCE(SUM(total_cost), 0) as total_cost FROM cost_records WHERE {where_sql}",
                params)
            total_cost = c.fetchone()["total_cost"]

            # Cost by model
            c.execute(
                f"SELECT model_name, COALESCE(SUM(total_cost), 0) as cost "
                f"FROM cost_records WHERE {where_sql} GROUP BY model_name ORDER BY cost DESC",
                params)
            cost_by_model = [dict(row) for row in c.fetchall()]

            # Cost by resource type
            c.execute(
                f"SELECT resource_type, COALESCE(SUM(total_cost), 0) as cost "
                f"FROM cost_records WHERE {where_sql} GROUP BY resource_type ORDER BY cost DESC",
                params)
            cost_by_resource = [dict(row) for row in c.fetchall()]

            # Cost by time period
            date_format = "%Y-%m-%d"
            if group_by == "week":
                date_format = "%Y-%W"
            elif group_by == "month":
                date_format = "%Y-%m"

            c.execute(
                f"SELECT strftime('{date_format}', record_date) as period, "
                f"COALESCE(SUM(total_cost), 0) as cost "
                f"FROM cost_records WHERE {where_sql} GROUP BY period ORDER BY period",
                params)
            cost_by_period = [dict(row) for row in c.fetchall()]

            return {
                "total_cost": round(total_cost, 2),
                "currency": "CNY",
                "period": {"start": start_date, "end": end_date},
                "cost_by_model": cost_by_model,
                "cost_by_resource": cost_by_resource,
                "cost_by_period": cost_by_period
            }

    def get_cost_trends(self, model_name: str = None, days: int = 30) -> Dict[str, Any]:
        """Get cost trends and projections."""
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            where_clauses = ["record_date BETWEEN ? AND ?"]
            params = [start_date, end_date]

            if model_name:
                where_clauses.append("model_name = ?")
                params.append(model_name)

            where_sql = " AND ".join(where_clauses)

            # Daily costs
            c.execute(
                f"SELECT record_date, COALESCE(SUM(total_cost), 0) as daily_cost "
                f"FROM cost_records WHERE {where_sql} GROUP BY record_date ORDER BY record_date",
                params)
            daily_costs = [dict(row) for row in c.fetchall()]

            # Calculate trends
            if len(daily_costs) >= 2:
                # Simple linear trend
                costs = [d["daily_cost"] for d in daily_costs]
                avg_cost = sum(costs) / len(costs)
                trend = "stable"

                if len(costs) >= 7:
                    recent_avg = sum(costs[-7:]) / 7
                    earlier_avg = sum(costs[:7]) / 7 if len(costs) >= 14 else sum(costs[:len(costs)//2]) / (len(costs)//2)

                    if recent_avg > earlier_avg * 1.1:
                        trend = "increasing"
                    elif recent_avg < earlier_avg * 0.9:
                        trend = "decreasing"

                # Project next 7 days
                projected = []
                if trend == "increasing":
                    growth_rate = (costs[-1] / costs[0]) ** (1/len(costs)) - 1 if costs[0] > 0 else 0
                    for i in range(1, 8):
                        projected.append({
                            "date": (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d"),
                            "projected_cost": round(costs[-1] * (1 + growth_rate) ** i, 2)
                        })
                elif trend == "decreasing":
                    decay_rate = 1 - (costs[-1] / costs[0]) ** (1/len(costs)) if costs[0] > 0 else 0
                    for i in range(1, 8):
                        projected.append({
                            "date": (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d"),
                            "projected_cost": round(costs[-1] * (1 - decay_rate) ** i, 2)
                        })
                else:
                    for i in range(1, 8):
                        projected.append({
                            "date": (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d"),
                            "projected_cost": round(avg_cost, 2)
                        })
            else:
                trend = "insufficient_data"
                projected = []

            return {
                "trend": trend,
                "average_daily_cost": round(sum(c["daily_cost"] for c in daily_costs) / max(len(daily_costs), 1), 2),
                "daily_costs": daily_costs,
                "projected_7_days": projected
            }

    def get_cost_breakdown(self, model_name: str = None, start_date: str = None,
                          end_date: str = None) -> Dict[str, Any]:
        """Get detailed cost breakdown."""
        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            where_clauses = ["record_date BETWEEN ? AND ?"]
            params = [start_date, end_date]

            if model_name:
                where_clauses.append("model_name = ?")
                params.append(model_name)

            where_sql = " AND ".join(where_clauses)

            # GPU cost breakdown
            c.execute(
                f"SELECT model_name, COALESCE(SUM(total_cost), 0) as gpu_cost "
                f"FROM cost_records WHERE resource_type = 'gpu' AND {where_sql} "
                f"GROUP BY model_name ORDER BY gpu_cost DESC",
                params)
            gpu_costs = [dict(row) for row in c.fetchall()]

            # CPU cost breakdown
            c.execute(
                f"SELECT model_name, COALESCE(SUM(total_cost), 0) as cpu_cost "
                f"FROM cost_records WHERE resource_type = 'cpu' AND {where_sql} "
                f"GROUP BY model_name ORDER BY cpu_cost DESC",
                params)
            cpu_costs = [dict(row) for row in c.fetchall()]

            # Storage cost breakdown
            c.execute(
                f"SELECT model_name, COALESCE(SUM(total_cost), 0) as storage_cost "
                f"FROM cost_records WHERE resource_type = 'storage' AND {where_sql} "
                f"GROUP BY model_name ORDER BY storage_cost DESC",
                params)
            storage_costs = [dict(row) for row in c.fetchall()]

            # Network cost breakdown
            c.execute(
                f"SELECT model_name, COALESCE(SUM(total_cost), 0) as network_cost "
                f"FROM cost_records WHERE resource_type = 'network' AND {where_sql} "
                f"GROUP BY model_name ORDER BY network_cost DESC",
                params)
            network_costs = [dict(row) for row in c.fetchall()]

            return {
                "period": {"start": start_date, "end": end_date},
                "gpu": gpu_costs,
                "cpu": cpu_costs,
                "storage": storage_costs,
                "network": network_costs
            }

    def set_budget(self, model_name: str = None, budget_type: str = "monthly",
                  amount: float = 0) -> Dict[str, Any]:
        """Set a cost budget."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Deactivate existing budget of same type
            if model_name:
                c.execute(
                    "UPDATE cost_budgets SET is_active = 0 WHERE model_name = ? AND budget_type = ?",
                    (model_name, budget_type))
            else:
                c.execute(
                    "UPDATE cost_budgets SET is_active = 0 WHERE model_name IS NULL AND budget_type = ?",
                    (budget_type,))

            c.execute(
                "INSERT INTO cost_budgets (model_name, budget_type, amount) VALUES (?, ?, ?)",
                (model_name, budget_type, amount))

            budget_id = c.lastrowint
            conn.commit()

            return {
                "budget_id": budget_id,
                "model_name": model_name or "global",
                "budget_type": budget_type,
                "amount": amount,
                "currency": "CNY"
            }

    def get_budget_status(self, model_name: str = None) -> Dict[str, Any]:
        """Get budget status and alerts."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get active budgets
            if model_name:
                c.execute(
                    "SELECT * FROM cost_budgets WHERE (model_name = ? OR model_name IS NULL) "
                    "AND is_active = 1",
                    (model_name,))
            else:
                c.execute("SELECT * FROM cost_budgets WHERE is_active = 1")

            budgets = [dict(row) for row in c.fetchall()]

            results = []
            for budget in budgets:
                # Calculate current spending
                now = datetime.utcnow()
                if budget["budget_type"] == "daily":
                    start_date = now.strftime("%Y-%m-%d")
                elif budget["budget_type"] == "weekly":
                    start_date = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
                else:  # monthly
                    start_date = now.strftime("%Y-%m-01")

                end_date = now.strftime("%Y-%m-%d")

                where_clauses = ["record_date BETWEEN ? AND ?"]
                params = [start_date, end_date]

                if budget["model_name"]:
                    where_clauses.append("model_name = ?")
                    params.append(budget["model_name"])

                where_sql = " AND ".join(where_clauses)

                c.execute(
                    f"SELECT COALESCE(SUM(total_cost), 0) as spent FROM cost_records WHERE {where_sql}",
                    params)
                spent = c.fetchone()["spent"]

                percent_used = round((spent / budget["amount"]) * 100, 1) if budget["amount"] > 0 else 0

                status = "ok"
                if percent_used >= 100:
                    status = "exceeded"
                elif percent_used >= 80:
                    status = "warning"
                elif percent_used >= 60:
                    status = "approaching"

                results.append({
                    "budget_id": budget["id"],
                    "model_name": budget["model_name"] or "global",
                    "budget_type": budget["budget_type"],
                    "budget_amount": budget["amount"],
                    "spent": round(spent, 2),
                    "remaining": round(budget["amount"] - spent, 2),
                    "percent_used": percent_used,
                    "status": status,
                    "period": {"start": start_date, "end": end_date}
                })

            return {"budgets": results}

    def get_optimization_suggestions(self) -> List[Dict[str, Any]]:
        """Get cost optimization suggestions."""
        suggestions = []

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Check for idle models (no recent cost records)
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            c.execute(
                "SELECT model_name, MAX(record_date) as last_used "
                "FROM cost_records GROUP BY model_name "
                "HAVING MAX(record_date) < ?",
                (thirty_days_ago,))
            idle_models = c.fetchall()

            for model in idle_models:
                suggestions.append({
                    "type": "idle_model",
                    "severity": "medium",
                    "model_name": model["model_name"],
                    "last_used": model["last_used"],
                    "suggestion": f"Model {model['model_name']} has been idle for over 30 days. "
                                 f"Consider archiving or removing to reduce storage costs.",
                    "estimated_savings": "Variable"
                })

            # Check for GPU cost spikes
            c.execute(
                "SELECT model_name, record_date, SUM(total_cost) as daily_cost "
                "FROM cost_records WHERE resource_type = 'gpu' "
                "GROUP BY model_name, record_date "
                "ORDER BY daily_cost DESC LIMIT 5")
            high_cost_days = c.fetchall()

            for day in high_cost_days:
                if day["daily_cost"] > 100:  # Threshold
                    suggestions.append({
                        "type": "high_gpu_cost",
                        "severity": "high",
                        "model_name": day["model_name"],
                        "date": day["record_date"],
                        "cost": day["daily_cost"],
                        "suggestion": f"High GPU cost ({day['daily_cost']} CNY) on {day['record_date']} "
                                     f"for {day['model_name']}. Review usage patterns and consider "
                                     f"batch processing or using smaller GPU instances."
                    })

            # Check for storage growth
            c.execute(
                "SELECT model_name, record_date, SUM(total_cost) as daily_cost "
                "FROM cost_records WHERE resource_type = 'storage' "
                "GROUP BY model_name, record_date "
                "ORDER BY record_date DESC LIMIT 30")
            storage_records = c.fetchall()

            if len(storage_records) >= 7:
                recent = sum(r["daily_cost"] for r in storage_records[:7])
                earlier = sum(r["daily_cost"] for r in storage_records[7:14]) if len(storage_records) >= 14 else 0

                if earlier > 0 and recent > earlier * 1.2:
                    suggestions.append({
                        "type": "storage_growth",
                        "severity": "medium",
                        "suggestion": "Storage costs are increasing. Consider implementing "
                                     "data lifecycle policies and cleaning up old model artifacts.",
                        "estimated_savings": f"~{round(recent - earlier, 2)} CNY/week"
                    })

        return suggestions

    def _check_budget_alerts(self, model_name: str):
        """Check and trigger budget alerts."""
        budget_status = self.get_budget_status(model_name)

        for budget in budget_status["budgets"]:
            if budget["status"] in ("warning", "exceeded"):
                with sqlite3.connect(str(DB_PATH)) as conn:
                    c = conn.cursor()

                    # Check if alert already triggered
                    c.execute(
                        "SELECT id FROM cost_alerts WHERE budget_id = ? AND is_triggered = 1",
                        (budget["budget_id"],))
                    if not c.fetchone():
                        c.execute(
                            "INSERT INTO cost_alerts (budget_id, alert_type, threshold_percent, "
                            "message, is_triggered, triggered_at) VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)",
                            (budget["budget_id"],
                             "critical" if budget["status"] == "exceeded" else "warning",
                             budget["percent_used"],
                             f"Budget {budget['status']}: {budget['percent_used']}% used"))
                        conn.commit()


cost_analysis_service = CostAnalysisService()