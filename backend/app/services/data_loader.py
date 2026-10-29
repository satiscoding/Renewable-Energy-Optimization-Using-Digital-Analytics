"""Historical dataset ingestion, data cleaning, gap interpolation, and DB seeding."""
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.config import BUNDLED_DATA_DIR, RAW_DATA_DIR
from app.db.models import Site, SensorReading, WeatherReading
from app.db.session import SessionLocal

logger = logging.getLogger("control_room.data_loader")
logging.basicConfig(level=logging.INFO)

SOLAR_SITE_ID = "solar-plant-1"
WIND_SITE_ID = "wind-alpha"

WIND_CUT_IN_MS = 3.0
WIND_CUT_OUT_MS = 25.0
WIND_RATED_WS_MS = 13.0
WIND_RATED_KW = 2050.0

def get_wind_theoretical_power_quick(wind_speed: float) -> float:
    """Theoretical power curve for wind turbine."""
    if wind_speed < WIND_CUT_IN_MS or wind_speed > WIND_CUT_OUT_MS:
        return 0.0
    if wind_speed >= WIND_RATED_WS_MS:
        return WIND_RATED_KW
    fraction = (wind_speed - WIND_CUT_IN_MS) / (WIND_RATED_WS_MS - WIND_CUT_IN_MS)
    return round(WIND_RATED_KW * (fraction ** 2.4), 2)


def get_solar_expected_power_quick(irrad: float, mod_temp: Optional[float], hour: float) -> float:
    """Physics-informed expected AC power (kW) for 3000 kW solar plant."""
    if hour < 5.75 or hour > 18.5 or irrad <= 0.005:
        return 0.0
    # Standard temperature coefficient: -0.4%/°C above 25°C STC
    t_cell = mod_temp if (mod_temp is not None and not np.isnan(mod_temp)) else 25.0
    temp_derate = max(0.80, 1.0 - (t_cell - 25.0) * 0.004)
    # 3000 kW DC capacity at 1000 W/m² (1.0 kW/m²) * inverter efficiency ~0.97
    expected = irrad * 2920.0 * temp_derate
    return round(min(3000.0, max(0.0, expected)), 2)


def parse_flexible_dt(s: str) -> Optional[datetime]:
    """Parse date-time across common Kaggle CSV formats."""
    s = s.strip()
    formats = [
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d %m %Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def interpolate_short_gaps_1d(values: List[Optional[float]], max_consecutive: int = 3) -> List[Optional[float]]:
    """Linearly interpolate missing segments of length <= max_consecutive."""
    n = len(values)
    res = list(values)
    i = 0
    while i < n:
        if res[i] is None:
            start_idx = i
            while i < n and res[i] is None:
                i += 1
            gap_len = i - start_idx
            if gap_len <= max_consecutive and start_idx > 0 and i < n and res[start_idx - 1] is not None and res[i] is not None:
                v_start = res[start_idx - 1]
                v_end = res[i]
                for k in range(gap_len):
                    frac = (k + 1) / (gap_len + 1)
                    res[start_idx + k] = round(v_start + frac * (v_end - v_start), 3)
        else:
            i += 1
    return res


def seed_sites(db: Session):
    """Seed multi-site definitions if they do not exist."""
    solar_site = db.query(Site).filter(Site.id == SOLAR_SITE_ID).first()
    if not solar_site:
        solar_site = Site(
            id=SOLAR_SITE_ID,
            name="Solar Plant 1",
            type="solar",
            capacity_kw=3000.0,
            aggregation_level="plant_total",
            created_at=datetime.utcnow()
        )
        db.add(solar_site)

    wind_site = db.query(Site).filter(Site.id == WIND_SITE_ID).first()
    if not wind_site:
        wind_site = Site(
            id=WIND_SITE_ID,
            name="Wind Turbine Alpha",
            type="wind",
            capacity_kw=2050.0,
            aggregation_level="turbine",
            created_at=datetime.utcnow()
        )
        db.add(wind_site)

    db.commit()
    logger.info("Sites initialized: Solar Plant 1 & Wind Turbine Alpha.")


def load_solar_data(db: Session, force: bool = False):
    """Load and aggregate solar plant generation and weather sensors (15-min intervals)."""
    existing_count = db.query(SensorReading).filter(SensorReading.site_id == SOLAR_SITE_ID).count()
    if existing_count > 0 and not force:
        # Check if expected_power_kw is already populated
        sample_check = db.query(SensorReading.expected_power_kw).filter(SensorReading.site_id == SOLAR_SITE_ID).first()
        if sample_check and sample_check[0] is not None:
            logger.info(f"Solar readings already present with expected values ({existing_count} rows). Skipping load.")
            return

    # Clear existing if force or missing expected
    db.query(SensorReading).filter(SensorReading.site_id == SOLAR_SITE_ID).delete()
    db.query(WeatherReading).filter(WeatherReading.site_id == SOLAR_SITE_ID).delete()

    gen_file = RAW_DATA_DIR / "Plant_1_Generation_Data.csv"
    if not gen_file.exists():
        gen_file = BUNDLED_DATA_DIR / "solar_generation_sample.csv"

    weather_file = RAW_DATA_DIR / "Plant_1_Weather_Sensor_Data.csv"
    if not weather_file.exists():
        weather_file = BUNDLED_DATA_DIR / "solar_weather_sample.csv"

    logger.info(f"Loading solar data from: {gen_file.name} and {weather_file.name}")

    gen_agg: Dict[datetime, Dict[str, float]] = {}
    with open(gen_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_clean = {k.strip().upper(): v.strip() for k, v in row.items() if k}
            dt = parse_flexible_dt(row_clean.get("DATE_TIME", ""))
            if not dt:
                continue

            try:
                ac_kw = float(row_clean.get("AC_POWER", 0.0) or 0.0)
                dc_kw = float(row_clean.get("DC_POWER", 0.0) or 0.0)
            except ValueError:
                continue

            if dt not in gen_agg:
                gen_agg[dt] = {"ac_kw": 0.0, "dc_kw": 0.0}
            gen_agg[dt]["ac_kw"] += ac_kw
            gen_agg[dt]["dc_kw"] += dc_kw

    weather_agg: Dict[datetime, Dict[str, Any]] = {}
    with open(weather_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_clean = {k.strip().upper(): v.strip() for k, v in row.items() if k}
            dt = parse_flexible_dt(row_clean.get("DATE_TIME", ""))
            if not dt:
                continue

            try:
                irrad = float(row_clean.get("IRRADIATION", 0.0) or 0.0)
                mod_t = float(row_clean.get("MODULE_TEMPERATURE", 25.0) or 25.0)
                amb_t = float(row_clean.get("AMBIENT_TEMPERATURE", 25.0) or 25.0)
            except ValueError:
                continue

            if dt not in weather_agg:
                weather_agg[dt] = {"irrad_list": [], "mod_t_list": [], "amb_t_list": []}
            weather_agg[dt]["irrad_list"].append(irrad)
            weather_agg[dt]["mod_t_list"].append(mod_t)
            weather_agg[dt]["amb_t_list"].append(amb_t)

    all_dts = sorted(list(set(gen_agg.keys()).union(set(weather_agg.keys()))))
    if not all_dts:
        logger.warning("No solar data timestamps found.")
        return

    ac_powers: List[Optional[float]] = []
    dc_powers: List[Optional[float]] = []
    irradiations: List[Optional[float]] = []
    module_temps: List[Optional[float]] = []
    ambient_temps: List[Optional[float]] = []

    for dt in all_dts:
        if dt in gen_agg:
            ac_powers.append(min(3500.0, max(0.0, gen_agg[dt]["ac_kw"])))
            dc_powers.append(max(0.0, gen_agg[dt]["dc_kw"]))
        else:
            ac_powers.append(None)
            dc_powers.append(None)

        if dt in weather_agg:
            w = weather_agg[dt]
            irradiations.append(min(1.5, max(0.0, float(np.mean(w["irrad_list"])))))
            module_temps.append(float(np.mean(w["mod_t_list"])))
            ambient_temps.append(float(np.mean(w["amb_t_list"])))
        else:
            irradiations.append(None)
            module_temps.append(None)
            ambient_temps.append(None)

    # Gap interpolation (<= 3 intervals = 45 min)
    ac_powers = interpolate_short_gaps_1d(ac_powers, max_consecutive=3)
    irradiations = interpolate_short_gaps_1d(irradiations, max_consecutive=3)
    module_temps = interpolate_short_gaps_1d(module_temps, max_consecutive=3)
    ambient_temps = interpolate_short_gaps_1d(ambient_temps, max_consecutive=3)

    sensor_objects = []
    weather_objects = []
    current_day = None
    running_yield = 0.0

    for idx, dt in enumerate(all_dts):
        day_date = dt.date()
        if day_date != current_day:
            current_day = day_date
            running_yield = 0.0

        ac_val = ac_powers[idx] or 0.0
        dc_val = dc_powers[idx] or 0.0
        irrad_val = irradiations[idx] or 0.0
        mod_t_val = module_temps[idx]
        amb_t_val = ambient_temps[idx]

        hour = dt.hour + dt.minute / 60.0
        # Calculate expected power for every historical reading
        expected_kw = get_solar_expected_power_quick(irrad_val, mod_t_val, hour)

        running_yield += ac_val * 0.25

        sensor_objects.append(SensorReading(
            site_id=SOLAR_SITE_ID,
            timestamp=dt,
            ac_power_kw=round(ac_val, 2),
            daily_yield_kwh=round(running_yield, 2),
            expected_power_kw=expected_kw,
            is_anomaly=0,
            type_specific_data={"dc_power_kw": round(dc_val, 2)}
        ))

        weather_objects.append(WeatherReading(
            site_id=SOLAR_SITE_ID,
            timestamp=dt,
            irradiation=round(irrad_val, 4),
            module_temp=round(mod_t_val, 2) if mod_t_val is not None else None,
            ambient_temp=round(amb_t_val, 2) if amb_t_val is not None else None,
            wind_speed=None,
            wind_direction=None
        ))

    db.bulk_save_objects(sensor_objects)
    db.bulk_save_objects(weather_objects)
    db.commit()
    logger.info(f"Loaded {len(sensor_objects)} solar readings with expected benchmark successfully.")


def load_wind_data(db: Session, force: bool = False):
    """Load wind turbine SCADA data (10-min intervals) with expected power."""
    existing_count = db.query(SensorReading).filter(SensorReading.site_id == WIND_SITE_ID).count()
    if existing_count > 0 and not force:
        sample_check = db.query(SensorReading.expected_power_kw).filter(SensorReading.site_id == WIND_SITE_ID).first()
        if sample_check and sample_check[0] is not None:
            logger.info(f"Wind readings already present with expected values ({existing_count} rows). Skipping load.")
            return

    db.query(SensorReading).filter(SensorReading.site_id == WIND_SITE_ID).delete()
    db.query(WeatherReading).filter(WeatherReading.site_id == WIND_SITE_ID).delete()

    scada_file = RAW_DATA_DIR / "T1.csv"
    if not scada_file.exists():
        scada_file = BUNDLED_DATA_DIR / "wind_scada_sample.csv"

    logger.info(f"Loading wind data from: {scada_file.name}")

    rows = []
    with open(scada_file, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return

        time_idx, power_idx, ws_idx, theo_idx, wd_idx = 0, 1, 2, 3, 4
        for idx, col in enumerate(header):
            cl = col.strip().lower()
            if "date" in cl or "time" in cl:
                time_idx = idx
            elif "activepower" in cl or "active power" in cl:
                power_idx = idx
            elif "wind speed" in cl:
                ws_idx = idx
            elif "theoretical" in cl:
                theo_idx = idx
            elif "direction" in cl:
                wd_idx = idx

        for r in reader:
            if len(r) <= max(time_idx, power_idx, ws_idx):
                continue
            dt = parse_flexible_dt(r[time_idx])
            if not dt:
                continue

            try:
                ac_kw = min(2200.0, max(0.0, float(r[power_idx])))
            except (ValueError, IndexError):
                ac_kw = 0.0

            try:
                ws = min(40.0, max(0.0, float(r[ws_idx])))
            except (ValueError, IndexError):
                ws = 0.0

            try:
                theo = float(r[theo_idx]) if len(r) > theo_idx and r[theo_idx] != "" else None
            except ValueError:
                theo = None

            try:
                wd = float(r[wd_idx]) if len(r) > wd_idx and r[wd_idx] != "" else 0.0
            except ValueError:
                wd = 0.0

            rows.append((dt, ac_kw, ws, theo, wd))

    rows.sort(key=lambda x: x[0])

    sensor_objects = []
    weather_objects = []
    current_day = None
    running_yield = 0.0

    for dt, ac_kw, ws, theo, wd in rows:
        day_date = dt.date()
        if day_date != current_day:
            current_day = day_date
            running_yield = 0.0

        running_yield += ac_kw * (10.0 / 60.0)

        # Expected power from theoretical curve for every historical reading
        expected_kw = round(theo, 2) if theo is not None else get_wind_theoretical_power_quick(ws)

        sensor_objects.append(SensorReading(
            site_id=WIND_SITE_ID,
            timestamp=dt,
            ac_power_kw=round(ac_kw, 2),
            daily_yield_kwh=round(running_yield, 2),
            expected_power_kw=expected_kw,
            is_anomaly=0,
            type_specific_data={"theoretical_power_kw": expected_kw}
        ))

        weather_objects.append(WeatherReading(
            site_id=WIND_SITE_ID,
            timestamp=dt,
            irradiation=None,
            module_temp=None,
            ambient_temp=18.5,
            wind_speed=round(ws, 2),
            wind_direction=round(wd, 2)
        ))

    db.bulk_save_objects(sensor_objects)
    db.bulk_save_objects(weather_objects)
    db.commit()
    logger.info(f"Loaded {len(sensor_objects)} wind readings with expected benchmark successfully.")


def load_historical_data(force: bool = False):
    """Main data loader entry point."""
    db = SessionLocal()
    try:
        seed_sites(db)
        load_solar_data(db, force=force)
        load_wind_data(db, force=force)
    finally:
        db.close()

if __name__ == "__main__":
    load_historical_data(force=True)
