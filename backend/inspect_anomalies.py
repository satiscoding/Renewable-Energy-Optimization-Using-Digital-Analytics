import numpy as np
from app.db.session import SessionLocal
from app.db.models import SensorReading, WeatherReading, Site
from app.services.analytics import (
    train_solar_model,
    evaluate_wind_model,
    SUSTAINED_SHORTFALL_THRESHOLD_PCT,
    MIN_SHORTFALL_KW,
    MIN_EXPECTED_KW,
    PERSISTENCE_INTERVALS
)

def run_inspection():
    db = SessionLocal()
    print("=== 1. CHECK EXPECTED-OUTPUT MODEL FEATURES & PERFORMANCE ===")
    _, solar_metrics = train_solar_model(db)
    print("Solar Model Metrics (RandomForest on [irrad, mod_temp, hour, doy] ONLY):")
    print(f"  Train R2: {solar_metrics.get('train_r2')} | Test R2: {solar_metrics.get('test_r2')} | MAE: {solar_metrics.get('mae')} kW | RMSE: {solar_metrics.get('rmse')} kW")

    wind_metrics = evaluate_wind_model(db)
    print("Wind Model Metrics (Theoretical Power Curve on [wind_speed] ONLY):")
    print(f"  Train R2: {wind_metrics.get('train_r2')} | Test R2: {wind_metrics.get('test_r2')} | MAE: {wind_metrics.get('mae')} kW | RMSE: {wind_metrics.get('rmse')} kW")

    print("\n=== 2. INSPECT LAST 50 INTERVALS FOR BOTH SITES ===")
    for site_id in ["solar-plant-1", "wind-alpha"]:
        readings = db.query(SensorReading).filter(SensorReading.site_id == site_id).order_by(SensorReading.timestamp.desc()).limit(50).all()
        readings = list(reversed(readings))
        print(f"\n--- Site: {site_id} (Last {len(readings)} intervals) ---")
        print(f"{'Timestamp':<17} | {'Actual(kW)':<11} | {'Expect(kW)':<11} | {'Residual(kW)':<13} | {'Threshold(kW)':<14} | {'PersistCount':<13} | {'Flagged'}")
        print("-" * 92)

        persist_count = 0
        for r in readings:
            exp = r.expected_power_kw if r.expected_power_kw is not None else 0.0
            act = r.ac_power_kw
            res = round(act - exp, 2) # actual - expected (negative = underperforming)
            shortfall = max(0.0, exp - act)

            # Threshold definition: at least 10% of expected and at least 25 kW
            threshold_kw = max(MIN_SHORTFALL_KW, round(exp * SUSTAINED_SHORTFALL_THRESHOLD_PCT, 2)) if exp >= MIN_EXPECTED_KW else 0.0

            if exp >= MIN_EXPECTED_KW and shortfall >= threshold_kw and threshold_kw > 0:
                persist_count += 1
            else:
                persist_count = 0

            is_flagged = bool(persist_count >= PERSISTENCE_INTERVALS)
            ts_str = r.timestamp.strftime("%Y-%m-%d %H:%M")
            print(f"{ts_str:<17} | {act:<11.1f} | {exp:<11.1f} | {res:<13.1f} | {threshold_kw:<14.1f} | {persist_count:<13} | {is_flagged}")

    db.close()

if __name__ == "__main__":
    run_inspection()
