"""Type-aware Recommendation Engine: gap shape pattern diagnosis and de-duplicated lifecycle management."""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import numpy as np
from sqlalchemy.orm import Session

from app.db.models import Recommendation, SensorReading, WeatherReading, Forecast, Site
from app.services.analytics import WIND_CUT_IN_MS, WIND_CUT_OUT_MS

logger = logging.getLogger("control_room.recommendations")

def format_relative_time(dt_utc: datetime) -> str:
    """Format UTC datetime into human relative time ('Just now', '12 min ago', '3 hours ago', '1 day ago').
    Ensures no future phrases appear for detected events.
    """
    now = datetime.utcnow()
    diff_seconds = max(0, int((now - dt_utc).total_seconds()))

    if diff_seconds < 60:
        return "Just now"
    elif diff_seconds < 3600:
        minutes = diff_seconds // 60
        return f"{minutes} min ago" if minutes > 1 else "1 min ago"
    elif diff_seconds < 86400:
        hours = diff_seconds // 3600
        return f"{hours} hours ago" if hours > 1 else "1 hour ago"
    else:
        days = diff_seconds // 86400
        return f"{days} days ago" if days > 1 else "1 day ago"


def resolve_recommendation_if_active(site_id: str, issue_type: str, db: Session):
    """Mark an active issue as resolved when telemetry returns to nominal."""
    recs = db.query(Recommendation).filter(
        Recommendation.site_id == site_id,
        Recommendation.issue_type == issue_type,
        Recommendation.status == "active"
    ).all()
    for rec in recs:
        rec.status = "resolved"
        rec.resolved_at = datetime.utcnow()
    if recs:
        db.commit()
        logger.info(f"Resolved {len(recs)} active issue(s) '{issue_type}' for site '{site_id}'.")


def add_recommendation_if_new(
    site_id: str,
    severity: str,
    issue_type: str,
    reason: str,
    action: str,
    db: Session
) -> Optional[Recommendation]:
    """Create a new recommendation only if an active issue of this type does not already exist."""
    existing = db.query(Recommendation).filter(
        Recommendation.site_id == site_id,
        Recommendation.issue_type == issue_type,
        Recommendation.status == "active"
    ).first()

    if existing:
        return None

    rec = Recommendation(
        site_id=site_id,
        severity=severity,
        issue_type=issue_type,
        reason=reason,
        action=action,
        status="active",
        created_at=datetime.utcnow()
    )
    db.add(rec)
    db.commit()
    logger.info(f"Created recommendation: [{severity.upper()}] {issue_type} for {site_id}")
    return rec


def evaluate_solar_recommendations(site_id: str, db: Session):
    """Diagnose solar site generation anomalies based on shortfall curve shape."""
    history = db.query(
        SensorReading.id,
        SensorReading.timestamp,
        SensorReading.ac_power_kw,
        SensorReading.expected_power_kw,
        WeatherReading.irradiation
    ).outerjoin(
        WeatherReading,
        (SensorReading.site_id == WeatherReading.site_id) & (SensorReading.timestamp == WeatherReading.timestamp)
    ).filter(
        SensorReading.site_id == site_id
    ).order_by(SensorReading.timestamp.desc(), SensorReading.id.desc()).limit(192).all()

    if len(history) < 4:
        return

    history = sorted(history, key=lambda x: (x.timestamp, x.id))
    daylight_records = []

    for r in history:
        hour = r.timestamp.hour + r.timestamp.minute / 60.0
        irrad = r.irradiation or 0.0
        exp = r.expected_power_kw or 0.0
        act = r.ac_power_kw

        # Analyze daylight windows
        if 8.0 <= hour <= 17.5 and (irrad > 0.10 or exp > 100.0):
            ratio = act / max(10.0, exp)
            daylight_records.append({
                "timestamp": r.timestamp,
                "hour": r.timestamp.hour,
                "actual": act,
                "expected": exp,
                "ratio": ratio
            })

    if not daylight_records:
        return

    recent_daylight = daylight_records[-3:] if len(daylight_records) >= 3 else daylight_records
    avg_recent_ratio = float(np.mean([d["ratio"] for d in recent_daylight]))
    latest_actual = recent_daylight[-1]["actual"]
    latest_expected = recent_daylight[-1]["expected"]

    # RULE 1: Sudden near-total drop (Fault / Inverter Trip)
    if latest_expected > 100.0 and (latest_actual / latest_expected) < 0.20:
        add_recommendation_if_new(
            site_id=site_id,
            severity="critical",
            issue_type="sudden_drop",
            reason=f"Sudden generation collapse detected: generating only {latest_actual:.0f} kW despite {latest_expected:.0f} kW solar potential.",
            action="Send technician to inspect plant junction boxes, DC disconnect switches, and central inverters.",
            db=db
        )
    else:
        resolve_recommendation_if_active(site_id, "sudden_drop", db)

    # RULE 2: Soiling / Dust accumulation (Consistent 10-45% shortfall across >=3 daylight steps)
    if len(recent_daylight) >= 3 and 0.40 <= avg_recent_ratio <= 0.90:
        shortfall_pct = (1.0 - avg_recent_ratio) * 100.0
        add_recommendation_if_new(
            site_id=site_id,
            severity="warning",
            issue_type="soiling",
            reason=f"Consistent {shortfall_pct:.1f}% daylight generation shortfall below benchmark indicates panel dust/particulate accumulation.",
            action="Clean panels / check for soiling across array blocks 1-4.",
            db=db
        )
    elif avg_recent_ratio > 0.92:
        resolve_recommendation_if_active(site_id, "soiling", db)

    # RULE 3: Partial shading recurring at same time of day across multiple distinct days
    if len(daylight_records) >= 12:
        hourly_records: Dict[int, List[Dict[str, Any]]] = {}
        for d in daylight_records:
            h = d["hour"]
            if h not in hourly_records:
                hourly_records[h] = []
            hourly_records[h].append(d)

        shaded_detected = False
        for h, rec_list in hourly_records.items():
            distinct_days = set(r["timestamp"].date() for r in rec_list)
            ratios = [r["ratio"] for r in rec_list]
            if len(distinct_days) >= 3 and np.mean(ratios) < 0.65 and avg_recent_ratio > 0.88:
                add_recommendation_if_new(
                    site_id=site_id,
                    severity="warning",
                    issue_type="shading",
                    reason=f"Consistent localized production dip recurring daily near {h:02d}:00 across {len(distinct_days)} days indicates physical obstruction or row-to-row shading.",
                    action="Partial shading suspected: verify perimeter tree growth or nearby construction silhouettes.",
                    db=db
                )
                shaded_detected = True
                break

        if not shaded_detected:
            resolve_recommendation_if_active(site_id, "shading", db)

    # RULE 4: Peak Generation Forecast Advisory (Energy shifting)
    upcoming = db.query(Forecast).filter(
        Forecast.site_id == site_id,
        Forecast.timestamp > datetime.utcnow()
    ).order_by(Forecast.timestamp.asc()).limit(16).all()

    if upcoming:
        afternoon_peaks = [f for f in upcoming if 12 <= f.timestamp.hour <= 15 and f.predicted_kw > 1500.0]
        if afternoon_peaks:
            add_recommendation_if_new(
                site_id=site_id,
                severity="info",
                issue_type="shift_load",
                reason="Solar irradiance peaks in the afternoon window with forecasted output exceeding 1,500 kW.",
                action="Shift high-load usage to the afternoon window (12:00 - 15:30) to maximize on-site self-consumption.",
                db=db
            )


def evaluate_wind_recommendations(site_id: str, db: Session):
    """Diagnose wind turbine operational anomalies based on SCADA power curve gaps."""
    history = db.query(
        SensorReading.id,
        SensorReading.timestamp,
        SensorReading.ac_power_kw,
        SensorReading.expected_power_kw
    ).filter(
        SensorReading.site_id == site_id
    ).order_by(SensorReading.timestamp.desc(), SensorReading.id.desc()).limit(24).all()

    if len(history) < 4:
        return

    history = sorted(history, key=lambda x: (x.timestamp, x.id))
    last_ts = history[-1].timestamp

    ws_row = db.query(WeatherReading.wind_speed).filter(
        WeatherReading.site_id == site_id,
        WeatherReading.timestamp == last_ts
    ).first()
    latest_ws = ws_row[0] if ws_row and ws_row[0] is not None else 7.0

    latest_actual = history[-1].ac_power_kw
    latest_expected = history[-1].expected_power_kw or 0.0

    # EDGE CASE: below cut-in (<3 m/s) or above cut-out (>25 m/s)
    if latest_ws < WIND_CUT_IN_MS or latest_ws > WIND_CUT_OUT_MS:
        resolve_recommendation_if_active(site_id, "wind_shortfall", db)
        resolve_recommendation_if_active(site_id, "sudden_drop", db)
        return

    # RULE 1: Sudden drop while wind speed is adequate
    if latest_ws >= 5.0 and latest_expected > 150.0 and latest_actual < 80.0:
        add_recommendation_if_new(
            site_id=site_id,
            severity="critical",
            issue_type="sudden_drop",
            reason=f"Turbine output collapsed to {latest_actual:.0f} kW despite favorable wind speed of {latest_ws:.1f} m/s.",
            action="Possible fault: send technician to check hydraulic pitch actuator and safety trip circuit.",
            db=db
        )
    else:
        resolve_recommendation_if_active(site_id, "sudden_drop", db)

    # RULE 2: Persistent shortfall vs theoretical power curve (>= 3 intervals)
    recent_readings = history[-3:] if len(history) >= 3 else history
    shortfalls = []
    for r in recent_readings:
        exp = r.expected_power_kw or 0.0
        act = r.ac_power_kw
        if exp >= 50.0:
            shortfalls.append((exp - act) / exp)

    if len(shortfalls) >= 3:
        avg_shortfall = float(np.mean(shortfalls))
        if avg_shortfall >= 0.10: # Sustained 10%+ shortfall
            add_recommendation_if_new(
                site_id=site_id,
                severity="warning",
                issue_type="wind_shortfall",
                reason=f"Persistent {avg_shortfall*100:.1f}% underperformance relative to aerodynamic power curve over recent intervals.",
                action="Schedule routine generator / rotor inspection and blade angle calibration.",
                db=db
            )
        elif avg_shortfall < 0.08:
            resolve_recommendation_if_active(site_id, "wind_shortfall", db)

    # RULE 3: Low wind forecast advisory
    upcoming = db.query(Forecast).filter(
        Forecast.site_id == site_id,
        Forecast.timestamp > datetime.utcnow()
    ).order_by(Forecast.timestamp.asc()).limit(12).all()

    if upcoming and all(f.predicted_kw < 80.0 for f in upcoming):
        add_recommendation_if_new(
            site_id=site_id,
            severity="info",
            issue_type="low_wind",
            reason="Atmospheric forecasts indicate an extended lull (<3.0 m/s) over the next 4 hours.",
            action="Reduce non-essential auxiliary load and prepare for grid standby mode.",
            db=db
        )
    else:
        resolve_recommendation_if_active(site_id, "low_wind", db)


def run_recommendation_pipeline(site_id: str, db: Session):
    """Run type-aware diagnostic evaluation for the site."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        return

    if site.type == "solar":
        evaluate_solar_recommendations(site_id, db)
    elif site.type == "wind":
        evaluate_wind_recommendations(site_id, db)
