"""Recommendations endpoint: type-aware operational and diagnostic actions."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Site, Recommendation
from app.api.schemas import RecommendationResponse
from app.services.recommendation_engine import format_relative_time

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("", response_model=List[RecommendationResponse])
def get_site_recommendations(
    site_id: str = Query(..., description="Target site identifier"),
    status: Optional[str] = Query("active", description="'active' | 'all' | 'resolved'"),
    db: Session = Depends(get_db)
):
    """Retrieve prioritized diagnostic recommendations for the requested site."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found.")

    query = db.query(Recommendation).filter(Recommendation.site_id == site_id)
    if status and status != "all":
        query = query.filter(Recommendation.status == status)

    recs = query.order_by(
        # Critical first, then Warning, then Info, followed by recency
        Recommendation.created_at.desc()
    ).all()

    # Priority sorting
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    sorted_recs = sorted(recs, key=lambda r: (severity_rank.get(r.severity, 3), -r.created_at.timestamp()))

    results = []
    for r in sorted_recs:
        results.append(RecommendationResponse(
            id=r.id,
            site_id=r.site_id,
            created_at=r.created_at.isoformat(),
            relative_time=format_relative_time(r.created_at),
            severity=r.severity,
            issue_type=r.issue_type,
            reason=r.reason,
            action=r.action,
            status=r.status
        ))

    return results
