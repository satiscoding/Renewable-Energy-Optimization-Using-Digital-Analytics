"""Simulator control endpoint: interactive tick step and anomaly injector for testing and demonstrations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.schemas import AnomalyInjectRequest, SimulatorTickResponse
from app.services.simulator import step_all_sites, step_simulation_for_site, inject_anomaly_mode
from app.services.recommendation_engine import resolve_recommendation_if_active

router = APIRouter(prefix="/simulator", tags=["Simulator"])

@router.post("/tick", response_model=SimulatorTickResponse)
def trigger_simulator_tick(db: Session = Depends(get_db)):
    """Advance simulation one step for all sites."""
    results = step_all_sites(db)
    return SimulatorTickResponse(status="success", results=results)

@router.post("/anomaly")
def set_site_anomaly(payload: AnomalyInjectRequest, db: Session = Depends(get_db)):
    """Inject anomaly mode for demo testing ('normal', 'soiling', 'sudden_drop', 'wind_shortfall').
    Applies the anomaly, steps the site so persistence requirements are met, and updates recommendation states.
    """
    valid_modes = ["normal", "soiling", "sudden_drop", "wind_shortfall"]
    if payload.anomaly_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid anomaly mode. Must be one of {valid_modes}")

    inject_anomaly_mode(payload.site_id, payload.anomaly_mode)

    if payload.anomaly_mode == "normal":
        # Advance 4 nominal steps so history sliding window is clean nominal telemetry
        for _ in range(4):
            step_simulation_for_site(payload.site_id, db, regen_forecast=False, run_recommendations=False)

        # Resolve all active anomaly recommendations for this site
        resolve_recommendation_if_active(payload.site_id, "soiling", db)
        resolve_recommendation_if_active(payload.site_id, "shading", db)
        resolve_recommendation_if_active(payload.site_id, "sudden_drop", db)
        resolve_recommendation_if_active(payload.site_id, "wind_shortfall", db)
        db.commit()
    else:
        # Advance 3 intervals under anomaly mode to satisfy persistence
        for _ in range(3):
            step_simulation_for_site(payload.site_id, db, regen_forecast=False, run_recommendations=True)

    return {"status": "success", "site_id": payload.site_id, "anomaly_mode": payload.anomaly_mode}
