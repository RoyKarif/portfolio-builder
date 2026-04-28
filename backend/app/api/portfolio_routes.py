"""Portfolio endpoints: build / list / get / delete."""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.data import asset_repo, portfolio_repo, price_repo, yfinance_client
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


# How recent the price history must be before we re-fetch from yfinance
# for a custom ticker. 7 days is a pragmatic default — fresh enough for
# a portfolio decision, not so strict that we hammer yfinance.
PRICE_FRESHNESS_DAYS = 7


def _ensure_prices_available(
    db: Session,
    tickers: list[str],
    years: int = 10,
) -> None:
    """Make sure every requested ticker has fresh prices in the DB.

    For curated tickers seeded ahead of time, this is a no-op.
    For custom tickers (added by user), we hit yfinance the first time
    or when local data is stale.
    """
    cutoff = date.today() - timedelta(days=PRICE_FRESHNESS_DAYS)

    for ticker in tickers:
        latest = price_repo.latest_price_date(db, ticker)
        if latest is not None and latest >= cutoff:
            # Fresh enough — skip.
            continue

        # Either we have no data, or it's stale. Fetch from yfinance.
        try:
            rows = yfinance_client.fetch_price_history(ticker, years=years)
        except yfinance_client.YFinanceError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot fetch prices for {ticker}: {e}",
            )

        # Make sure the asset row exists. If not (custom ticker), create one
        # with sensible defaults. The user can refine asset_class later.
        if asset_repo.get_asset_by_ticker(db, ticker) is None:
            asset_repo.create_asset(
                db,
                ticker=ticker,
                name=ticker,
                asset_class="equity",  # default; user can correct
                is_curated=False,
            )

        price_repo.bulk_insert_prices(db, ticker, rows)
        db.commit()


@router.post("/build", response_model=PortfolioResponse)
def build_portfolio(
    request: PortfolioBuildRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortfolioResponse:
    """Build a portfolio: load prices → compute μ,Σ → MVO → Monte Carlo → save."""

    # 1. Make sure all tickers have prices.
    _ensure_prices_available(db, request.tickers)

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
    mc_seed = 42  # deterministic; persisted on the row for reproducibility
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
