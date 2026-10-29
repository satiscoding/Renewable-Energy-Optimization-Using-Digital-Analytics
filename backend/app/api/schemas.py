"""Pydantic schemas for request validation and response serialization."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class SiteSchema(BaseModel):
    id: str
    name: str
    type: str
    capacity_kw: float
    aggregation_level: str

    class Config:
        from_attributes = True


class WeatherSnapshot(BaseModel):
    irradiation: Optional[float] = None
    module_temp: Optional[float] = None
    ambient_temp: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None


class SiteStatusResponse(BaseModel):
    site_id: str
    site_name: str
    site_type: str
    timestamp: str
    actual_kw: float
    expected_kw: float
    gap_kw: float
    gap_pct: float
    daily_yield_kwh: float
    capacity_kw: float
    current_load_pct: float             # Actual kW / Rated kW * 100
    daily_capacity_factor_pct: float    # Daily yield kWh / (Rated kW * elapsed hours) * 100
    capacity_factor_pct: float          # Backward compatible alias for daily CF
    health: str                         # "healthy" | "anomaly_detected"
    active_issues_count: int
    latest_weather: WeatherSnapshot


class HistoryPoint(BaseModel):
    timestamp: str
    actual_kw: float
    expected_kw: Optional[float] = None
    is_anomaly: int = 0
    irradiation: Optional[float] = None
    wind_speed: Optional[float] = None


class HistoryResponse(BaseModel):
    site_id: str
    site_name: str
    site_type: str
    capacity_kw: float
    points_count: int
    points: List[HistoryPoint]


class ForecastPoint(BaseModel):
    timestamp: str
    predicted_kw: float
    confidence_low_kw: Optional[float] = None
    confidence_high_kw: Optional[float] = None


class ForecastResponse(BaseModel):
    site_id: str
    model_used: str
    evaluation_metrics: Dict[str, Any]
    points_count: int
    points: List[ForecastPoint]


class RecommendationResponse(BaseModel):
    id: int
    site_id: str
    created_at: str
    relative_time: str
    severity: str # "info" | "warning" | "critical"
    issue_type: str
    reason: str
    action: str
    status: str # "active" | "resolved"


class AnomalyInjectRequest(BaseModel):
    site_id: str
    anomaly_mode: str = Field(..., description="'normal' | 'soiling' | 'sudden_drop' | 'wind_shortfall'")


class SimulatorTickResponse(BaseModel):
    status: str
    results: Dict[str, Any]
