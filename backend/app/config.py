"""Configuration settings for Solar & Wind Control Room backend."""
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BUNDLED_DATA_DIR = DATA_DIR / "bundled"
RAW_DATA_DIR = DATA_DIR / "raw"
DB_PATH = BASE_DIR / "control_room.db"

class Settings(BaseModel):
    PROJECT_NAME: str = "Solar & Wind Control Room"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"
    DATABASE_URL: str = f"sqlite:///{DB_PATH.as_posix()}"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    DATA_MODE: str = "live_weather" # "live_weather" (default) | "simulated"
    # Simulation settings
    SIMULATION_INTERVAL_SECONDS: int = 5
    # Forecast horizon
    DEFAULT_FORECAST_HORIZON_HOURS: int = 6
    # Anomaly rolling window intervals
    ANOMALY_ROLLING_WINDOW: int = 8
    ANOMALY_Z_THRESHOLD: float = 2.0

settings = Settings()
