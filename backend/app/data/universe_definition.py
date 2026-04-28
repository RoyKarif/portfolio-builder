"""Single source of truth for the curated universe.

Used by:
  - app.main (startup hook) to register Asset rows on boot
  - scripts.seed_universe (CLI tool) for manual bulk seed
  - app.data.price_fetcher (auto-fetcher) to know which class is which

Selection rationale (32 ETFs):
  - Span 5 asset classes (equity, bond, commodity, real_estate, cash).
  - Within equity: cover broad-market US, all 11 GICS sectors, and
    multiple international regions (developed, emerging, EU, Japan,
    China, India).
  - Within bonds: cover the duration spectrum (1-3M, 7-10Y, 20+Y) plus
    investment grade and high yield.
  - Each ticker chosen for liquidity, expense ratio, and AUM, so historical
    data is reliable.
  - 32 sits in the textbook "sweet spot" for Markowitz: enough for
    meaningful diversification across asset classes and geographies,
    not so many that estimation noise in μ and Σ dominates the signal.
    With ~2500 days of data, 32 assets gives roughly 78x more observations
    than parameters — plenty of statistical headroom.
"""

# (ticker, display_name, asset_class)
CURATED_UNIVERSE: list[tuple[str, str, str]] = [
    # --- US equity, broad market ---
    ("SPY", "SPDR S&P 500 ETF", "equity"),
    ("QQQ", "Invesco QQQ (NASDAQ-100)", "equity"),
    ("IWM", "iShares Russell 2000 (Small Cap)", "equity"),
    ("VTI", "Vanguard Total US Stock Market", "equity"),

    # --- US equity, all 11 GICS sectors ---
    ("XLK", "Technology Select Sector SPDR", "equity"),
    ("XLF", "Financials Select Sector SPDR", "equity"),
    ("XLE", "Energy Select Sector SPDR", "equity"),
    ("XLV", "Health Care Select Sector SPDR", "equity"),
    ("XLI", "Industrials Select Sector SPDR", "equity"),
    ("XLY", "Consumer Discretionary Select Sector SPDR", "equity"),
    ("XLP", "Consumer Staples Select Sector SPDR", "equity"),
    ("XLU", "Utilities Select Sector SPDR", "equity"),
    ("XLB", "Materials Select Sector SPDR", "equity"),
    ("XLRE", "Real Estate Select Sector SPDR", "equity"),
    ("XLC", "Communication Services Select Sector SPDR", "equity"),

    # --- International equity ---
    ("EFA", "iShares MSCI EAFE (Developed ex-US)", "equity"),
    ("EEM", "iShares MSCI Emerging Markets", "equity"),
    ("VGK", "Vanguard FTSE Europe", "equity"),
    ("EWJ", "iShares MSCI Japan", "equity"),
    ("FXI", "iShares China Large-Cap", "equity"),
    ("INDA", "iShares MSCI India", "equity"),

    # --- Bonds (full duration spectrum + credit) ---
    ("AGG", "iShares Core US Aggregate Bond", "bond"),
    ("TLT", "iShares 20+ Year Treasury", "bond"),
    ("IEF", "iShares 7-10 Year Treasury", "bond"),
    ("SHY", "iShares 1-3 Year Treasury", "bond"),
    ("LQD", "iShares iBoxx Investment Grade Corporate", "bond"),
    ("HYG", "iShares iBoxx High Yield Corporate", "bond"),

    # --- Commodities ---
    ("GLD", "SPDR Gold Trust", "commodity"),
    ("SLV", "iShares Silver Trust", "commodity"),
    ("DBC", "Invesco DB Commodity Index", "commodity"),

    # --- Real estate ---
    ("VNQ", "Vanguard Real Estate ETF", "real_estate"),
    ("IYR", "iShares US Real Estate", "real_estate"),

    # --- Cash equivalent ---
    ("BIL", "SPDR 1-3 Month T-Bill", "cash"),
]
