"""History endpoint: trailing 24-hour generation telemetry."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Site, SensorReading, WeatherReading
from app.api.schemas import HistoryResponse, HistoryPoint

router = APIRouter(prefix="/history", tags=["History"])

@router.get("", response_model=HistoryResponse)
def get_site_history(
    site_id: str = Query(..., description="Target site identifier"),
    hours: int = Query(24, ge=1, le=168, description="History window in hours"),
    db: Session = Depends(get_db)
):
    """Retrieve time series history for the requested site."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found.")

    latest_reading = db.query(SensorReading.timestamp).filter(
        SensorReading.site_id == site_id
    ).order_by(SensorReading.timestamp.desc()).first()

    if not latest_reading:
        return HistoryResponse(
            site_id=site.id,
            site_name=site.name,
            site_type=site.type,
            capacity_kw=site.capacity_kw,
            points_count=0,
            points=[]
        )

    end_ts = latest_reading[0]
    start_ts = end_ts - timedelta(hours=hours)

    readings = db.query(
        SensorReading.timestamp,
        SensorReading.ac_power_kw,
        SensorReading.expected_power_kw,
        SensorReading.is_anomaly,
        WeatherReading.irradiation,
        WeatherReading.wind_speed
    ).outerjoin(
        WeatherReading,
        (SensorReading.site_id == WeatherReading.site_id) & (SensorReading.timestamp == WeatherReading.timestamp)
    ).filter(
        SensorReading.site_id == site_id,
        SensorReading.timestamp >= start_ts,
        SensorReading.timestamp <= end_ts
    ).order_by(SensorReading.timestamp.asc()).all()

    points = [
        HistoryPoint(
            timestamp=r.timestamp.isoformat(),
            actual_kw=r.ac_power_kw,
            expected_kw=r.expected_power_kw,
            is_anomaly=r.is_anomaly,
            irradiation=r.irradiation,
            wind_speed=r.wind_speed
        )
        for r in readings
    ]

    return HistoryResponse(
        site_id=site.id,
        site_name=site.name,
        site_type=site.type,
        capacity_kw=site.capacity_kw,
        points_count=len(points),
        points=points
    )
