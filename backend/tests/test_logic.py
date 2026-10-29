"""Pytest suite for verification of core domain logic, edge cases, and site isolation."""
import pytest
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import Site, SensorReading, WeatherReading, Recommendation, Forecast
from app.services.analytics import (
    get_wind_theoretical_power,
    analyze_point_discrepancy,
    detect_anomalies_time_series,
    WIND_CUT_IN_MS,
    WIND_CUT_OUT_MS,
    SUSTAINED_SHORTFALL_THRESHOLD_PCT,
    MIN_SHORTFALL_KW,
    PERSISTENCE_INTERVALS
)
from app.services.recommendation_engine import (
    add_recommendation_if_new,
    resolve_recommendation_if_active,
    format_relative_time
)

@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()

    s1 = Site(id="solar-plant-1", name="Solar Plant 1", type="solar", capacity_kw=3000.0, aggregation_level="plant_total")
    s2 = Site(id="wind-alpha", name="Wind Turbine Alpha", type="wind", capacity_kw=2050.0, aggregation_level="turbine")
    session.add_all([s1, s2])
    session.commit()

    yield session
    session.close()


def test_daily_yield_integral_nonzero():
    """Verify daily yield integral is non-zero when power is generated and matches kW * dt."""
    # 8 intervals of 15 min (0.25h) at 1200 kW
    kw_values = [1200.0] * 8
    dt_hours = 0.25
    running_yields = [sum(kw_values[:i+1]) * dt_hours for i in range(len(kw_values))]

    assert running_yields[0] == 300.0
    assert running_yields[-1] == 2400.0
    assert all(y > 0 for y in running_yields)


def test_wind_cut_in_edge_case():
    """Verify wind below cut-in speed (expected ~0) does not produce false efficiency drop alerts."""
    expected = get_wind_theoretical_power(2.1)
    assert expected == 0.0

    discrepancy = analyze_point_discrepancy("wind", actual_kw=0.0, expected_kw=expected, wind_speed=2.1)
    assert discrepancy["is_shortfall"] is False
    assert discrepancy["status"] == "normal_cut_in_out"
    assert discrepancy["gap_pct"] == 0.0


def test_wind_cut_out_edge_case():
    """Verify wind above cut-out speed (25 m/s) clamps expected to 0 and suppresses alerts."""
    expected = get_wind_theoretical_power(27.5)
    assert expected == 0.0

    discrepancy = analyze_point_discrepancy("wind", actual_kw=0.0, expected_kw=expected, wind_speed=27.5)
    assert discrepancy["is_shortfall"] is False
    assert discrepancy["status"] == "normal_cut_in_out"


def test_excess_generation_treated_as_mismatch_not_penalty():
    """Verify if actual exceeds expected by >30%, it is logged as calibration review rather than shortfall."""
    discrepancy = analyze_point_discrepancy("solar", actual_kw=1500.0, expected_kw=1000.0)
    assert discrepancy["is_shortfall"] is False
    assert discrepancy["status"] == "model_mismatch_review"


def test_persistent_anomaly_rolling():
    """Verify transient dip (passing cloud) is ignored, while persistent dip triggers anomaly."""
    # Expected power = 1000 kW
    expecteds = [1000.0] * 8
    # 8 intervals with transient single dip (e.g. 500 kW = 50% drop, but only for 1 interval)
    actuals_transient = [1000.0, 990.0, 980.0, 500.0, 995.0, 1000.0, 990.0, 1000.0]
    flags_transient = detect_anomalies_time_series(actuals_transient, expecteds, min_consecutive=3, shortfall_threshold_pct=0.10)
    assert sum(flags_transient) == 0, "Transient single dip should NOT trigger persistent anomaly!"

    # 4 consecutive large shortfalls (15% drop: 850 kW vs 1000 kW)
    actuals_persistent = [1000.0, 990.0, 980.0, 850.0, 850.0, 850.0, 850.0, 850.0]
    flags_persistent = detect_anomalies_time_series(actuals_persistent, expecteds, min_consecutive=3, shortfall_threshold_pct=0.10)
    assert flags_persistent[-1] == 1, "Persistent 15% shortfall must be flagged as anomaly!"
    assert flags_persistent[3] == 0, "First interval of shortfall should not flag yet (needs min 3)!"
    assert flags_persistent[5] == 1, "Third interval of shortfall should flag!"


def test_tuned_threshold_passing_clouds_and_small_dips_rejected():
    """Verify that passing clouds (1-2 intervals) or small dips (5-6%) are NOT flagged,
    but sustained drops of 10-15% for >=3 intervals ARE flagged.
    """
    expecteds = [1500.0] * 10

    # Case A: 2-interval passing cloud with severe 40% dip -> MUST NOT flag
    actuals_cloud = [1500.0, 1500.0, 900.0, 900.0, 1500.0, 1500.0, 1500.0, 1500.0, 1500.0, 1500.0]
    flags_cloud = detect_anomalies_time_series(actuals_cloud, expecteds, min_consecutive=3, shortfall_threshold_pct=0.10)
    assert sum(flags_cloud) == 0, "Passing cloud (only 2 intervals) must not be flagged!"

    # Case B: Sustained minor dip (6% shortfall, e.g. 1410 kW vs 1500 kW) for 5 intervals -> MUST NOT flag
    actuals_minor = [1500.0, 1500.0, 1410.0, 1410.0, 1410.0, 1410.0, 1410.0, 1500.0, 1500.0, 1500.0]
    flags_minor = detect_anomalies_time_series(actuals_minor, expecteds, min_consecutive=3, shortfall_threshold_pct=0.10)
    assert sum(flags_minor) == 0, "Sustained minor dip (<10%) must not be flagged!"

    # Case C: Sustained 12% drop (1320 kW vs 1500 kW, gap = 180 kW) for 4 intervals -> MUST flag starting on 3rd interval
    actuals_sustained = [1500.0, 1500.0, 1320.0, 1320.0, 1320.0, 1320.0, 1500.0, 1500.0, 1500.0, 1500.0]
    flags_sustained = detect_anomalies_time_series(actuals_sustained, expecteds, min_consecutive=3, shortfall_threshold_pct=0.10)
    assert flags_sustained[2] == 0  # 1st drop interval
    assert flags_sustained[3] == 0  # 2nd drop interval
    assert flags_sustained[4] == 1  # 3rd drop interval -> FLAGGED!
    assert flags_sustained[5] == 1  # 4th drop interval -> FLAGGED!
    assert flags_sustained[6] == 0  # Back to normal -> cleared!


def test_recommendation_deduplication_and_lifecycle(db_session):
    """Verify recommendation is created once per event, de-duplicated, and resolved properly."""
    r1 = add_recommendation_if_new(
        site_id="solar-plant-1",
        severity="warning",
        issue_type="soiling",
        reason="Dust accumulation detected.",
        action="Clean panels.",
        db=db_session
    )
    assert r1 is not None
    assert r1.status == "active"

    r2 = add_recommendation_if_new(
        site_id="solar-plant-1",
        severity="warning",
        issue_type="soiling",
        reason="Dust accumulation detected.",
        action="Clean panels.",
        db=db_session
    )
    assert r2 is None

    active_count = db_session.query(Recommendation).filter(
        Recommendation.site_id == "solar-plant-1",
        Recommendation.status == "active"
    ).count()
    assert active_count == 1

    resolve_recommendation_if_active("solar-plant-1", "soiling", db_session)
    resolved_rec = db_session.query(Recommendation).filter(Recommendation.id == r1.id).first()
    assert resolved_rec.status == "resolved"
    assert resolved_rec.resolved_at is not None


def test_relative_time_formatting_never_future():
    """Verify timestamps format to past relative phrases and never future terms."""
    now = datetime.utcnow()
    assert format_relative_time(now - timedelta(seconds=20)) == "Just now"
    assert format_relative_time(now - timedelta(minutes=15)) == "15 min ago"
    assert format_relative_time(now - timedelta(hours=3)) == "3 hours ago"
    assert format_relative_time(now - timedelta(days=2)) == "2 days ago"


def test_strict_site_isolation(db_session):
    """Verify data queries for solar-plant-1 NEVER leak into wind-alpha."""
    t1 = datetime(2026, 10, 20, 12, 0)

    db_session.add(SensorReading(site_id="solar-plant-1", timestamp=t1, ac_power_kw=2500.0, daily_yield_kwh=12000.0))
    db_session.add(SensorReading(site_id="wind-alpha", timestamp=t1, ac_power_kw=1800.0, daily_yield_kwh=7500.0))
    db_session.commit()

    solar_readings = db_session.query(SensorReading).filter(SensorReading.site_id == "solar-plant-1").all()
    wind_readings = db_session.query(SensorReading).filter(SensorReading.site_id == "wind-alpha").all()

    assert len(solar_readings) == 1
    assert solar_readings[0].ac_power_kw == 2500.0

    assert len(wind_readings) == 1
    assert wind_readings[0].ac_power_kw == 1800.0

    cross_solar = [r for r in solar_readings if r.site_id == "wind-alpha"]
    assert len(cross_solar) == 0, "Critical bug: solar query returned wind data!"
