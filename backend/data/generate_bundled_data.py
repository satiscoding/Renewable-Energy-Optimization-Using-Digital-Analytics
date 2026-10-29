"""Generate realistic bundled datasets matching exact Kaggle schemas for offline readiness."""
import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "bundled"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def generate_solar_data(days: int = 14):
    """Generate 15-min solar generation and weather data matching Kaggle Indian Solar PV dataset."""
    start_time = datetime(2026, 10, 15, 0, 0, 0)
    total_steps = days * 24 * 4 # 15-min steps

    gen_file = DATA_DIR / "solar_generation_sample.csv"
    weather_file = DATA_DIR / "solar_weather_sample.csv"

    inverters = [f"INV_{i:02d}" for i in range(1, 23)] # 22 inverters (~130 kW each = ~2860 kW plant)

    weather_rows = []
    gen_rows = []

    # State tracking
    total_yield_map = {inv: 500000.0 for inv in inverters}

    for step in range(total_steps):
        current_time = start_time + timedelta(minutes=15 * step)
        time_str = current_time.strftime("%d-%m-%Y %H:%M")
        hour = current_time.hour + current_time.minute / 60.0
        day_step = (current_time.hour * 4) + (current_time.minute // 15)

        # Solar zenith simulation (sun between 06:00 and 18:30)
        if 6.0 <= hour <= 18.5:
            # Solar peak at 12:15
            sun_angle = math.sin((hour - 6.0) / 12.5 * math.pi)
            base_irrad = max(0.0, sun_angle * 0.95 + random.uniform(-0.04, 0.04)) # kW/m²
            # Some cloud dips on day 4 and day 9
            if current_time.day in [19, 24] and 10.0 <= hour <= 14.0:
                base_irrad *= 0.65
            irrad = round(max(0.0, base_irrad), 4)
            amb_temp = round(22.0 + sun_angle * 12.0 + random.uniform(-1.0, 1.0), 2)
            mod_temp = round(amb_temp + irrad * 28.0 + random.uniform(-1.5, 1.5), 2)
        else:
            irrad = 0.0
            amb_temp = round(20.0 + random.uniform(-1.0, 1.0), 2)
            mod_temp = round(amb_temp + random.uniform(-0.5, 0.5), 2)

        weather_rows.append([
            time_str,
            "PLANT_1",
            amb_temp,
            mod_temp,
            irrad
        ])

        # Generation per inverter
        for inv_idx, inv in enumerate(inverters):
            # Reset daily yield at midnight
            if day_step == 0:
                daily_yield = 0.0
            else:
                daily_yield = None # will be cumulative

            if irrad > 0.01:
                # Slight efficiency difference per inverter
                inv_factor = 0.96 + (inv_idx % 5) * 0.015
                dc_kw = irrad * 135.0 * inv_factor * (1.0 - (mod_temp - 25.0) * 0.004)
                dc_kw = max(0.0, dc_kw + random.uniform(-1.5, 1.5))
                ac_kw = dc_kw * 0.975 # Inverter efficiency
            else:
                dc_kw = 0.0
                ac_kw = 0.0

            # Step kWh = ac_kw * 0.25h
            step_kwh = ac_kw * 0.25
            total_yield_map[inv] += step_kwh
            # Approx daily cumulative
            inv_daily_yield = (step_kwh * 4) # simplified indicator

            gen_rows.append([
                time_str,
                "PLANT_1",
                inv,
                round(dc_kw, 2),
                round(ac_kw, 2),
                round(inv_daily_yield, 2),
                round(total_yield_map[inv], 2)
            ])

    # Write weather CSV
    with open(weather_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["DATE_TIME", "PLANT_ID", "AMBIENT_TEMPERATURE", "MODULE_TEMPERATURE", "IRRADIATION"])
        writer.writerows(weather_rows)

    # Write gen CSV
    with open(gen_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["DATE_TIME", "PLANT_ID", "SOURCE_KEY", "DC_POWER", "AC_POWER", "DAILY_YIELD", "TOTAL_YIELD"])
        writer.writerows(gen_rows)

    print(f"Generated solar data: {len(weather_rows)} weather steps, {len(gen_rows)} inverter rows.")


def theoretical_power(ws: float) -> float:
    """Theoretical power curve for 2050 kW wind turbine (Kaggle SCADA T1)."""
    if ws < 3.0 or ws > 25.0:
        return 0.0
    elif ws >= 13.0:
        return 2050.0
    else:
        # Sigmoidal power curve between 3 m/s and 13 m/s
        ratio = (ws - 3.0) / (13.0 - 3.0)
        return round(2050.0 * (ratio ** 2.4), 2)


def generate_wind_data(days: int = 14):
    """Generate 10-min SCADA wind data matching Kaggle T1.csv format."""
    start_time = datetime(2026, 10, 15, 0, 0, 0)
    total_steps = days * 24 * 6 # 10-min steps
    scada_file = DATA_DIR / "wind_scada_sample.csv"

    rows = []
    current_ws = 7.5
    current_wd = 180.0

    for step in range(total_steps):
        current_time = start_time + timedelta(minutes=10 * step)
        time_str = current_time.strftime("%d %m %Y %H:%M")

        # Wind speed random walk with diurnal component
        hour = current_time.hour
        diurnal = math.sin((hour - 2) / 24.0 * 2 * math.pi) * 1.5
        current_ws = 0.85 * current_ws + 0.15 * (7.0 + diurnal + random.uniform(-3.5, 3.5))
        current_ws = max(0.5, min(23.5, current_ws))

        # Wind direction random walk
        current_wd = (current_wd + random.uniform(-8.0, 8.0)) % 360.0

        theo_kw = theoretical_power(current_ws)

        # Actual power fluctuates slightly around theoretical
        if theo_kw > 0.0:
            actual_kw = theo_kw * random.uniform(0.94, 1.03)
            actual_kw = max(0.0, min(2050.0, actual_kw))
        else:
            actual_kw = 0.0

        rows.append([
            time_str,
            round(actual_kw, 2),
            round(current_ws, 2),
            round(theo_kw, 2),
            round(current_wd, 2)
        ])

    with open(scada_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date/Time", "LV ActivePower (kW)", "Wind Speed (m/s)", "Theoretical_Power_Curve (KWh)", "Wind Direction (°)"])
        writer.writerows(rows)

    print(f"Generated wind SCADA data: {len(rows)} steps.")

if __name__ == "__main__":
    generate_solar_data()
    generate_wind_data()
