import urllib.request
import json
import time

BASE = "http://127.0.0.1:8000/api"

def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def post_json(url: str, data: dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def test_anomaly_flow():
    # 1. Reset to normal
    print("--- 1. RESET TO NOMINAL ---")
    post_json(f"{BASE}/simulator/anomaly", {"site_id": "solar-plant-1", "anomaly_mode": "normal"})
    post_json(f"{BASE}/simulator/anomaly", {"site_id": "wind-alpha", "anomaly_mode": "normal"})

    s_solar = get_json(f"{BASE}/status?site_id=solar-plant-1")
    s_wind = get_json(f"{BASE}/status?site_id=wind-alpha")
    print(f"Initial Solar health: '{s_solar.get('health')}', Wind health: '{s_wind.get('health')}'")

    # 2. Test Solar Soiling
    print("\n--- 2. TESTING SOLAR SOILING ---")
    r1 = post_json(f"{BASE}/simulator/anomaly", {"site_id": "solar-plant-1", "anomaly_mode": "soiling"})
    print("Inject response:", r1)
    status_solar = get_json(f"{BASE}/status?site_id=solar-plant-1")
    print(f"Solar status badge: '{status_solar.get('health')}' (expected: 'anomaly_detected')")
    print(f"Solar actual vs expected: {status_solar.get('actual_kw')} kW vs {status_solar.get('expected_kw')} kW")
    recs_solar = get_json(f"{BASE}/recommendations?site_id=solar-plant-1")
    soiling_recs = [r for r in recs_solar if r.get("issue_type") == "soiling" and r.get("status") == "active"]
    print(f"Active soiling recommendations count: {len(soiling_recs)}")
    for rec in soiling_recs:
        print(f"  [ID {rec.get('id')}] [{rec.get('severity').upper()}] {rec.get('reason')} -> Action: {rec.get('action')} | Time: {rec.get('relative_time')}")
    assert status_solar.get("health") == "anomaly_detected", "Solar status should be anomaly_detected!"
    assert len(soiling_recs) == 1, "Expected 1 active soiling recommendation!"

    # Check deduplication: inject soiling again
    post_json(f"{BASE}/simulator/anomaly", {"site_id": "solar-plant-1", "anomaly_mode": "soiling"})
    recs_solar_after = get_json(f"{BASE}/recommendations?site_id=solar-plant-1")
    soiling_recs_after = [r for r in recs_solar_after if r.get("issue_type") == "soiling" and r.get("status") == "active"]
    print(f"Active soiling recommendations after duplicate trigger (must remain 1): {len(soiling_recs_after)}")
    assert len(soiling_recs_after) == 1, "Duplicate recommendation was created!"

    # 3. Test Wind Shortfall
    print("\n--- 3. TESTING WIND SHORTFALL ---")
    r2 = post_json(f"{BASE}/simulator/anomaly", {"site_id": "wind-alpha", "anomaly_mode": "wind_shortfall"})
    print("Inject response:", r2)
    status_wind = get_json(f"{BASE}/status?site_id=wind-alpha")
    print(f"Wind status badge: '{status_wind.get('health')}' (expected: 'anomaly_detected')")
    print(f"Wind actual vs expected: {status_wind.get('actual_kw')} kW vs {status_wind.get('expected_kw')} kW")
    recs_wind = get_json(f"{BASE}/recommendations?site_id=wind-alpha")
    wind_recs = [r for r in recs_wind if r.get("issue_type") == "wind_shortfall" and r.get("status") == "active"]
    print(f"Active wind shortfall recommendations count: {len(wind_recs)}")
    for rec in wind_recs:
        print(f"  [ID {rec.get('id')}] [{rec.get('severity').upper()}] {rec.get('reason')} -> Action: {rec.get('action')} | Time: {rec.get('relative_time')}")
    assert status_wind.get("health") == "anomaly_detected", "Wind status should be anomaly_detected!"
    assert len(wind_recs) == 1, "Expected 1 active wind shortfall recommendation!"

    # Check wind deduplication
    post_json(f"{BASE}/simulator/anomaly", {"site_id": "wind-alpha", "anomaly_mode": "wind_shortfall"})
    recs_wind_after = get_json(f"{BASE}/recommendations?site_id=wind-alpha")
    wind_recs_after = [r for r in recs_wind_after if r.get("issue_type") == "wind_shortfall" and r.get("status") == "active"]
    print(f"Active wind shortfall recommendations after duplicate trigger (must remain 1): {len(wind_recs_after)}")
    assert len(wind_recs_after) == 1, "Duplicate wind recommendation was created!"

    # 4. Test Sudden Drop
    print("\n--- 4. TESTING SUDDEN DROP (CRITICAL) ---")
    r3 = post_json(f"{BASE}/simulator/anomaly", {"site_id": "solar-plant-1", "anomaly_mode": "sudden_drop"})
    print("Inject response:", r3)
    status_drop = get_json(f"{BASE}/status?site_id=solar-plant-1")
    print(f"Solar status badge: '{status_drop.get('health')}' (expected: 'anomaly_detected')")
    recs_drop = get_json(f"{BASE}/recommendations?site_id=solar-plant-1")
    drop_recs = [r for r in recs_drop if r.get("issue_type") == "sudden_drop" and r.get("status") == "active"]
    print(f"Active sudden drop recommendations count: {len(drop_recs)}")
    for rec in drop_recs:
        print(f"  [ID {rec.get('id')}] [{rec.get('severity').upper()}] {rec.get('reason')} -> Action: {rec.get('action')} | Time: {rec.get('relative_time')}")
    assert status_drop.get("health") == "anomaly_detected", "Solar status should be anomaly_detected!"
    assert len(drop_recs) == 1, "Expected 1 active sudden drop recommendation!"
    assert drop_recs[0].get("severity") == "critical", "Expected critical severity for sudden drop!"

    # 5. Test Resolution back to Nominal
    print("\n--- 5. TESTING RESOLUTION BACK TO NOMINAL ---")
    post_json(f"{BASE}/simulator/anomaly", {"site_id": "solar-plant-1", "anomaly_mode": "normal"})
    post_json(f"{BASE}/simulator/anomaly", {"site_id": "wind-alpha", "anomaly_mode": "normal"})
    status_solar_res = get_json(f"{BASE}/status?site_id=solar-plant-1")
    status_wind_res = get_json(f"{BASE}/status?site_id=wind-alpha")
    print(f"Solar status badge after normal: '{status_solar_res.get('health')}' (expected: 'healthy')")
    print(f"Wind status badge after normal: '{status_wind_res.get('health')}' (expected: 'healthy')")

    recs_solar_res = get_json(f"{BASE}/recommendations?site_id=solar-plant-1")
    recs_wind_res = get_json(f"{BASE}/recommendations?site_id=wind-alpha")
    active_anomaly_solar = [r for r in recs_solar_res if r.get("status") == "active" and r.get("severity") in ["critical", "warning"]]
    active_anomaly_wind = [r for r in recs_wind_res if r.get("status") == "active" and r.get("severity") in ["critical", "warning"]]

    print(f"Solar active critical/warning anomalies remaining (must be 0): {len(active_anomaly_solar)}")
    print(f"Wind active critical/warning anomalies remaining (must be 0): {len(active_anomaly_wind)}")
    assert len(active_anomaly_solar) == 0, "Solar anomaly recommendations not resolved!"
    assert len(active_anomaly_wind) == 0, "Wind anomaly recommendations not resolved!"
    assert status_solar_res.get("health") == "healthy", "Solar status should be healthy!"
    assert status_wind_res.get("health") == "healthy", "Wind status should be healthy!"

    print("\n>>> ALL DEMO INJECT ANOMALY LIFECYCLE TESTS PASSED PERFECTLY! <<<")

if __name__ == "__main__":
    test_anomaly_flow()
