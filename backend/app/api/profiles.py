from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.profile import InvestmentProfile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileResponse

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _to_response(profile: InvestmentProfile) -> ProfileResponse:
    return ProfileResponse(
        id=str(profile.id),
        risk_level=profile.risk_level,
        investment_horizon=profile.investment_horizon,
        available_amount=float(profile.available_amount),
        target_return=float(profile.target_return),
        preferred_sectors=profile.preferred_sectors,
        include_tickers=profile.include_tickers,
        exclude_tickers=profile.exclude_tickers,
    )


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    req: ProfileCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = InvestmentProfile(user_id=user.id, **req.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_response(profile)


@router.get("", response_model=list[ProfileResponse])
def list_profiles(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profiles = db.query(InvestmentProfile).filter(InvestmentProfile.user_id == user.id).all()
    return [_to_response(p) for p in profiles]


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(InvestmentProfile).filter(
        InvestmentProfile.id == profile_id,
        InvestmentProfile.user_id == user.id,
    ).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return _to_response(profile)
