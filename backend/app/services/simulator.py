"""Live Telemetry Simulator: pushes live readings every 5s with controllable anomaly injections."""
import asyncio
import logging
import random
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.models import Site, SensorReading, WeatherReading
from app.db.session import SessionLocal
from app.services.analytics import calculate_expected_power, analyze_point_discrepancy, WIND_CUT_IN_MS, WIND_CUT_OUT_MS
from app.services.recommendation_engine import run_recommendation_pipeline
from app.services.forecaster import generate_forecasts_for_site

logger = logging.getLogger("control_room.simulator")

ANOMALY_OVERRIDE: Dict[str, str] = {
    "solar-plant-1": "normal",
    "wind-alpha": "normal"
}

def inject_anomaly_mode(site_id: str, mode: str):
    """Set the anomaly mode for a site ('normal', 'soiling', 'sudden_drop', 'wind_shortfall')."""
    ANOMALY_OVERRIDE[site_id] = mode
    logger.info(f"Set anomaly mode for {site_id} to '{mode}'")


def step_simulation_for_site(
    site_id: str,
    db: Session,
    target_time: Optional[datetime] = None,
    regen_forecast: bool = True,
    run_recommendations: bool = True
) -> Dict[str, Any]:
    """Advance site state by one reading step, calculating actual, expected, daily yield and checking rules."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        return {}

    last_reading = db.query(SensorReading).filter(
        SensorReading.site_id == site_id
    ).order_by(SensorReading.timestamp.desc()).first()

    step_minutes = 15 if site.type == "solar" else 10
    mode = ANOMALY_OVERRIDE.get(site_id, "normal")

    if target_time:
        next_ts = target_time
    elif last_reading:
        next_ts = last_reading.timestamp + timedelta(minutes=step_minutes)
    else:
        next_ts = datetime.utcnow()

    # For solar demonstration: if an anomaly is injected or time is outside daylight, jump to active daylight (11:00 AM)
    if site.type == "solar" and (next_ts.hour < 8 or next_ts.hour >= 16):
        next_day = (last_reading.timestamp + timedelta(days=1)).date() if last_reading else datetime.utcnow().date()
        next_ts = datetime(next_day.year, next_day.month, next_day.day, 11, 0)

    hour = next_ts.hour + next_ts.minute / 60.0

    # Generate synthetic weather
    if site.type == "solar":
        if 6.0 <= hour <= 18.25:
            sun_angle = math.sin((hour - 6.0) / 12.25 * math.pi)
            irrad = max(0.0, sun_angle * 0.92 + random.uniform(-0.02, 0.02))
            amb_temp = round(24.0 + sun_angle * 10.0 + random.uniform(-0.5, 0.5), 1)
            mod_temp = round(amb_temp + irrad * 28.0 + random.uniform(-1.0, 1.0), 1)
        else:
            irrad = 0.0
            amb_temp = round(21.0 + random.uniform(-0.5, 0.5), 1)
            mod_temp = amb_temp

        weather_entry = WeatherReading(
            site_id=site_id,
            timestamp=next_ts,
            irradiation=round(irrad, 4),
            module_temp=mod_temp,
            ambient_temp=amb_temp,
            wind_speed=None,
            wind_direction=None
        )
        db.add(weather_entry)
        db.flush()

        expected_kw = calculate_expected_power("solar", db, weather_entry, next_ts)

        if expected_kw <= 5.0:
            actual_kw = 0.0
        elif mode == "sudden_drop":
            actual_kw = round(expected_kw * 0.06, 2)
        elif mode == "soiling":
            # 18-25% drop (exceeds the 10-15% threshold reliably)
            actual_kw = round(expected_kw * 0.78, 2)
        else:
            actual_kw = round(expected_kw * random.uniform(0.97, 1.01), 2)

        type_data = {"dc_power_kw": round(actual_kw * 1.025, 2)}
        interval_hours = 0.25

    else:
        # Wind site
        base_ws = 8.5 + 2.0 * math.sin(hour / 24.0 * 2 * math.pi) + random.uniform(-0.8, 0.8)
        ws = max(3.5, min(24.0, round(base_ws, 2)))
        wd = round((180.0 + 30.0 * math.cos(hour / 12.0) + random.uniform(-8, 8)) % 360, 1)

        weather_entry = WeatherReading(
            site_id=site_id,
            timestamp=next_ts,
            irradiation=None,
            module_temp=None,
            ambient_temp=17.0,
            wind_speed=ws,
            wind_direction=wd
        )
        db.add(weather_entry)
        db.flush()

        expected_kw = calculate_expected_power("wind", db, weather_entry, next_ts)

        if expected_kw <= 5.0:
            actual_kw = 0.0
        elif mode == "sudden_drop":
            actual_kw = round(expected_kw * 0.05, 2)
        elif mode == "wind_shortfall":
            # 22% shortfall
            actual_kw = round(expected_kw * 0.78, 2)
        else:
            actual_kw = round(expected_kw * random.uniform(0.96, 1.02), 2)

        type_data = {"theoretical_power_kw": expected_kw}
        interval_hours = 10.0 / 60.0

    # Trapezoidal daily yield (reset at midnight)
    if last_reading and last_reading.timestamp.date() == next_ts.date():
        prior_daily = last_reading.daily_yield_kwh or 0.0
        daily_yield_kwh = round(prior_daily + (actual_kw * interval_hours), 2)
    else:
        daily_yield_kwh = round(actual_kw * interval_hours, 2)

    discrepancy = analyze_point_discrepancy(
        site.type,
        actual_kw,
        expected_kw,
        weather_entry.wind_speed
    )
    is_anomaly = 1 if discrepancy["is_shortfall"] else 0

    reading = SensorReading(
        site_id=site_id,
        timestamp=next_ts,
        ac_power_kw=actual_kw,
        daily_yield_kwh=daily_yield_kwh,
        expected_power_kw=expected_kw,
        is_anomaly=is_anomaly,
        type_specific_data=type_data
    )
    db.add(reading)
    db.commit()

    # Re-evaluate recommendations
    if run_recommendations:
        run_recommendation_pipeline(site_id, db)

    # Regenerate forward forecast to keep aligned with new interval if requested
    if regen_forecast:
        generate_forecasts_for_site(site_id, db, horizon_hours=6)

    return {
        "site_id": site_id,
        "timestamp": next_ts.isoformat(),
        "actual_kw": actual_kw,
        "expected_kw": expected_kw,
        "daily_yield_kwh": daily_yield_kwh,
        "mode": mode,
        "is_anomaly": is_anomaly
    }


def step_all_sites(db: Session) -> Dict[str, Any]:
    """Advance simulation for both solar and wind sites."""
    res_solar = step_simulation_for_site("solar-plant-1", db)
    res_wind = step_simulation_for_site("wind-alpha", db)
    return {"solar": res_solar, "wind": res_wind}


async def simulation_loop(interval_seconds: int = 5):
    """Background task running continuously every 5 seconds."""
    logger.info(f"Starting background live feed simulator loop ({interval_seconds}s ticks)...")
    while True:
        db = SessionLocal()
        try:
            step_all_sites(db)
        except Exception as e:
            logger.error(f"Error in live feed simulator: {e}")
        finally:
            db.close()
        await asyncio.sleep(interval_seconds)
