"""Sites endpoint: multi-site list."""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Site
from app.api.schemas import SiteSchema

router = APIRouter(prefix="/sites", tags=["Sites"])

@router.get("", response_model=List[SiteSchema])
def get_sites(db: Session = Depends(get_db)):
    """Return all configured renewable energy sites."""
    sites = db.query(Site).order_by(Site.type.asc(), Site.name.asc()).all()
    return sites
