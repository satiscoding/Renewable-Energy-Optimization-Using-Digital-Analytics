"""Database schema initialization."""
import logging
from app.db.session import engine, Base
from app.db import models # ensure models are registered with Base

logger = logging.getLogger("control_room.init_db")

def init_db():
    """Create all tables defined in models."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")

if __name__ == "__main__":
    init_db()
