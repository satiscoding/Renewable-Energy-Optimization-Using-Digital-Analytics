"""Forecasts endpoint: 2-6 hour ahead multi-step predictions and model metrics."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Site, Forecast, SensorReading
from app.api.schemas import ForecastResponse, ForecastPoint
from app.services.forecaster import MODEL_COMPARISON_TABLE, generate_forecasts_for_site
from app.services.analytics import get_analytics_metrics

router = APIRouter(prefix="/forecasts", tags=["Forecasts"])

@router.get("", response_model=ForecastResponse)
def get_site_forecasts(
    site_id: str = Query(..., description="Target site identifier"),
    horizon_hours: int = Query(6, ge=2, le=12, description="Forecast horizon in hours"),
    db: Session = Depends(get_db)
):
    """Retrieve multi-hour ahead forecast points, uncertainty bounds, and model evaluation metrics.
    Guarantees forecasts are fresh and strictly start from the latest reading interval.
    """
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found.")

    latest_reading = db.query(SensorReading).filter(
        SensorReading.site_id == site_id
    ).order_by(SensorReading.timestamp.desc()).first()

    step_minutes = 15 if site.type == "solar" else 10
    step_delta = timedelta(minutes=step_minutes)

    forecasts = db.query(Forecast).filter(
        Forecast.site_id == site_id
    ).order_by(Forecast.timestamp.asc()).all()

    # Staleness check: verify forecast exists and starts at latest_reading.timestamp + step_delta
    is_stale = False
    if not forecasts or not latest_reading:
        is_stale = True
    else:
        expected_first_ts = latest_reading.timestamp + step_delta
        # If first forecast does not match expected next interval, regenerate
        if forecasts[0].timestamp != expected_first_ts:
            is_stale = True

    if is_stale:
        forecasts = generate_forecasts_for_site(site_id, db, horizon_hours=horizon_hours)

    model_name = forecasts[0].model if forecasts else "XGBoost"

    # Fetch model evaluation metrics
    metrics = MODEL_COMPARISON_TABLE.get(site_id)
    if not metrics:
        metrics = {"active_model": get_analytics_metrics(site_id, db)}

    points = [
        ForecastPoint(
            timestamp=f.timestamp.isoformat(),
            predicted_kw=f.predicted_kw,
            confidence_low_kw=f.confidence_low_kw,
            confidence_high_kw=f.confidence_high_kw
        )
        for f in forecasts
    ]

    return ForecastResponse(
        site_id=site.id,
        model_used=model_name,
        evaluation_metrics=metrics,
        points_count=len(points),
        points=points
    )
