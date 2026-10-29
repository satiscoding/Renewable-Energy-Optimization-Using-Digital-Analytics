"""Status endpoint: real-time telemetry snapshot, daily yield integral, and health badge."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Site, SensorReading, WeatherReading, Recommendation
from app.api.schemas import SiteStatusResponse, WeatherSnapshot

router = APIRouter(prefix="/status", tags=["Status"])

@router.get("", response_model=SiteStatusResponse)
def get_site_status(
    site_id: str = Query(..., description="Target site identifier (e.g. 'solar-plant-1' or 'wind-alpha')"),
    db: Session = Depends(get_db)
):
    """Retrieve instantaneous telemetry, daily kWh yield, gap metrics, and health condition for a site."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Site with ID '{site_id}' not found.")

    latest_reading = db.query(SensorReading).filter(
        SensorReading.site_id == site_id
    ).order_by(SensorReading.timestamp.desc()).first()

    if not latest_reading:
        raise HTTPException(status_code=404, detail=f"No telemetry readings recorded for site '{site_id}'.")

    latest_weather = db.query(WeatherReading).filter(
        WeatherReading.site_id == site_id,
        WeatherReading.timestamp == latest_reading.timestamp
    ).first()

    actual_kw = latest_reading.ac_power_kw
    expected_kw = latest_reading.expected_power_kw or 0.0
    gap_kw = round(expected_kw - actual_kw, 2)
    gap_pct = round((gap_kw / max(1.0, expected_kw)) * 100.0, 2) if expected_kw > 15.0 else 0.0

    # Trapezoidal daily yield integration from midnight of the reading's day
    day_start = datetime(latest_reading.timestamp.year, latest_reading.timestamp.month, latest_reading.timestamp.day)
    day_readings = db.query(SensorReading.ac_power_kw).filter(
        SensorReading.site_id == site_id,
        SensorReading.timestamp >= day_start,
        SensorReading.timestamp <= latest_reading.timestamp
    ).all()

    dt_hours = 0.25 if site.type == "solar" else (10.0 / 60.0)
    day_total_kwh = sum(r[0] * dt_hours for r in day_readings)

    daily_yield_kwh = max(
        round(day_total_kwh, 2),
        round(latest_reading.daily_yield_kwh or 0.0, 2)
    )

    # Metric 1: Current Load (% of rated capacity)
    current_load_pct = round((actual_kw / max(1.0, site.capacity_kw)) * 100.0, 1)

    # Metric 2: True Daily Capacity Factor = Daily Yield (kWh) / (Rated kW * Hours Elapsed Today)
    hours_elapsed_today = max(0.25, latest_reading.timestamp.hour + (latest_reading.timestamp.minute / 60.0))
    max_possible_kwh_today = site.capacity_kw * hours_elapsed_today
    daily_cf_pct = round((daily_yield_kwh / max(1.0, max_possible_kwh_today)) * 100.0, 1)

    # Check active recommendations and anomalies to derive site health
    active_issues = db.query(Recommendation).filter(
        Recommendation.site_id == site_id,
        Recommendation.status == "active"
    ).all()

    has_critical_or_warn = any(r.severity in ["critical", "warning"] for r in active_issues)
    is_anomaly_flagged = bool(latest_reading.is_anomaly) or has_critical_or_warn

    health_status = "anomaly_detected" if is_anomaly_flagged else "healthy"

    weather_snap = WeatherSnapshot(
        irradiation=latest_weather.irradiation if latest_weather else None,
        module_temp=latest_weather.module_temp if latest_weather else None,
        ambient_temp=latest_weather.ambient_temp if latest_weather else None,
        wind_speed=latest_weather.wind_speed if latest_weather else None,
        wind_direction=latest_weather.wind_direction if latest_weather else None
    )

    return SiteStatusResponse(
        site_id=site.id,
        site_name=site.name,
        site_type=site.type,
        timestamp=latest_reading.timestamp.isoformat(),
        actual_kw=actual_kw,
        expected_kw=expected_kw,
        gap_kw=gap_kw,
        gap_pct=gap_pct,
        daily_yield_kwh=daily_yield_kwh,
        capacity_kw=site.capacity_kw,
        current_load_pct=current_load_pct,
        daily_capacity_factor_pct=daily_cf_pct,
        capacity_factor_pct=daily_cf_pct,
        health=health_status,
        active_issues_count=len(active_issues),
        latest_weather=weather_snap
    )
