from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.engine.pipeline import generate_portfolio
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.profile import InvestmentProfile
from app.models.user import User
from app.schemas.portfolio import PortfolioResponse, PortfolioListItem, HoldingResponse, SimulationResponse

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.post("/generate/{profile_id}", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
def generate(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(InvestmentProfile).filter(
        InvestmentProfile.id == profile_id,
        InvestmentProfile.user_id == user.id,
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    result = generate_portfolio(
        country=user.country,
        risk_level=profile.risk_level,
        investment_horizon=profile.investment_horizon,
        available_amount=float(profile.available_amount),
        target_return=float(profile.target_return) / 100,
        preferred_sectors=profile.preferred_sectors,
        include_tickers=profile.include_tickers,
        exclude_tickers=profile.exclude_tickers,
        db=db,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    sim = result["simulation"]
    portfolio = Portfolio(
        user_id=user.id,
        profile_id=profile.id,
        status="active",
        risk_score=result["risk_score"],
        expected_return_low=result["expected_return_low"],
        expected_return_high=result["expected_return_high"],
        portfolio_return=result["portfolio_return"],
        total_value=float(profile.available_amount),
        percentile_10=sim["percentile_10"],
        percentile_50=sim["percentile_50"],
        percentile_90=sim["percentile_90"],
        horizon_years=sim["horizon_years"],
        n_simulations=sim["n_simulations"],
    )
    db.add(portfolio)
    db.flush()

    for h in result["holdings"]:
        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            ticker=h["ticker"],
            company_name=h["company_name"],
            sector=h["sector"],
            allocation_pct=h["allocation_pct"],
            expected_return=h["expected_return"],
        )
        db.add(holding)

    db.commit()
    db.refresh(portfolio)

    return PortfolioResponse(
        id=str(portfolio.id),
        status=portfolio.status,
        risk_score=float(portfolio.risk_score),
        expected_return_low=float(portfolio.expected_return_low),
        expected_return_high=float(portfolio.expected_return_high),
        portfolio_return=result["portfolio_return"],
        total_value=float(portfolio.total_value),
        holdings=[HoldingResponse(**h) for h in result["holdings"]],
        simulation=SimulationResponse(**result["simulation"]),
    )


@router.get("", response_model=list[PortfolioListItem])
def list_portfolios(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolios = db.query(Portfolio).filter(Portfolio.user_id == user.id).all()
    return [
        PortfolioListItem(
            id=str(p.id),
            status=p.status,
            risk_score=float(p.risk_score),
            expected_return_low=float(p.expected_return_low),
            expected_return_high=float(p.expected_return_high),
            total_value=float(p.total_value),
            created_at=p.created_at.isoformat(),
        )
        for p in portfolios
    ]


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user.id,
    ).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = db.query(PortfolioHolding).filter(PortfolioHolding.portfolio_id == portfolio.id).all()

    return PortfolioResponse(
        id=str(portfolio.id),
        status=portfolio.status,
        risk_score=float(portfolio.risk_score),
        expected_return_low=float(portfolio.expected_return_low),
        expected_return_high=float(portfolio.expected_return_high),
        portfolio_return=float(portfolio.portfolio_return) if portfolio.portfolio_return is not None else 0.0,
        total_value=float(portfolio.total_value),
        holdings=[
            HoldingResponse(
                ticker=h.ticker, company_name=h.company_name, sector=h.sector,
                allocation_pct=float(h.allocation_pct), expected_return=float(h.expected_return),
            ) for h in holdings
        ],
        simulation=SimulationResponse(
            percentile_10=float(portfolio.percentile_10) if portfolio.percentile_10 is not None else 0.0,
            percentile_50=float(portfolio.percentile_50) if portfolio.percentile_50 is not None else 0.0,
            percentile_90=float(portfolio.percentile_90) if portfolio.percentile_90 is not None else 0.0,
            return_low=float(portfolio.expected_return_low) / 100,
            return_high=float(portfolio.expected_return_high) / 100,
            initial_value=float(portfolio.total_value),
            horizon_years=float(portfolio.horizon_years) if portfolio.horizon_years is not None else 0.0,
            n_simulations=int(portfolio.n_simulations) if portfolio.n_simulations is not None else 0,
        ),
    )


@router.patch("/{portfolio_id}/archive")
def archive_portfolio(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user.id,
    ).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    portfolio.status = "archived"
    db.commit()
    return {"id": str(portfolio.id), "status": "archived"}


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user.id,
    ).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    db.delete(portfolio)
    db.commit()
    return None
