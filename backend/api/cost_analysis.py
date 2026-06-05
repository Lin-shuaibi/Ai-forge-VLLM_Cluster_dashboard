"""Cost analysis dashboard API."""
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from services.cost_analysis_service import cost_analysis_service, CostAnalysisService
from services.auth_service import get_current_user, require_permission, TokenData

router = APIRouter(prefix="/cost-analysis", tags=["cost-analysis"])


class CostRecordCreate(BaseModel):
    model_name: str = Field(..., description="Model name")
    resource_type: str = Field(..., pattern="^(gpu|cpu|memory|storage|network)$")
    usage_amount: float = Field(..., ge=0, description="Amount used")
    unit: str = Field(..., description="Unit of measurement (hours, gb, requests)")
    unit_price: float = Field(..., ge=0, description="Price per unit")
    record_date: Optional[str] = Field(None, description="Date of record (YYYY-MM-DD)")


class BudgetCreate(BaseModel):
    model_name: Optional[str] = Field(None, description="Model name (null for global)")
    budget_type: str = Field(..., pattern="^(daily|weekly|monthly)$")
    amount: float = Field(..., ge=0, description="Budget amount")


@router.post("/records", response_model=dict)
async def create_cost_record(
    record: CostRecordCreate,
    current_user: TokenData = Depends(require_permission("cost_analysis", "create"))
):
    """Create a cost record."""
    try:
        result = cost_analysis_service.record_cost(
            model_name=record.model_name,
            resource_type=record.resource_type,
            usage_amount=record.usage_amount,
            unit=record.unit,
            unit_price=record.unit_price,
            record_date=record.record_date
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create cost record: {str(e)}")


@router.get("/summary", response_model=dict)
async def get_cost_summary(
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    group_by: str = Query("day", pattern="^(day|week|month)$"),
    current_user: TokenData = Depends(require_permission("cost_analysis", "read"))
):
    """Get cost summary."""
    try:
        result = cost_analysis_service.get_cost_summary(
            model_name=model_name,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cost summary: {str(e)}")


@router.get("/trends", response_model=dict)
async def get_cost_trends(
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: TokenData = Depends(require_permission("cost_analysis", "read"))
):
    """Get cost trends and projections."""
    try:
        result = cost_analysis_service.get_cost_trends(model_name=model_name, days=days)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cost trends: {str(e)}")


@router.get("/breakdown", response_model=dict)
async def get_cost_breakdown(
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: TokenData = Depends(require_permission("cost_analysis", "read"))
):
    """Get detailed cost breakdown by resource type."""
    try:
        result = cost_analysis_service.get_cost_breakdown(
            model_name=model_name,
            start_date=start_date,
            end_date=end_date
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cost breakdown: {str(e)}")


@router.post("/budgets", response_model=dict)
async def set_budget(
    budget: BudgetCreate,
    current_user: TokenData = Depends(require_permission("cost_analysis", "create"))
):
    """Set a cost budget."""
    try:
        result = cost_analysis_service.set_budget(
            model_name=budget.model_name,
            budget_type=budget.budget_type,
            amount=budget.amount
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set budget: {str(e)}")


@router.get("/budgets/status", response_model=dict)
async def get_budget_status(
    model_name: Optional[str] = Query(None, description="Filter by model name"),
    current_user: TokenData = Depends(require_permission("cost_analysis", "read"))
):
    """Get budget status and alerts."""
    try:
        result = cost_analysis_service.get_budget_status(model_name=model_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get budget status: {str(e)}")


@router.get("/optimization-suggestions", response_model=List[dict])
async def get_optimization_suggestions(
    current_user: TokenData = Depends(require_permission("cost_analysis", "read"))
):
    """Get cost optimization suggestions."""
    try:
        suggestions = cost_analysis_service.get_optimization_suggestions()
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@router.get("/alerts", response_model=List[dict])
async def get_cost_alerts(
    triggered_only: bool = Query(True, description="Only show triggered alerts"),
    current_user: TokenData = Depends(require_permission("cost_analysis", "read"))
):
    """Get cost alerts."""
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            sql = "SELECT ca.*, cb.model_name, cb.budget_type, cb.amount FROM cost_alerts ca "
            sql += "JOIN cost_budgets cb ON ca.budget_id = cb.id"

            if triggered_only:
                sql += " WHERE ca.is_triggered = 1"

            sql += " ORDER BY ca.triggered_at DESC LIMIT 50"

            c.execute(sql)
            alerts = [dict(row) for row in c.fetchall()]

            return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")


@router.get("/forecast", response_model=dict)
async def get_cost_forecast(
    days: int = Query(30, ge=1, le=365, description="Forecast horizon in days"),
    current_user: TokenData = Depends(require_permission("cost_analysis", "read"))
):
    """Get cost forecast."""
    try:
        # Get historical data
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute(
                "SELECT record_date, SUM(total_cost) as daily_cost "
                "FROM cost_records WHERE record_date BETWEEN ? AND ? "
                "GROUP BY record_date ORDER BY record_date",
                (start_date, end_date))
            historical = [dict(row) for row in c.fetchall()]

        if len(historical) < 7:
            return {
                "forecast": [],
                "confidence": "low",
                "message": "Insufficient historical data for forecasting"
            }

        # Simple moving average forecast
        daily_costs = [h["daily_cost"] for h in historical]
        window = min(7, len(daily_costs))
        moving_avg = sum(daily_costs[-window:]) / window

        forecast = []
        for i in range(1, days + 1):
            forecast_date = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")
            forecast.append({
                "date": forecast_date,
                "forecast_cost": round(moving_avg, 2),
                "lower_bound": round(moving_avg * 0.8, 2),
                "upper_bound": round(moving_avg * 1.2, 2)
            })

        total_forecast = sum(f["forecast_cost"] for f in forecast)

        return {
            "forecast": forecast,
            "total_forecast": round(total_forecast, 2),
            "confidence": "medium",
            "method": "7-day_moving_average",
            "historical_days": len(historical)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate forecast: {str(e)}")


@router.get("/export", response_model=dict)
async def export_cost_data(
    format: str = Query("json", pattern="^(json|csv)$"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: TokenData = Depends(require_permission("cost_analysis", "read"))
):
    """Export cost data."""
    try:
        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute(
                "SELECT * FROM cost_records WHERE record_date BETWEEN ? AND ? "
                "ORDER BY record_date, model_name",
                (start_date, end_date))
            records = [dict(row) for row in c.fetchall()]

        if format == "csv":
            # Generate CSV
            csv_lines = ["model_name,resource_type,usage_amount,unit,unit_price,total_cost,record_date"]
            for record in records:
                csv_lines.append(
                    f"{record['model_name']},{record['resource_type']},{record['usage_amount']},"
                    f"{record['unit']},{record['unit_price']},{record['total_cost']},{record['record_date']}"
                )
            return {
                "format": "csv",
                "data": "\n".join(csv_lines),
                "filename": f"cost_export_{start_date}_to_{end_date}.csv"
            }
        else:
            return {
                "format": "json",
                "data": records,
                "count": len(records),
                "period": {"start": start_date, "end": end_date}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export data: {str(e)}")