"""Single source of truth for the curated universe.

Used by:
  - app.main (startup hook) to register Asset rows on boot
  - scripts.seed_universe (CLI tool) for manual bulk seed
  - app.data.price_fetcher (auto-fetcher) to know which class is which
"""

# (ticker, display_name, asset_class)
CURATED_UNIVERSE: list[tuple[str, str, str]] = [
    # --- US equity, broad ---
    ("SPY", "SPDR S&P 500 ETF", "equity"),
    ("QQQ", "Invesco QQQ (NASDAQ-100)", "equity"),
    ("IWM", "iShares Russell 2000 (Small Cap)", "equity"),
    ("VTI", "Vanguard Total Stock Market", "equity"),
    # --- US equity, sector / style ---
    ("XLK", "Technology Select Sector SPDR", "equity"),
    ("XLF", "Financials Select Sector SPDR", "equity"),
    ("XLE", "Energy Select Sector SPDR", "equity"),
    ("XLV", "Health Care Select Sector SPDR", "equity"),
    # --- International equity ---
    ("EFA", "iShares MSCI EAFE (Developed ex-US)", "equity"),
    ("EEM", "iShares MSCI Emerging Markets", "equity"),
    ("VGK", "Vanguard FTSE Europe", "equity"),
    # --- Bonds ---
    ("AGG", "iShares Core U.S. Aggregate Bond", "bond"),
    ("TLT", "iShares 20+ Year Treasury", "bond"),
    ("LQD", "iShares iBoxx Investment Grade Corporate", "bond"),
    ("HYG", "iShares iBoxx High Yield Corporate", "bond"),
    # --- Commodities ---
    ("GLD", "SPDR Gold Trust", "commodity"),
    ("SLV", "iShares Silver Trust", "commodity"),
    ("DBC", "Invesco DB Commodity Index", "commodity"),
    # --- Real estate ---
    ("VNQ", "Vanguard Real Estate ETF", "real_estate"),
    # --- Cash equivalent ---
    ("BIL", "SPDR 1-3 Month T-Bill", "cash"),
]
