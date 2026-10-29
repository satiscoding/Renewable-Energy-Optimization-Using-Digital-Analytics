"""FastAPI main application entry point for Solar & Wind Control Room."""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.data_loader import load_historical_data
from app.services.forecaster import update_all_forecasts
from app.services.recommendation_engine import run_recommendation_pipeline
from app.services.simulator import simulation_loop
from app.api import (
    routes_sites,
    routes_status,
    routes_history,
    routes_forecasts,
    routes_recommendations,
    routes_simulator
)

logger = logging.getLogger("control_room.main")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info("Initializing Solar & Wind Control Room Backend...")
    # 1. Bootstrap database tables
    init_db()

    # 2. Check and load historical data if database is empty
    logger.info("Loading initial historical datasets...")
    load_historical_data()

    # 3. Generate initial multi-hour forecasts and baseline recommendations
    db = SessionLocal()
    try:
        logger.info("Generating baseline forecasts...")
        update_all_forecasts(db)
        logger.info("Running baseline recommendation pipelines...")
        run_recommendation_pipeline("solar-plant-1", db)
        run_recommendation_pipeline("wind-alpha", db)
    finally:
        db.close()

    # 4. Start background live simulation task ONLY if DATA_MODE == "simulated"
    sim_task = None
    if settings.DATA_MODE == "simulated":
        sim_task = asyncio.create_task(simulation_loop(interval_seconds=settings.SIMULATION_INTERVAL_SECONDS))
        logger.info("Live feed simulator background worker active (DATA_MODE=simulated).")
    else:
        logger.info(f"Live feed simulator background worker disabled (DATA_MODE={settings.DATA_MODE}).")

    yield

    # Shutdown
    if sim_task:
        sim_task.cancel()
    logger.info("Control Room Backend shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Digital Analytics Control Room for Multi-Site Solar & Wind Plants (Phase-II B.Tech Capstone).",
    lifespan=lifespan
)

# CORS setup for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"], # allow local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers under /api
app.include_router(routes_sites.router, prefix=settings.API_V1_STR)
app.include_router(routes_status.router, prefix=settings.API_V1_STR)
app.include_router(routes_history.router, prefix=settings.API_V1_STR)
app.include_router(routes_forecasts.router, prefix=settings.API_V1_STR)
app.include_router(routes_recommendations.router, prefix=settings.API_V1_STR)
app.include_router(routes_simulator.router, prefix=settings.API_V1_STR)

@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
