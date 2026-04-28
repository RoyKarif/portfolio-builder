"""Universe endpoint — returns the curated set of ETFs."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.data.asset_repo import get_curated_assets
from app.db import get_db
from app.schemas.portfolio import AssetResponse


router = APIRouter(prefix="/api/universe", tags=["universe"])


@router.get("", response_model=list[AssetResponse])
def list_universe(db: Session = Depends(get_db)) -> list[AssetResponse]:
    """Return the 20 curated ETFs the frontend should show as default options."""
    assets = get_curated_assets(db)
    return [AssetResponse.model_validate(a) for a in assets]
