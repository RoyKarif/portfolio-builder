"""Portfolio endpoints: build / list / get / delete."""

import secrets
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.data import portfolio_repo, price_repo
from app.data.price_fetcher import ensure_prices_fresh
from app.db import get_db
from app.engine import (
    daily_log_returns,
    mean_returns,
    covariance_matrix,
    solve_mvo,
    simulate_portfolio,
    summarize,
    RISK_LEVEL_TO_VOLATILITY,
)
from app.engine.monte_carlo import histogram_bins
from app.models.user import User
from app.schemas.portfolio import (
    PortfolioBuildRequest,
    PortfolioListItem,
    PortfolioResponse,
)


router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


@router.post("/build", response_model=PortfolioResponse)
def build_portfolio(
    request: PortfolioBuildRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortfolioResponse:
    """Build a portfolio: load prices → compute μ,Σ → MVO → Monte Carlo → save."""

    # 1. Make sure all tickers have FRESH prices (latest trading day).
    # Hits yfinance for any ticker whose cached data is older than 1 day,
    # in parallel. Falls back to synthetic data if yfinance is unavailable.
    ensure_prices_fresh(db, request.tickers, max_staleness_days=1)

    # 2. Load price history.
    prices = price_repo.get_price_history(db, request.tickers, years=10)
    if prices.empty or prices.shape[1] < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough price history to build portfolio",
        )

    # 3. Statistics: μ and Σ.
    log_returns = daily_log_returns(prices)
    mu = mean_returns(log_returns)
    sigma = covariance_matrix(log_returns)

    # 4. Map risk level to target volatility, then solve MVO.
    target_vol = RISK_LEVEL_TO_VOLATILITY[request.risk_level]
    try:
        weights_arr = solve_mvo(mu, sigma, target_volatility=target_vol)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Portfolio infeasible: {e}",
        )

    # Map weights back to tickers (the order from the DataFrame).
    tickers_in_order = list(prices.columns)
    weights = {t: float(w) for t, w in zip(tickers_in_order, weights_arr)}

    # 5. Compute expected stats.
    expected_return = float(weights_arr @ mu)
    expected_variance = float(weights_arr @ sigma @ weights_arr)
    expected_volatility = float(expected_variance ** 0.5)
    # Risk-free rate assumed 0 — adequate for a teaching demo.
    sharpe_ratio = (
        expected_return / expected_volatility
        if expected_volatility > 0 else 0.0
    )

    # 6. Monte Carlo.
    # Random seed per build → each new build shows a different fan chart
    # (even if the MVO weights are identical, because MVO is deterministic
    # given the same μ, Σ, and target). The seed is persisted on the row,
    # so reopening this portfolio later reproduces the exact same chart.
    mc_seed = secrets.randbits(31)
    final_values, cumulative = simulate_portfolio(
        weights=weights_arr,
        mu_annual=mu,
        sigma_annual=sigma,
        initial_value=float(request.amount),
        horizon_years=request.horizon_years,
        seed=mc_seed,
    )
    mc_summary = summarize(
        final_values=final_values,
        cumulative=cumulative,
        initial_value=float(request.amount),
        horizon_years=request.horizon_years,
    )
    histogram = histogram_bins(final_values)

    # 7. Persist.
    name = request.name or f"Portfolio {date.today().isoformat()}"
    portfolio = portfolio_repo.save_portfolio(
        db,
        user_id=user.id,
        name=name,
        amount=request.amount,
        risk_level=request.risk_level,
        horizon_years=request.horizon_years,
        target_volatility=target_vol,
        weights=weights,
        expected_return=expected_return,
        expected_volatility=expected_volatility,
        sharpe_ratio=sharpe_ratio,
        mc_summary=mc_summary,
        mc_seed=mc_seed,
    )

    response = PortfolioResponse.model_validate(portfolio)
    response.histogram = histogram  # type: ignore[assignment]
    return response


@router.get("", response_model=list[PortfolioListItem])
def list_portfolios(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PortfolioListItem]:
    """All portfolios this user has built, newest first."""
    portfolios = portfolio_repo.list_user_portfolios(db, user.id)
    return [PortfolioListItem.model_validate(p) for p in portfolios]


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortfolioResponse:
    """One portfolio by id — must belong to the requesting user."""
    portfolio = portfolio_repo.get_portfolio(db, portfolio_id, user.id)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return PortfolioResponse.model_validate(portfolio)


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete one of the user's portfolios. 404 if not found or not owned."""
    deleted = portfolio_repo.delete_portfolio(db, portfolio_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
