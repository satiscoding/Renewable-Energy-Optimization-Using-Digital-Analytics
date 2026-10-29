"""SQLAlchemy ORM models strictly parameterized by site_id."""
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Index
)
from sqlalchemy.orm import relationship
from app.db.session import Base

class Site(Base):
    """Renewable energy generation site (multi-site by design)."""
    __tablename__ = "sites"

    id = Column(String(64), primary_key=True, index=True) # e.g. "solar-plant-1", "wind-alpha"
    name = Column(String(128), nullable=False)            # e.g. "Solar Plant 1", "Wind Turbine Alpha"
    type = Column(String(16), nullable=False, index=True) # "solar" | "wind"
    capacity_kw = Column(Float, nullable=False)           # Plant capacity in kW
    aggregation_level = Column(String(32), nullable=False)# "plant_total" for solar, "turbine" for wind
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sensor_readings = relationship("SensorReading", back_populates="site", cascade="all, delete-orphan")
    weather_readings = relationship("WeatherReading", back_populates="site", cascade="all, delete-orphan")
    forecasts = relationship("Forecast", back_populates="site", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="site", cascade="all, delete-orphan")


class SensorReading(Base):
    """Telemetry readings for a site at a given timestamp."""
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(64), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    ac_power_kw = Column(Float, nullable=False)             # Actual output in kW
    daily_yield_kwh = Column(Float, nullable=True)          # Cumulative or computed energy yield for the day in kWh
    expected_power_kw = Column(Float, nullable=True)        # Model-predicted or theoretical expected kW
    is_anomaly = Column(Integer, default=0, nullable=False) # 1 if flagged as persistent shortfall anomaly
    type_specific_data = Column(JSON, nullable=True)        # Inverter metrics for solar or rotor/pitch for wind

    site = relationship("Site", back_populates="sensor_readings")

    __table_args__ = (
        Index("ix_sensor_site_timestamp", "site_id", "timestamp"),
    )


class WeatherReading(Base):
    """Weather and ambient conditions at a site at a given timestamp."""
    __tablename__ = "weather"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(64), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    irradiation = Column(Float, nullable=True)              # W/m² or kW/m² (solar)
    module_temp = Column(Float, nullable=True)              # °C (solar PV cell temperature)
    ambient_temp = Column(Float, nullable=True)             # °C
    wind_speed = Column(Float, nullable=True)               # m/s (anemometer)
    wind_direction = Column(Float, nullable=True)           # Degrees (0-360)

    site = relationship("Site", back_populates="weather_readings")

    __table_args__ = (
        Index("ix_weather_site_timestamp", "site_id", "timestamp"),
    )


class Forecast(Base):
    """Future output forecasts (2-6 hours ahead)."""
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(64), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True) # Target prediction time (UTC)
    predicted_kw = Column(Float, nullable=False)             # Predicted generation in kW
    confidence_low_kw = Column(Float, nullable=True)        # Lower confidence bound (kW)
    confidence_high_kw = Column(Float, nullable=True)       # Upper confidence bound (kW)
    model = Column(String(64), nullable=False)               # Model name e.g. "XGBoost", "GradientBoosting"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    site = relationship("Site", back_populates="forecasts")

    __table_args__ = (
        Index("ix_forecast_site_timestamp", "site_id", "timestamp"),
    )


class Recommendation(Base):
    """Type-aware operational and diagnostic recommendations."""
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(64), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    severity = Column(String(16), nullable=False)            # "info" | "warning" | "critical"
    issue_type = Column(String(32), nullable=False)          # "soiling", "shading", "sudden_drop", "wind_shortfall", "low_wind", "shift_load"
    reason = Column(Text, nullable=False)                    # Plain language root cause explanation
    action = Column(Text, nullable=False)                    # Concrete recommended operational action
    status = Column(String(16), default="active", nullable=False) # "active" | "resolved"

    site = relationship("Site", back_populates="recommendations")

    __table_args__ = (
        Index("ix_rec_site_status", "site_id", "status"),
    )
