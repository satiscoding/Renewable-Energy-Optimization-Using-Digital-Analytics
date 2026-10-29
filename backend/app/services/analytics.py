"""Analytics Engine: Expected vs Actual generation, wind edge cases, and tuned anomaly detection."""
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy.orm import Session

from app.db.models import SensorReading, WeatherReading, Site
from app.db.session import SessionLocal

logger = logging.getLogger("control_room.analytics")

# Wind turbine specifications (Vestas / standard 2050 kW SCADA turbine)
WIND_CUT_IN_MS = 3.0
WIND_CUT_OUT_MS = 25.0
WIND_RATED_WS_MS = 13.0
WIND_RATED_KW = 2050.0

# Threshold constants:
# Minimum sustained drop percentage to flag an anomaly (10-15%)
SUSTAINED_SHORTFALL_THRESHOLD_PCT = 0.10 # 10% sustained drop
MIN_SHORTFALL_KW = 25.0                 # Reject minor <25 kW sensor drift
MIN_EXPECTED_KW = 50.0                  # Below 50 kW is idle/low baseline
PERSISTENCE_INTERVALS = 3               # Minimum consecutive intervals to reject transient passing clouds

_solar_model = None
_solar_metrics: Dict[str, float] = {}
_wind_metrics: Dict[str, float] = {}

def get_wind_theoretical_power(wind_speed: float) -> float:
    """Theoretical power curve for wind turbine with physical boundary enforcement.
    Strictly uses ONLY wind_speed (no lag or actual power features).
    """
    if wind_speed < WIND_CUT_IN_MS or wind_speed > WIND_CUT_OUT_MS:
        return 0.0
    if wind_speed >= WIND_RATED_WS_MS:
        return WIND_RATED_KW
    fraction = (wind_speed - WIND_CUT_IN_MS) / (WIND_RATED_WS_MS - WIND_CUT_IN_MS)
    return round(WIND_RATED_KW * (fraction ** 2.4), 2)


def train_solar_model(db: Session) -> Tuple[Any, Dict[str, float]]:
    """Train RandomForestRegressor for solar plant expected AC power using ONLY weather and time features.
    Features: [irradiation, module_temp, hour, day_of_year].
    NO lag or rolling features of actual power are included.
    """
    global _solar_model, _solar_metrics
    if _solar_model is not None:
        return _solar_model, _solar_metrics

    q = db.query(
        SensorReading.timestamp,
        SensorReading.ac_power_kw,
        WeatherReading.irradiation,
        WeatherReading.module_temp
    ).join(
        WeatherReading,
        (SensorReading.site_id == WeatherReading.site_id) & (SensorReading.timestamp == WeatherReading.timestamp)
    ).filter(
        SensorReading.site_id == "solar-plant-1"
    ).order_by(SensorReading.timestamp.asc()).all()

    if not q:
        logger.warning("No solar training data available.")
        return None, {}

    feature_rows = []
    target_vals = []

    for r in q:
        if r.irradiation is not None and r.module_temp is not None:
            hour = r.timestamp.hour + r.timestamp.minute / 60.0
            doy = r.timestamp.timetuple().tm_yday
            # Strictly weather & time features ONLY
            feature_rows.append([r.irradiation, r.module_temp, hour, doy])
            target_vals.append(r.ac_power_kw)

    if len(feature_rows) < 20:
        return None, {}

    X = np.array(feature_rows, dtype=np.float32)
    y = np.array(target_vals, dtype=np.float32)

    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    model = RandomForestRegressor(n_estimators=35, max_depth=10, random_state=42, n_jobs=1)
    model.fit(X_train, y_train)

    y_train_pred = np.clip(model.predict(X_train), 0.0, 3500.0)
    y_test_pred = np.clip(model.predict(X_test), 0.0, 3500.0)

    train_r2 = float(r2_score(y_train, y_train_pred))
    test_r2 = float(r2_score(y_test, y_test_pred))
    test_mae = float(mean_absolute_error(y_test, y_test_pred))
    test_rmse = float(np.sqrt(mean_squared_error(y_test, y_test_pred)))

    _solar_model = model
    _solar_metrics = {
        "train_r2": round(train_r2, 4),
        "test_r2": round(test_r2, 4),
        "r2": round(test_r2, 4),
        "mae": round(test_mae, 2),
        "rmse": round(test_rmse, 2)
    }
    logger.info(f"Solar model trained. Train R2: {train_r2:.4f}, Test R2: {test_r2:.4f}, Test MAE: {test_mae:.2f} kW")
    return model, _solar_metrics


def evaluate_wind_model(db: Session) -> Dict[str, float]:
    """Evaluate theoretical power curve against historical SCADA data.
    Uses ONLY wind speed (aerodynamic power curve).
    """
    global _wind_metrics
    if _wind_metrics:
        return _wind_metrics

    q = db.query(
        SensorReading.ac_power_kw,
        WeatherReading.wind_speed
    ).join(
        WeatherReading,
        (SensorReading.site_id == WeatherReading.site_id) & (SensorReading.timestamp == WeatherReading.timestamp)
    ).filter(
        SensorReading.site_id == "wind-alpha"
    ).all()

    if not q:
        return {}

    y_true = []
    y_pred = []

    for r in q:
        if r.wind_speed is not None:
            y_true.append(r.ac_power_kw)
            y_pred.append(get_wind_theoretical_power(r.wind_speed))

    if not y_true:
        return {}

    y_true_arr = np.array(y_true, dtype=np.float32)
    y_pred_arr = np.array(y_pred, dtype=np.float32)

    split_idx = int(len(y_true_arr) * 0.8)
    y_train, y_test = y_true_arr[:split_idx], y_true_arr[split_idx:]
    p_train, p_test = y_pred_arr[:split_idx], y_pred_arr[split_idx:]

    train_r2 = float(r2_score(y_train, p_train))
    test_r2 = float(r2_score(y_test, p_test))
    test_mae = float(mean_absolute_error(y_test, p_test))
    test_rmse = float(np.sqrt(mean_squared_error(y_test, p_test)))

    _wind_metrics = {
        "train_r2": round(train_r2, 4),
        "test_r2": round(test_r2, 4),
        "r2": round(test_r2, 4),
        "mae": round(test_mae, 2),
        "rmse": round(test_rmse, 2)
    }
    logger.info(f"Wind theoretical curve evaluated. Train R2: {train_r2:.4f}, Test R2: {test_r2:.4f}, Test MAE: {test_mae:.2f} kW")
    return _wind_metrics


def calculate_expected_power(
    site_type: str,
    db: Session,
    weather: Optional[WeatherReading],
    timestamp: datetime
) -> float:
    """Calculate expected power in kW strictly respecting plant physics and edge cases.
    ONLY uses weather and time features.
    """
    if not weather:
        return 0.0

    if site_type == "solar":
        hour = timestamp.hour + timestamp.minute / 60.0
        if hour < 5.75 or hour > 18.5 or (weather.irradiation is not None and weather.irradiation <= 0.005):
            return 0.0

        model, _ = train_solar_model(db)
        if model is None:
            irrad = weather.irradiation or 0.0
            return round(irrad * 2850.0, 2)

        feat = np.array([[
            weather.irradiation or 0.0,
            weather.module_temp if weather.module_temp is not None else 25.0,
            hour,
            timestamp.timetuple().tm_yday
        ]], dtype=np.float32)
        pred = float(model.predict(feat)[0])
        return round(max(0.0, min(3000.0, pred)), 2)

    elif site_type == "wind":
        ws = weather.wind_speed or 0.0
        if ws < WIND_CUT_IN_MS or ws > WIND_CUT_OUT_MS:
            return 0.0
        return get_wind_theoretical_power(ws)

    return 0.0


def analyze_point_discrepancy(
    site_type: str,
    actual_kw: float,
    expected_kw: float,
    wind_speed: Optional[float] = None
) -> Dict[str, Any]:
    """Analyze gap between actual and expected power, handling all edge cases."""
    # EDGE CASE 1: Wind below cut-in (<3 m/s) or above cut-out (>25 m/s)
    if site_type == "wind" and (wind_speed is not None and (wind_speed < WIND_CUT_IN_MS or wind_speed > WIND_CUT_OUT_MS)):
        return {
            "gap_kw": 0.0,
            "gap_pct": 0.0,
            "is_shortfall": False,
            "status": "normal_cut_in_out",
            "notes": "Legitimate idle below cut-in or cut-out protection. No alert."
        }

    # EDGE CASE 2: Expected is legitimately near zero (night for solar or calm wind)
    if expected_kw < MIN_EXPECTED_KW:
        return {
            "gap_kw": 0.0,
            "gap_pct": 0.0,
            "is_shortfall": False,
            "status": "nominal_idle",
            "notes": "Low expected baseline. No alert."
        }

    # EDGE CASE 3: Actual exceeds expected by >30% (data/model mismatch, NOT underperformance)
    if actual_kw > expected_kw * 1.3:
        return {
            "gap_kw": round(expected_kw - actual_kw, 2),
            "gap_pct": round(((expected_kw - actual_kw) / expected_kw) * 100.0, 2),
            "is_shortfall": False,
            "status": "model_mismatch_review",
            "notes": "Generation exceeds model expectation significantly. Review calibration."
        }

    gap_kw = round(expected_kw - actual_kw, 2)
    gap_pct = round((gap_kw / max(1.0, expected_kw)) * 100.0, 2)
    
    # An interval is a candidate shortfall if gap is at least 10% and at least 25 kW
    is_shortfall = (gap_pct >= (SUSTAINED_SHORTFALL_THRESHOLD_PCT * 100.0)) and (gap_kw >= MIN_SHORTFALL_KW)

    return {
        "gap_kw": gap_kw,
        "gap_pct": gap_pct,
        "is_shortfall": is_shortfall,
        "status": "underperforming" if is_shortfall else "nominal",
        "notes": ""
    }


def detect_anomalies_time_series(
    actuals: List[float],
    expecteds: List[float],
    min_consecutive: int = PERSISTENCE_INTERVALS,
    shortfall_threshold_pct: float = SUSTAINED_SHORTFALL_THRESHOLD_PCT,
    min_gap_kw: float = MIN_SHORTFALL_KW,
    min_expected_kw: float = MIN_EXPECTED_KW
) -> List[int]:
    """Flag sustained anomalies.
    Tuned so that:
    - Passing clouds or momentary dips (1-2 intervals) are NOT flagged.
    - Small dips (< 10%) are NOT flagged.
    - 10-15% sustained shortfall for >= min_consecutive intervals IS flagged.
    """
    n = len(actuals)
    raw_flags = np.zeros(n, dtype=bool)

    for i in range(n):
        exp = expecteds[i]
        act = actuals[i]
        if exp >= min_expected_kw:
            gap = exp - act
            pct = gap / exp
            if pct >= shortfall_threshold_pct and gap >= min_gap_kw:
                raw_flags[i] = True

    persistent_flags = [0] * n
    for i in range(min_consecutive - 1, n):
        if np.all(raw_flags[i - min_consecutive + 1 : i + 1]):
            persistent_flags[i] = 1

    return persistent_flags


def get_analytics_metrics(site_id: str, db: Session) -> Dict[str, Any]:
    """Retrieve model performance metrics."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        return {}

    if site.type == "solar":
        _, metrics = train_solar_model(db)
        return metrics
    elif site.type == "wind":
        return evaluate_wind_model(db)
    return {}
