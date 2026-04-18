# Defensive Universe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-inject a small fixed set of defensive ETFs (AGG, IEF, GLD, XLU, XLP) into the candidate universe when `risk_level <= 3`, eliminating the equal-weight collapse for low-risk profiles. No HRP/MVO changes; defensives just enter the universe and the existing optimizer chooses among them.

**Architecture:** A module-level `DEFENSIVE_ETFS` constant and a new `risk_level` parameter on `select_universe`. The auto-inject loop reuses the existing `seen` dedup set so user-supplied tickers in `include_tickers` aren't duplicated, and the existing `excluded` set means `exclude_tickers` overrides auto-injection. An `is_defensive: bool` flag is added to every stock dict (False for regular sector picks, True for defensives) and threaded through pipeline → schema → API → methodology page so the behavior is visible end-to-end.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest, React/TypeScript. No new dependencies.

**Reference spec:** [docs/superpowers/specs/2026-04-18-defensive-universe-design.md](../specs/2026-04-18-defensive-universe-design.md)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/engine/universe.py` | **Modify** | Add `DEFENSIVE_ETFS` constant, add `risk_level` parameter, add auto-inject loop, add `is_defensive=False` to all regular stock entries |
| `backend/app/engine/pipeline.py` | **Modify** | Pass `risk_level` to `select_universe`; copy `is_defensive` from the stock metadata into each holding dict |
| `backend/tests/test_engine/test_universe.py` | **Modify** | Add 5 new tests covering the auto-injection rule, dedup, exclusion, sector labels, and the regular-stock `is_defensive=False` default |
| `backend/tests/test_pipeline_integration.py` | **Modify** | Add one integration test that the engine result's `holdings` list contains `is_defensive` correctly populated end-to-end |
| `backend/app/schemas/portfolio.py` | **Modify** | Add `is_defensive: bool = False` to `HoldingResponse` |
| `backend/app/api/portfolios.py` | **Modify** | The `get_portfolio` endpoint constructs `HoldingResponse` manually — add the `is_defensive` field there. The `generate` endpoint already spreads `**h`, so no change |
| `frontend/src/methodology/MethodologyPage.tsx` | **Modify** | Add one paragraph in the "Choosing Stocks" section explaining defensive auto-injection |
| `backend/scripts/validate_hrp.py` | **Modify** | Extend the real-data spot check section to evaluate the 5 success criteria from spec §5 |

---

## Task 1: Add `DEFENSIVE_ETFS` constant + auto-inject to `select_universe` (TDD)

**Files:**
- Modify: `backend/app/engine/universe.py`
- Modify: `backend/tests/test_engine/test_universe.py`

The `select_universe` function gains a new `risk_level: int` parameter and appends `DEFENSIVE_ETFS` when `risk_level <= 3`. All regular stock dicts get `is_defensive: False`. The auto-inject loop reuses the existing `seen` and `excluded` sets so dedup and exclusion are automatic.

### Step 1: Write the failing tests for auto-injection behavior

Replace the entire body of `backend/tests/test_engine/test_universe.py` with:

```python
from unittest.mock import patch

from app.engine.universe import DEFENSIVE_ETFS, select_universe


def _mock_fetch_info(ticker: str) -> dict:
    stock_db = {
        "AAPL": {"company_name": "Apple", "sector": "Technology", "exchange": "NMS"},
        "MSFT": {"company_name": "Microsoft", "sector": "Technology", "exchange": "NMS"},
        "JNJ": {"company_name": "J&J", "sector": "Healthcare", "exchange": "NYSE"},
    }
    return stock_db.get(ticker, {"company_name": ticker, "sector": "Unknown", "exchange": "NMS"})


def _mock_sector_tickers_with_meta(sectors: list[str]) -> list[dict]:
    return [
        {"ticker": "AAPL", "company_name": "Apple", "sector": "Technology", "exchange": ""},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "exchange": ""},
    ]


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_high_risk_level_excludes_defensives(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=[], exclude_tickers=[], risk_level=4,
    )
    tickers = {s["ticker"] for s in result}
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    # Risk level 4 (and 5) must not see any defensive ETFs.
    for etf in DEFENSIVE_ETFS:
        assert etf["ticker"] not in tickers, f"{etf['ticker']} leaked into risk_level=4 universe"


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_low_risk_level_appends_defensives(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=[], exclude_tickers=[], risk_level=1,
    )
    tickers = {s["ticker"] for s in result}
    # Sector picks are still there (append, not replace).
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    # All defensives present.
    for etf in DEFENSIVE_ETFS:
        assert etf["ticker"] in tickers, f"defensive {etf['ticker']} missing from risk_level=1 universe"


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_user_include_of_defensive_etf_does_not_duplicate(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=["GLD"], exclude_tickers=[], risk_level=2,
    )
    tickers = [s["ticker"] for s in result]
    # GLD should appear exactly once even though both include_tickers
    # AND the auto-inject loop would normally add it.
    assert tickers.count("GLD") == 1


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_exclude_overrides_auto_inject(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=[], exclude_tickers=["AGG"], risk_level=1,
    )
    tickers = {s["ticker"] for s in result}
    # AGG was excluded by the user; auto-inject must respect that.
    assert "AGG" not in tickers
    # The other defensives are still added.
    assert "IEF" in tickers
    assert "GLD" in tickers
    assert "XLU" in tickers
    assert "XLP" in tickers


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_is_defensive_flag_set_correctly(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=[], exclude_tickers=[], risk_level=1,
    )
    by_ticker = {s["ticker"]: s for s in result}
    # Regular sector picks have is_defensive=False.
    assert by_ticker["AAPL"]["is_defensive"] is False
    assert by_ticker["MSFT"]["is_defensive"] is False
    # All defensives have is_defensive=True with stable sector labels.
    expected_sectors = {"AGG": "Bonds", "IEF": "Bonds", "GLD": "Commodities",
                        "XLU": "Utilities", "XLP": "Consumer Staples"}
    for etf_ticker, expected_sector in expected_sectors.items():
        entry = by_ticker[etf_ticker]
        assert entry["is_defensive"] is True
        assert entry["sector"] == expected_sector
```

### Step 2: Run tests to verify they fail

Run from the repo root:

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_engine/test_universe.py -v
```

Expected: collection errors or failures. The first `from app.engine.universe import DEFENSIVE_ETFS` line fails because the constant doesn't exist yet, and `select_universe(..., risk_level=...)` would fail because the parameter doesn't exist.

### Step 3: Add `DEFENSIVE_ETFS` constant and `risk_level` parameter

Modify `backend/app/engine/universe.py` to add the constant after the existing imports and modify the `select_universe` signature. Replace the entire file contents with:

```python
from app.data.country_data import get_allowed_exchanges
from app.data.market import fetch_stock_info


DEFENSIVE_ETFS: list[dict] = [
    {"ticker": "AGG", "company_name": "iShares Core US Aggregate Bond ETF",
     "sector": "Bonds", "exchange": "", "is_defensive": True},
    {"ticker": "IEF", "company_name": "iShares 7-10 Year Treasury Bond ETF",
     "sector": "Bonds", "exchange": "", "is_defensive": True},
    {"ticker": "GLD", "company_name": "SPDR Gold Trust",
     "sector": "Commodities", "exchange": "", "is_defensive": True},
    {"ticker": "XLU", "company_name": "Utilities Select Sector SPDR Fund",
     "sector": "Utilities", "exchange": "", "is_defensive": True},
    {"ticker": "XLP", "company_name": "Consumer Staples Select Sector SPDR Fund",
     "sector": "Consumer Staples", "exchange": "", "is_defensive": True},
]


def select_universe(
    country: str,
    sectors: list[str],
    include_tickers: list[str],
    exclude_tickers: list[str],
    risk_level: int,
) -> list[dict]:
    """Build the candidate stock universe.

    yf.Sector already returns top US-listed companies in each sector, so we
    trust those without per-ticker yfinance validation (which was causing
    rate-limits → empty results). User-provided include_tickers are still
    validated via fetch_stock_info so we have proper company names.

    When risk_level <= 3, append a small fixed set of defensive ETFs to
    the candidate universe (per the defensive-universe spec). Defensives
    are appended, not replaced over user picks, and respect the user's
    exclude_tickers and include_tickers.
    """
    allowed_exchanges = set(get_allowed_exchanges(country))
    excluded = set(exclude_tickers)
    sector_tickers_with_meta = _get_sector_tickers_with_meta(sectors)

    result = []
    seen = set()
    for entry in sector_tickers_with_meta:
        ticker = entry["ticker"]
        if ticker in excluded or ticker in seen:
            continue
        seen.add(ticker)
        entry["is_defensive"] = False
        result.append(entry)

    for ticker in include_tickers:
        if ticker in excluded or ticker in seen:
            continue
        seen.add(ticker)
        info = fetch_stock_info(ticker)
        if info.get("exchange") and info["exchange"] not in allowed_exchanges:
            continue
        result.append({
            "ticker": ticker,
            "company_name": info.get("company_name", ticker),
            "sector": info.get("sector", "Unknown"),
            "exchange": info.get("exchange", ""),
            "is_defensive": False,
        })

    # Auto-inject defensive ETFs for conservative-to-moderate profiles.
    # Appended to the existing selection; reuses `seen` and `excluded` so
    # user-supplied includes aren't duplicated and excludes still win.
    if risk_level <= 3:
        for etf in DEFENSIVE_ETFS:
            if etf["ticker"] in excluded or etf["ticker"] in seen:
                continue
            seen.add(etf["ticker"])
            result.append(dict(etf))  # copy so callers can't mutate the constant

    return result


SECTOR_MAP = {
    "Technology": "technology",
    "Healthcare": "healthcare",
    "Energy": "energy",
    "Finance": "financial-services",
    "Consumer": "consumer-cyclical",
    "Real Estate": "real-estate",
    "Industrial": "industrials",
}


def _get_sector_tickers_with_meta(sectors: list[str]) -> list[dict]:
    """Return top companies per sector with name + sector metadata from yfinance."""
    import yfinance as yf
    out: list[dict] = []
    for sector in sectors:
        yf_sector = SECTOR_MAP.get(sector)
        if not yf_sector:
            continue
        try:
            top = yf.Sector(yf_sector).top_companies
        except Exception:
            continue
        if top is None or top.empty:
            continue
        for symbol, row in top.head(15).iterrows():
            out.append({
                "ticker": symbol,
                "company_name": row.get("name", symbol),
                "sector": sector,
                "exchange": "",
            })
    return out
```

Three notable points about this implementation:

1. **`is_defensive: False` is added to regular stock entries** — for sector picks via `entry["is_defensive"] = False` (mutating the dict from `_get_sector_tickers_with_meta`), and for `include_tickers` via the explicit field in the dict literal.
2. **`dict(etf)` shallow-copies the constant** when appending — so any downstream mutation can't accidentally corrupt the module-level `DEFENSIVE_ETFS` list.
3. **`risk_level` is positional-required**, not optional with a default. This forces every caller to make an explicit choice — there's no quiet "what does risk_level=None mean?" path.

### Step 4: Run tests to verify they pass

Run from the repo root:

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_engine/test_universe.py -v
```

Expected: 5 PASSED.

### Step 5: Commit

```bash
cd /Users/roeykarif/Portfolio-Builder
git add backend/app/engine/universe.py backend/tests/test_engine/test_universe.py
git commit -m "feat(universe): auto-inject defensive ETFs for low-risk profiles

Add DEFENSIVE_ETFS constant (AGG, IEF, GLD, XLU, XLP) and a risk_level
parameter to select_universe. When risk_level <= 3, append the defensive
ETFs to the candidate universe; otherwise leave the universe unchanged.

Defensives are appended (not replacing user sector picks), reuse the
existing seen-set for dedup against include_tickers, and honor
exclude_tickers. Each stock dict now carries is_defensive: bool so the
flag flows through the rest of the pipeline.

Tests cover: high-risk exclusion, low-risk injection, dedup of
user-included defensives, exclude-tickers overrides auto-inject, and
the is_defensive flag plus stable per-ETF sector labels (Bonds,
Commodities, Utilities, Consumer Staples)."
```

---

## Task 2: Pipeline passes `risk_level` and threads `is_defensive` through

**Files:**
- Modify: `backend/app/engine/pipeline.py`
- Modify: `backend/tests/test_pipeline_integration.py`

The pipeline needs two changes: pass `risk_level` to `select_universe`, and copy `is_defensive` from each stock's metadata into the holdings dict it builds for the result.

### Step 1: Write the failing integration test

Append to `backend/tests/test_pipeline_integration.py`:

```python
def _fake_universe_with_defensives(country, sectors, include_tickers, exclude_tickers, risk_level):
    """Mock universe selector that mirrors the real one's auto-inject
    behavior: 10 fake stocks always, plus 5 defensive ETFs when risk_level <= 3."""
    stocks = [
        {"ticker": f"T{i}", "company_name": f"Co{i}", "sector": "Technology",
         "exchange": "", "is_defensive": False}
        for i in range(10)
    ]
    if risk_level <= 3:
        stocks.extend([
            {"ticker": "AGG", "company_name": "iShares Core US Aggregate Bond ETF",
             "sector": "Bonds", "exchange": "", "is_defensive": True},
            {"ticker": "IEF", "company_name": "iShares 7-10 Year Treasury Bond ETF",
             "sector": "Bonds", "exchange": "", "is_defensive": True},
            {"ticker": "GLD", "company_name": "SPDR Gold Trust",
             "sector": "Commodities", "exchange": "", "is_defensive": True},
            {"ticker": "XLU", "company_name": "Utilities Select Sector SPDR Fund",
             "sector": "Utilities", "exchange": "", "is_defensive": True},
            {"ticker": "XLP", "company_name": "Consumer Staples Select Sector SPDR Fund",
             "sector": "Consumer Staples", "exchange": "", "is_defensive": True},
        ])
    return stocks


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe_with_defensives)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_holdings_carry_is_defensive_flag(mock_dl, mock_uni):
    result = generate_portfolio(
        country="US", risk_level=2, investment_horizon="3-5y",
        available_amount=10_000.0, target_return=10.0,
        preferred_sectors=["Technology"], include_tickers=[], exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    # Every holding must have the is_defensive field populated.
    for h in result["holdings"]:
        assert "is_defensive" in h, f"holding missing is_defensive: {h}"
        assert isinstance(h["is_defensive"], bool)
    # At least one defensive ETF is in the holdings (the synthetic universe
    # plus risk_level=2 should make HRP put non-trivial weight on bonds).
    defensive_holdings = [h for h in result["holdings"] if h["is_defensive"]]
    assert len(defensive_holdings) > 0, "expected at least one defensive holding at risk_level=2"
```

### Step 2: Run the test to verify it fails

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_pipeline_integration.py::test_pipeline_holdings_carry_is_defensive_flag -v
```

Expected: FAIL. The pipeline currently doesn't pass `risk_level` to `select_universe` (TypeError on the new mock's required `risk_level` param), and even if that's fixed, the holdings dict construction doesn't include `is_defensive`.

### Step 3: Update `pipeline.py` to pass `risk_level` and emit `is_defensive`

Two edits in `backend/app/engine/pipeline.py`. First, pass `risk_level` through to `select_universe`. Find the `# Stage 1: Universe Selection` block (currently lines 33-39):

```python
    # Stage 1: Universe Selection
    stocks = select_universe(
        country=country,
        sectors=preferred_sectors,
        include_tickers=include_tickers,
        exclude_tickers=exclude_tickers,
    )
```

Replace with:

```python
    # Stage 1: Universe Selection
    stocks = select_universe(
        country=country,
        sectors=preferred_sectors,
        include_tickers=include_tickers,
        exclude_tickers=exclude_tickers,
        risk_level=risk_level,
    )
```

Second, the holdings construction loop needs to copy `is_defensive` into each holding dict. Find the loop (currently around line 173 after the Task 2 + Task 5 changes). The current code is:

```python
    holdings = []
    for i, ticker in enumerate(valid_tickers):
        w = float(weights_array[i])
        if w < 0.01:
            continue
        stock = ticker_to_stock[ticker]
        holdings.append({
            "ticker": ticker,
            "company_name": stock["company_name"],
            "sector": stock["sector"],
            "allocation_pct": round(w * 100, 2),
            "expected_return": round(stock["expected_return"] * 100, 2),
        })
```

Replace with (only the `holdings.append({...})` dict gains one field):

```python
    holdings = []
    for i, ticker in enumerate(valid_tickers):
        w = float(weights_array[i])
        if w < 0.01:
            continue
        stock = ticker_to_stock[ticker]
        holdings.append({
            "ticker": ticker,
            "company_name": stock["company_name"],
            "sector": stock["sector"],
            "allocation_pct": round(w * 100, 2),
            "expected_return": round(stock["expected_return"] * 100, 2),
            "is_defensive": stock.get("is_defensive", False),
        })
```

Use `.get("is_defensive", False)` rather than `stock["is_defensive"]` — defensive in case any code path supplies a stock dict without the field (the explicit default makes the contract obvious to readers).

### Step 4: Run all tests to verify they pass

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_pipeline_integration.py tests/test_hrp.py tests/test_engine/test_universe.py -v
```

Expected: PASS for everything — 5 universe tests + the existing 9 pipeline tests + the 1 new pipeline test + 8 HRP tests = 23 total. Note that several of the existing pipeline tests use the `_fake_universe` fixture (without `risk_level` parameter); they may now fail if the test fixtures don't accept the new parameter. If they fail with a `TypeError: _fake_universe() got an unexpected keyword argument 'risk_level'`, update the fixture signatures in `test_pipeline_integration.py` to accept (and ignore) `risk_level`:

```python
def _fake_universe(country, sectors, include_tickers, exclude_tickers, risk_level):
    return [
        {"ticker": f"T{i}", "company_name": f"Co{i}", "sector": "Technology",
         "exchange": "", "is_defensive": False}
        for i in range(10)
    ]


def _fake_universe_30(country, sectors, include_tickers, exclude_tickers, risk_level):
    return [
        {"ticker": f"T{i:02d}", "company_name": f"Co{i}", "sector": "Technology",
         "exchange": "", "is_defensive": False}
        for i in range(30)
    ]
```

Two changes per fixture: add `risk_level` parameter, and add `"is_defensive": False` to every dict (so the pipeline's `stock.get("is_defensive", False)` always finds the field, matching the contract from the universe layer).

### Step 5: Commit

```bash
cd /Users/roeykarif/Portfolio-Builder
git add backend/app/engine/pipeline.py backend/tests/test_pipeline_integration.py
git commit -m "feat(pipeline): pass risk_level to universe + thread is_defensive

The pipeline now passes risk_level to select_universe (which uses it
to decide whether to auto-inject defensive ETFs) and copies the
is_defensive flag from each stock's metadata into its holding dict.

Existing test fixtures _fake_universe and _fake_universe_30 are updated
to accept the new risk_level parameter and to populate is_defensive=False
on every stock — matching the universe layer's contract."
```

---

## Task 3: Add `is_defensive` to `HoldingResponse` schema and API

**Files:**
- Modify: `backend/app/schemas/portfolio.py`
- Modify: `backend/app/api/portfolios.py`

The Pydantic schema gains the field; the `generate` API endpoint needs no change because it already spreads `**h`; the `get_portfolio` endpoint manually constructs `HoldingResponse` and needs one new line.

### Step 1: Add `is_defensive` to `HoldingResponse`

In `backend/app/schemas/portfolio.py`, locate the `HoldingResponse` class at the top of the file (currently lines 4-9):

```python
class HoldingResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str
    allocation_pct: float
    expected_return: float
```

Replace with:

```python
class HoldingResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str
    allocation_pct: float
    expected_return: float
    is_defensive: bool = False
```

The default `False` keeps it backward-compatible with portfolios stored before this change.

### Step 2: Update `get_portfolio` endpoint to pass `is_defensive`

In `backend/app/api/portfolios.py`, locate the `get_portfolio` endpoint's `HoldingResponse` construction (currently around lines 134-139):

```python
        holdings=[
            HoldingResponse(
                ticker=h.ticker, company_name=h.company_name, sector=h.sector,
                allocation_pct=float(h.allocation_pct), expected_return=float(h.expected_return),
            ) for h in holdings
        ],
```

Replace with:

```python
        holdings=[
            HoldingResponse(
                ticker=h.ticker, company_name=h.company_name, sector=h.sector,
                allocation_pct=float(h.allocation_pct), expected_return=float(h.expected_return),
                is_defensive=getattr(h, "is_defensive", False),
            ) for h in holdings
        ],
```

The `getattr(..., False)` is because the `PortfolioHolding` SQLAlchemy model may not have an `is_defensive` column yet (we haven't added it in this phase — persisting the flag is out of scope per the spec). For portfolios stored before this change, the field is missing entirely and `getattr` returns the default. The `generate` endpoint already does `HoldingResponse(**h)` which spreads the dict including the new key, so that endpoint needs no change.

### Step 3: Verify schema and API import cleanly

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib python -c "
from app.schemas.portfolio import HoldingResponse
from app.api.portfolios import router
fields = list(HoldingResponse.model_fields.keys())
print('HoldingResponse fields:', fields)
assert 'is_defensive' in fields, 'is_defensive missing from schema'
print('Routes:', [r.path for r in router.routes])
print('OK')
"
```

Expected output:
```
HoldingResponse fields: ['ticker', 'company_name', 'sector', 'allocation_pct', 'expected_return', 'is_defensive']
Routes: ['/portfolios/generate/{profile_id}', '/portfolios', '/portfolios/{portfolio_id}', '/portfolios/{portfolio_id}/archive', '/portfolios/{portfolio_id}']
OK
```

### Step 4: Run the full test suite to confirm no regressions

```bash
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_pipeline_integration.py tests/test_hrp.py tests/test_engine/test_universe.py -v
```

Expected: same 23 tests as Task 2, all PASS.

### Step 5: Commit

```bash
cd /Users/roeykarif/Portfolio-Builder
git add backend/app/schemas/portfolio.py backend/app/api/portfolios.py
git commit -m "feat(api): expose is_defensive on HoldingResponse

HoldingResponse gains an is_defensive: bool field (default False for
backward compatibility). The generate endpoint already spreads **h so
it picks up the new key automatically; get_portfolio constructs holdings
manually and uses getattr to handle pre-existing portfolios that don't
have the column."
```

---

## Task 4: Methodology page paragraph

**Files:**
- Modify: `frontend/src/methodology/MethodologyPage.tsx`

### Step 1: Add the defensive paragraph

In `frontend/src/methodology/MethodologyPage.tsx`, locate the `#stocks` section (the "Choosing Stocks" section, currently around lines 22-29):

```tsx
      <section id="stocks" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Choosing Stocks</h2>
        <p className="text-gray-700">
          We start with a universe of well-known, liquid companies listed on major exchanges in your selected country.
          From that pool, we focus on the sectors you're interested in — Technology, Healthcare, and so on.
          You can also add specific tickers you want included, or exclude any you'd rather avoid.
        </p>
      </section>
```

Replace with:

```tsx
      <section id="stocks" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Choosing Stocks</h2>
        <p className="text-gray-700 mb-3">
          We start with a universe of well-known, liquid companies listed on major exchanges in your selected country.
          From that pool, we focus on the sectors you're interested in — Technology, Healthcare, and so on.
          You can also add specific tickers you want included, or exclude any you'd rather avoid.
        </p>
        <p className="text-gray-700">
          <strong>Defensive assets for conservative profiles.</strong> If you pick a conservative-to-moderate
          risk level (1, 2, or 3), we automatically add a small set of defensive assets to your portfolio's
          candidate pool: broad investment-grade bonds (AGG), intermediate Treasuries (IEF), gold (GLD), and
          defensive equity (utilities XLU and consumer staples XLP). These don't replace your sector choices —
          they're added alongside them, giving the optimizer the option to use them when a low risk cap requires
          reducing volatility. Higher risk profiles (4 and 5) don't include them automatically, since they
          conflict with an aggressive growth target.
        </p>
      </section>
```

Two changes: the existing paragraph gains `mb-3` for spacing, and a new paragraph follows it with the defensive explanation. Indentation matches the surrounding 8-space pattern.

### Step 2: Build / type check

```bash
cd /Users/roeykarif/Portfolio-Builder/frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds. If `npm run build` isn't a script in `package.json`, fall back to `npx tsc --noEmit`.

If neither works (no node_modules), at minimum verify tag balance:

```bash
cd /Users/roeykarif/Portfolio-Builder && python3 -c "
content = open('frontend/src/methodology/MethodologyPage.tsx').read()
assert content.count('<section') == content.count('</section>'), 'mismatched section tags'
assert content.count('<p ') == content.count('</p>'), 'mismatched p tags'
assert 'Defensive assets for conservative profiles' in content, 'defensive paragraph missing'
print('OK')
"
```

### Step 3: Commit

```bash
cd /Users/roeykarif/Portfolio-Builder
git add frontend/src/methodology/MethodologyPage.tsx
git commit -m "docs(methodology): explain defensive auto-injection for low-risk profiles

Adds one paragraph to the Choosing Stocks section explaining that risk
levels 1-3 automatically include AGG, IEF, GLD, XLU, and XLP alongside
the user's sector picks. Wording matches the design spec."
```

---

## Task 5: Validation script extension

**Files:**
- Modify: `backend/scripts/validate_hrp.py`

Extend the real-data spot check to evaluate the 5 success criteria from spec §5. Output a clean PASS/FAIL summary at the end.

### Step 1: Replace the `run_real_data_spot_check` function

In `backend/scripts/validate_hrp.py`, find the existing `run_real_data_spot_check` function. Replace it with the version below. The new version captures each portfolio's holdings into a dict so the post-loop success-criteria block can analyze them.

```python
DEFENSIVE_TICKERS = {"AGG", "IEF", "GLD", "XLU", "XLP"}


def _portfolio_l1_distance(p_a: dict, p_b: dict) -> float:
    """L1 distance between two portfolios' weight vectors over the union
    of their tickers. Each input is {ticker: weight_pct}."""
    tickers = set(p_a) | set(p_b)
    return sum(abs(p_a.get(t, 0.0) - p_b.get(t, 0.0)) for t in tickers) / 100.0


def _defensive_share(holdings: list[dict]) -> float:
    """Share of total weight held in defensive ETFs (as a fraction)."""
    return sum(h["allocation_pct"] for h in holdings if h["ticker"] in DEFENSIVE_TICKERS) / 100.0


def run_real_data_spot_check():
    print("=" * 64)
    print("TABLE 4 — Real-data spot check (live yfinance, 5 portfolios)")
    print("=" * 64)
    from app.engine.pipeline import generate_portfolio

    runs: dict[int, dict] = {}
    for risk_level in [1, 2, 3, 4, 5]:
        try:
            result = generate_portfolio(
                country="US",
                risk_level=risk_level,
                investment_horizon="3-5y",
                available_amount=10_000.0,
                target_return=10.0,
                preferred_sectors=["Technology"],
                include_tickers=[],
                exclude_tickers=[],
                db=None,
            )
        except Exception as e:
            print(f"risk_level={risk_level}: EXCEPTION — {type(e).__name__}: {e}")
            continue

        if "error" in result:
            print(f"risk_level={risk_level}: ERROR — {result['error']}")
            continue

        runs[risk_level] = result
        n_holdings = len(result["holdings"])
        top_3 = sorted(result["holdings"], key=lambda h: -h["allocation_pct"])[:3]
        top_str = ", ".join(
            f"{h['ticker']}{'*' if h.get('is_defensive') else ''}({h['allocation_pct']:.1f}%)"
            for h in top_3
        )
        hrp_cand = result.get("hrp_candidate_vol")
        hrp_cand_str = f"{hrp_cand:.4f}" if hrp_cand is not None else "n/a"
        defensive = _defensive_share(result["holdings"])
        print(
            f"risk_level={risk_level} method={result['weighting_method']:<22} "
            f"risk_score={result['risk_score']:>5.2f} hrp_cand={hrp_cand_str:>7} "
            f"n_holdings={n_holdings:>2} defensive_share={defensive*100:>5.1f}%"
        )
        print(f"               top 3 (* = defensive): {top_str}")
    print()

    print("=" * 64)
    print("TABLE 5 — Success criteria (defensive universe, spec §5)")
    print("=" * 64)
    if not all(rl in runs for rl in [1, 2, 3, 4, 5]):
        print("SKIP — not all 5 risk levels produced a portfolio (see errors above)")
        return

    # Extract weight vectors as {ticker: pct} for each risk level.
    pf = {
        rl: {h["ticker"]: h["allocation_pct"] for h in runs[rl]["holdings"]}
        for rl in [1, 2, 3, 4, 5]
    }

    # Criterion 1: no equal-weight collapse on risk levels 1-3.
    methods_1_3 = {rl: runs[rl]["weighting_method"] for rl in [1, 2, 3]}
    crit1_pass = all(m in {"hrp", "mvo_risk_cap"} for m in methods_1_3.values())
    print(f"  [1] No equal-weight collapse on risk_level 1-3:  {'PASS' if crit1_pass else 'FAIL'}")
    print(f"      methods: {methods_1_3}")

    # Criterion 2: risk-level differentiation (1 vs 2, 2 vs 3, 1 vs 3).
    pairs = [(1, 2), (2, 3), (1, 3)]
    deltas = {p: _portfolio_l1_distance(pf[p[0]], pf[p[1]]) for p in pairs}
    # Threshold calibrated empirically; spec leaves it open. Use 0.10 as a
    # conservative starting point — anything below that suggests the slider
    # isn't doing much, well above means the algorithm is responding to risk_level.
    crit2_pass = sum(1 for d in deltas.values() if d > 0.10) >= 2
    print(f"  [2] Risk-level differentiation (>=2 of 3 pairs L1>0.10):  {'PASS' if crit2_pass else 'FAIL'}")
    for p, d in deltas.items():
        print(f"      L1(risk={p[0]}, risk={p[1]}) = {d:.3f}")

    # Criterion 3: defensive allocation present at risk_level 1 (>= 30%).
    def_share_1 = _defensive_share(runs[1]["holdings"])
    crit3_pass = def_share_1 >= 0.30
    print(f"  [3] Defensive share at risk_level=1 >= 30%:  {'PASS' if crit3_pass else 'FAIL'}")
    print(f"      observed: {def_share_1*100:.1f}%")

    # Criterion 4: defensive monotonicity across risk levels 1-3 (allow <5pp inversion).
    shares_1_3 = [_defensive_share(runs[rl]["holdings"]) for rl in [1, 2, 3]]
    crit4_pass = (shares_1_3[0] >= shares_1_3[1] - 0.05) and (shares_1_3[1] >= shares_1_3[2] - 0.05)
    print(f"  [4] Defensive monotonicity (1 >= 2 >= 3, +/-5pp slack):  {'PASS' if crit4_pass else 'FAIL'}")
    print(f"      shares: risk_1={shares_1_3[0]*100:.1f}%, risk_2={shares_1_3[1]*100:.1f}%, risk_3={shares_1_3[2]*100:.1f}%")

    # Criterion 5: no defensives in risk levels 4 or 5.
    crit5_pass = all(
        all(not h.get("is_defensive", False) for h in runs[rl]["holdings"])
        for rl in [4, 5]
    )
    print(f"  [5] No defensives in risk_level 4 or 5:  {'PASS' if crit5_pass else 'FAIL'}")
    for rl in [4, 5]:
        defensives_present = [h["ticker"] for h in runs[rl]["holdings"] if h.get("is_defensive", False)]
        print(f"      risk_level={rl} defensive holdings: {defensives_present or 'none'}")

    print()
    n_pass = sum([crit1_pass, crit2_pass, crit3_pass, crit4_pass, crit5_pass])
    print(f"  OVERALL: {n_pass}/5 success criteria passing")
    print()
```

The threshold for criterion 2 is set at L1 > 0.10 as a starting point. The spec deliberately left this open ("calibrated empirically during implementation"). If the actual observed L1 deltas come in materially different (e.g. all > 0.5, or all hovering around 0.05), revisit the threshold and update the script — that's expected and explicitly part of the success-criteria contract.

### Step 2: Run the script and inspect output

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib python scripts/validate_hrp.py 2>&1 | tail -50
```

Expected output:
- TABLE 4 (real-data spot check): risk levels 1, 2, 3 should produce **different** portfolios with `weighting_method` ∈ {`hrp`, `mvo_risk_cap`}, NOT `fallback_equal_weight`. Top-3 holdings should include some defensives (marked with `*`).
- TABLE 5 (success criteria): 5/5 PASS, or close to it. If criterion 2's L1 threshold doesn't match observed reality, adjust to the actual observed range and rerun.

If the `OVERALL` line shows < 5/5, do NOT proceed. Investigate which criteria failed and adjust either the threshold (criterion 2 only) or surface a real bug.

### Step 3: Commit

```bash
cd /Users/roeykarif/Portfolio-Builder
git add backend/scripts/validate_hrp.py
git commit -m "chore(validation): add defensive-universe success-criteria checks

Extends the real-data spot check to evaluate the 5 success criteria
from spec §5: no equal-weight collapse on risk_level 1-3, risk-level
differentiation, defensive share at low risk, defensive monotonicity,
and no defensives at high risk. Each criterion prints PASS/FAIL with
the observed values.

The L1 threshold for criterion 2 (risk-level differentiation) is set
at 0.10 as a starting point per the spec's deliberate softening — to
be tuned against observed runs if the actual range differs materially."
```

---

## Final verification

After all 5 tasks complete, run the full backend test suite once more:

```bash
source /Users/roeykarif/Portfolio-Builder/backend/venv/bin/activate
cd /Users/roeykarif/Portfolio-Builder/backend
DYLD_LIBRARY_PATH=$(pwd)/venv/lib/python3.10/site-packages/xgboost/lib pytest --noconftest tests/test_pipeline_integration.py tests/test_hrp.py tests/test_engine/test_universe.py -v
```

Expected: 23 tests pass — 5 universe + 9 pipeline (4 pre-existing + 4 from P3 + 1 from this plan) + 8 HRP + 1 regression test from the validation findings = wait, let me recount:
- test_engine/test_universe.py: 5 tests (all from this plan)
- test_pipeline_integration.py: 4 pre-existing + 4 from P3 + 1 weights-sum regression + 1 from this plan (is_defensive) = 10
- test_hrp.py: 8 tests

= **23 tests total**.

Then run the validation script and confirm `OVERALL: 5/5 success criteria passing` (or, if criterion 2's threshold needed adjustment, that the adjusted version passes 5/5).
