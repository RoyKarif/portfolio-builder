# Portfolio Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add portfolio deletion, redesign the portfolio results page for beginners, and add a methodology info page.

**Architecture:** Small backend change (one DELETE endpoint with cascade). Frontend adds shared components (`InfoTooltip`, `ConfirmDeleteModal`), new portfolio-page components (`HeroScenarioCard`, `RiskGauge`, `DiversificationCard`, `ScenarioGrid`), and a new `/methodology` route. The existing `PortfolioPage` is restructured; deprecated components (`RiskComparison`, `BacktestChart`, `MonteCarloChart`) are removed.

**Tech Stack:** Backend: FastAPI + SQLAlchemy + pytest. Frontend: React 18 + react-router-dom + Tailwind + recharts (no test runner — use TypeScript compilation and manual browser verification).

**Spec:** [docs/superpowers/specs/2026-04-17-portfolio-page-redesign-design.md](../specs/2026-04-17-portfolio-page-redesign-design.md)

---

## Task 1: Backend DELETE endpoint with cascade

**Files:**
- Modify: `backend/app/models/portfolio.py`
- Modify: `backend/app/api/portfolios.py`
- Modify: `backend/tests/test_portfolios.py`

- [ ] **Step 1: Add cascade to SQLAlchemy relationships**

In `backend/app/models/portfolio.py`, update the `Portfolio.holdings` relationship and `Portfolio.snapshots` relationship to cascade:

```python
    holdings = relationship("PortfolioHolding", back_populates="portfolio", cascade="all, delete-orphan")
    snapshots = relationship("PortfolioSnapshot", back_populates="portfolio", cascade="all, delete-orphan")
```

- [ ] **Step 2: Write failing test for DELETE endpoint**

In `backend/tests/test_portfolios.py`, append:

```python
@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_delete_portfolio(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    gen_resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    portfolio_id = gen_resp.json()["id"]

    del_resp = client.delete(f"/portfolios/{portfolio_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/portfolios/{portfolio_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_portfolio_not_found(client, auth_headers):
    resp = client.delete("/portfolios/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


@patch("app.api.portfolios.generate_portfolio", return_value=MOCK_ENGINE_RESULT)
def test_delete_portfolio_requires_auth(mock_engine, client, auth_headers):
    profile_resp = client.post("/profiles", json=PROFILE_PAYLOAD, headers=auth_headers)
    profile_id = profile_resp.json()["id"]
    gen_resp = client.post(f"/portfolios/generate/{profile_id}", headers=auth_headers)
    portfolio_id = gen_resp.json()["id"]

    resp = client.delete(f"/portfolios/{portfolio_id}")
    assert resp.status_code == 401
```

- [ ] **Step 3: Run tests and verify they fail**

```bash
docker compose run --rm backend pytest tests/test_portfolios.py::test_delete_portfolio -v
```

Expected: FAIL (405 Method Not Allowed or similar — endpoint does not exist).

- [ ] **Step 4: Implement the DELETE endpoint**

In `backend/app/api/portfolios.py`, add this route at the end of the file (after `archive_portfolio`):

```python
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
```

- [ ] **Step 5: Run tests and verify they pass**

```bash
docker compose run --rm backend pytest tests/test_portfolios.py -v
```

Expected: all three new tests PASS, existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/portfolio.py backend/app/api/portfolios.py backend/tests/test_portfolios.py
git commit -m "feat(api): add DELETE /portfolios/{id} with cascade"
```

---

## Task 2: Frontend API client helpers

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add helper functions to the API client**

In `frontend/src/api/client.ts`, append (after the `export default api;` line, add before it — move the export to the bottom):

```typescript
export const deletePortfolio = (id: string) => api.delete(`/portfolios/${id}`);
export const archivePortfolio = (id: string) => api.patch(`/portfolios/${id}/archive`);
```

The final file should end with:

```typescript
export const deletePortfolio = (id: string) => api.delete(`/portfolios/${id}`);
export const archivePortfolio = (id: string) => api.patch(`/portfolios/${id}/archive`);

export default api;
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(api-client): add deletePortfolio and archivePortfolio helpers"
```

---

## Task 3: InfoTooltip shared component

**Files:**
- Create: `frontend/src/components/InfoTooltip.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/InfoTooltip.tsx` with:

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";

interface Props {
  text: string;
  learnMoreAnchor?: string;
}

export default function InfoTooltip({ text, learnMoreAnchor }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-block align-middle ml-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className="w-4 h-4 rounded-full bg-gray-200 text-gray-600 text-[10px] font-bold hover:bg-blue-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
        aria-label="More info"
      >
        ?
      </button>
      {open && (
        <span className="absolute z-20 left-1/2 -translate-x-1/2 mt-2 w-64 bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm text-gray-700 normal-case font-normal">
          <span className="block mb-1">{text}</span>
          {learnMoreAnchor && (
            <Link
              to={`/methodology#${learnMoreAnchor}`}
              className="text-blue-600 hover:underline text-xs"
            >
              Learn more →
            </Link>
          )}
        </span>
      )}
    </span>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/InfoTooltip.tsx
git commit -m "feat(ui): add InfoTooltip shared component"
```

---

## Task 4: ConfirmDeleteModal shared component

**Files:**
- Create: `frontend/src/components/ConfirmDeleteModal.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ConfirmDeleteModal.tsx` with:

```tsx
interface Props {
  open: boolean;
  title?: string;
  message?: string;
  onCancel: () => void;
  onConfirm: () => void;
  confirmLabel?: string;
}

export default function ConfirmDeleteModal({
  open,
  title = "Delete this portfolio?",
  message = "This action cannot be undone. Your portfolio data and holdings will be permanently removed.",
  onCancel,
  onConfirm,
  confirmLabel = "Delete",
}: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-xl font-bold mb-2">{title}</h2>
        <p className="text-gray-600 mb-6">{message}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ConfirmDeleteModal.tsx
git commit -m "feat(ui): add ConfirmDeleteModal shared component"
```

---

## Task 5: PortfolioCard delete button

**Files:**
- Modify: `frontend/src/dashboard/PortfolioCard.tsx`
- Modify: `frontend/src/dashboard/DashboardPage.tsx`

- [ ] **Step 1: Update PortfolioCard to accept an `onDelete` callback and render the button**

Replace the entire contents of `frontend/src/dashboard/PortfolioCard.tsx` with:

```tsx
import { Link } from "react-router-dom";
import { MouseEvent } from "react";

interface Props {
  id: string;
  status: string;
  riskScore: number;
  expectedReturnLow: number;
  expectedReturnHigh: number;
  totalValue: number;
  createdAt: string;
  onDelete: (id: string) => void;
}

export default function PortfolioCard({
  id, status, riskScore, expectedReturnLow, expectedReturnHigh, totalValue, createdAt, onDelete,
}: Props) {
  const handleDeleteClick = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDelete(id);
  };

  return (
    <Link
      to={`/portfolio/${id}`}
      className="group relative block bg-white p-6 rounded-lg shadow hover:shadow-md transition-shadow"
    >
      <button
        type="button"
        onClick={handleDeleteClick}
        className="absolute top-3 right-3 w-8 h-8 rounded-full bg-gray-100 text-gray-500 hover:bg-red-100 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
        aria-label="Delete portfolio"
        title="Delete portfolio"
      >
        🗑️
      </button>
      <div className="flex justify-between items-start mb-3 pr-8">
        <span className="text-sm text-gray-400">{new Date(createdAt).toLocaleDateString()}</span>
        <span className={`text-xs px-2 py-1 rounded-full ${
          status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
        }`}>
          {status}
        </span>
      </div>
      <p className="text-2xl font-bold mb-1">${totalValue.toLocaleString()}</p>
      <p className="text-sm text-gray-600 mb-2">
        Expected: {expectedReturnLow}% — {expectedReturnHigh}% annual
      </p>
      <p className="text-sm text-gray-500">Risk score: {riskScore}%</p>
    </Link>
  );
}
```

- [ ] **Step 2: Wire up the delete flow in DashboardPage**

Replace the entire contents of `frontend/src/dashboard/DashboardPage.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { deletePortfolio } from "../api/client";
import PortfolioCard from "./PortfolioCard";
import Spinner from "../components/Spinner";
import ConfirmDeleteModal from "../components/ConfirmDeleteModal";

interface PortfolioItem {
  id: string;
  status: string;
  risk_score: number;
  expected_return_low: number;
  expected_return_high: number;
  total_value: number;
  created_at: string;
}

export default function DashboardPage() {
  const [portfolios, setPortfolios] = useState<PortfolioItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    api.get("/portfolios").then((resp) => {
      setPortfolios(resp.data);
      setLoading(false);
    });
  }, []);

  const handleDeleteConfirm = async () => {
    if (!deletingId) return;
    const id = deletingId;
    await deletePortfolio(id);
    setPortfolios((prev) => prev.filter((p) => p.id !== id));
    setDeletingId(null);
  };

  if (loading) return <Spinner />;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">My Portfolios</h1>
        <Link to="/profile/new" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          + New Portfolio
        </Link>
      </div>

      {portfolios.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-lg mb-4">No portfolios yet</p>
          <Link to="/profile/new" className="text-blue-600 hover:underline">
            Create your first portfolio
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {portfolios.map((p) => (
            <PortfolioCard
              key={p.id}
              id={p.id}
              status={p.status}
              riskScore={p.risk_score}
              expectedReturnLow={p.expected_return_low}
              expectedReturnHigh={p.expected_return_high}
              totalValue={p.total_value}
              createdAt={p.created_at}
              onDelete={setDeletingId}
            />
          ))}
        </div>
      )}

      <ConfirmDeleteModal
        open={!!deletingId}
        onCancel={() => setDeletingId(null)}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Manual browser verification**

Open `http://localhost:5173/dashboard`:
- Hover over a portfolio card → trash icon appears.
- Click trash icon → modal appears, does not navigate.
- Click Cancel → modal closes, card still there.
- Click Delete → modal closes, card removed from list.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/dashboard/PortfolioCard.tsx frontend/src/dashboard/DashboardPage.tsx
git commit -m "feat(dashboard): add delete button to portfolio cards"
```

---

## Task 6: RiskGauge component

**Files:**
- Create: `frontend/src/portfolio/RiskGauge.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/portfolio/RiskGauge.tsx`:

```tsx
import InfoTooltip from "../components/InfoTooltip";

interface Props {
  riskScore: number;
}

function classify(score: number): { label: string; level: number; color: string; bg: string } {
  if (score < 15) return { label: "Low risk", level: 1, color: "text-green-700", bg: "bg-green-500" };
  if (score < 25) return { label: "Medium-low risk", level: 2, color: "text-lime-700", bg: "bg-lime-500" };
  if (score < 35) return { label: "Medium risk", level: 3, color: "text-yellow-700", bg: "bg-yellow-500" };
  if (score < 50) return { label: "High risk", level: 4, color: "text-orange-700", bg: "bg-orange-500" };
  return { label: "Very high risk", level: 5, color: "text-red-700", bg: "bg-red-500" };
}

export default function RiskGauge({ riskScore }: Props) {
  const { label, level, color, bg } = classify(riskScore);

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-500">
          Risk Level
          <InfoTooltip
            text="How much your portfolio's value may swing up or down. Higher risk means bigger potential gains and losses."
            learnMoreAnchor="risk"
          />
        </h3>
        <span className="text-xs text-gray-400">{riskScore.toFixed(1)}% volatility</span>
      </div>
      <p className={`text-2xl font-bold mb-4 ${color}`}>{label}</p>
      <div className="flex gap-1.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <div
            key={n}
            className={`flex-1 h-2 rounded-full ${n <= level ? bg : "bg-gray-200"}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-2">
        <span>Safer</span>
        <span>Riskier</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/portfolio/RiskGauge.tsx
git commit -m "feat(portfolio): add RiskGauge component"
```

---

## Task 7: DiversificationCard component

**Files:**
- Create: `frontend/src/portfolio/DiversificationCard.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/portfolio/DiversificationCard.tsx`:

```tsx
import InfoTooltip from "../components/InfoTooltip";

interface Holding {
  sector: string;
}

interface Props {
  holdings: Holding[];
}

export default function DiversificationCard({ holdings }: Props) {
  const sectorCount = new Set(holdings.map((h) => h.sector)).size;
  const stockCount = holdings.length;
  const good = sectorCount >= 3 && stockCount >= 5;

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-500">
          Diversification
          <InfoTooltip
            text="Spreading your money across many stocks and sectors reduces the impact of any single one performing badly."
            learnMoreAnchor="optimization"
          />
        </h3>
        <span className={`text-xs px-2 py-0.5 rounded-full ${good ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
          {good ? "Well diversified" : "Limited"}
        </span>
      </div>
      <p className="text-2xl font-bold mb-1 text-gray-900">{stockCount} stocks</p>
      <p className="text-sm text-gray-600">across {sectorCount} sector{sectorCount === 1 ? "" : "s"}</p>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/portfolio/DiversificationCard.tsx
git commit -m "feat(portfolio): add DiversificationCard component"
```

---

## Task 8: HeroScenarioCard component

**Files:**
- Create: `frontend/src/portfolio/HeroScenarioCard.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/portfolio/HeroScenarioCard.tsx`:

```tsx
import InfoTooltip from "../components/InfoTooltip";

interface Props {
  initialValue: number;
  horizonYears: number;
  percentile10: number;
  percentile50: number;
  percentile90: number;
  nSimulations: number;
}

function formatMoney(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

function formatYears(y: number): string {
  if (y < 1) return `${Math.round(y * 12)} months`;
  if (y === Math.round(y)) return `${y} year${y === 1 ? "" : "s"}`;
  return `${y.toFixed(1)} years`;
}

export default function HeroScenarioCard({
  initialValue, horizonYears, percentile10, percentile50, percentile90, nSimulations,
}: Props) {
  const unavailable = horizonYears <= 0 || nSimulations <= 0;

  if (unavailable) {
    return (
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-8 rounded-2xl shadow border border-blue-100">
        <p className="text-gray-600 text-center">
          Simulation data is not available for this portfolio.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-8 rounded-2xl shadow-lg text-white">
      <p className="text-blue-100 text-sm mb-2">
        If you invest {formatMoney(initialValue)} today
      </p>
      <p className="text-2xl md:text-3xl font-bold mb-4 leading-snug">
        in {formatYears(horizonYears)} you could have between{" "}
        <span className="text-white">{formatMoney(percentile10)}</span> and{" "}
        <span className="text-white">{formatMoney(percentile90)}</span>.
      </p>
      <p className="text-blue-100">
        Most likely around <span className="font-bold text-white">{formatMoney(percentile50)}</span>.
      </p>
      <div className="mt-6 pt-4 border-t border-white/20 flex items-center justify-between text-xs text-blue-100">
        <span>Based on {nSimulations.toLocaleString()} simulated paths</span>
        <InfoTooltip
          text="We run thousands of randomized future scenarios to estimate a range of possible outcomes. This is not a prediction — it's a distribution of what could happen."
          learnMoreAnchor="simulation"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/portfolio/HeroScenarioCard.tsx
git commit -m "feat(portfolio): add HeroScenarioCard component"
```

---

## Task 9: ScenarioGrid component

**Files:**
- Create: `frontend/src/portfolio/ScenarioGrid.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/portfolio/ScenarioGrid.tsx`:

```tsx
import InfoTooltip from "../components/InfoTooltip";

interface Props {
  initialValue: number;
  percentile10: number;
  percentile50: number;
  percentile90: number;
  horizonYears: number;
}

function formatMoney(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

export default function ScenarioGrid({
  initialValue, percentile10, percentile50, percentile90, horizonYears,
}: Props) {
  if (horizonYears <= 0) return null;

  const scenarios = [
    {
      label: "Bad years",
      likelihood: "10% chance",
      value: percentile10,
      icon: "📉",
      bg: "bg-red-50",
      border: "border-red-200",
      text: "text-red-700",
      valueText: "text-red-900",
    },
    {
      label: "Typical scenario",
      likelihood: "most likely",
      value: percentile50,
      icon: "📊",
      bg: "bg-blue-50",
      border: "border-blue-200",
      text: "text-blue-700",
      valueText: "text-blue-900",
    },
    {
      label: "Good years",
      likelihood: "10% chance",
      value: percentile90,
      icon: "📈",
      bg: "bg-green-50",
      border: "border-green-200",
      text: "text-green-700",
      valueText: "text-green-900",
    },
  ];

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <div className="flex items-center mb-4">
        <h2 className="text-lg font-semibold">Future Scenarios</h2>
        <InfoTooltip
          text="We split the simulated outcomes into three buckets: the worst 10%, the middle (most likely), and the best 10%. Real outcomes will almost certainly fall somewhere in this range."
          learnMoreAnchor="simulation"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {scenarios.map((s) => (
          <div key={s.label} className={`${s.bg} ${s.border} border rounded-xl p-4`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xl">{s.icon}</span>
              <span className={`text-xs ${s.text}`}>{s.likelihood}</span>
            </div>
            <p className={`text-sm font-medium ${s.text}`}>{s.label}</p>
            <p className={`text-2xl font-bold ${s.valueText} mt-1`}>{formatMoney(s.value)}</p>
            <p className="text-xs text-gray-500 mt-1">
              from {formatMoney(initialValue)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/portfolio/ScenarioGrid.tsx
git commit -m "feat(portfolio): add ScenarioGrid component"
```

---

## Task 10: Sort holdings in HoldingsTable and AllocationChart

**Files:**
- Modify: `frontend/src/portfolio/HoldingsTable.tsx`
- Modify: `frontend/src/portfolio/AllocationChart.tsx`

These components will receive sorted holdings from `PortfolioPage`, but to make them self-protective (YAGNI balance: a one-line guard is cheap insurance), we sort inside too.

- [ ] **Step 1: Update HoldingsTable to sort its input**

Replace the body of `HoldingsTable` in `frontend/src/portfolio/HoldingsTable.tsx`:

```tsx
import InfoTooltip from "../components/InfoTooltip";

interface Holding {
  ticker: string;
  company_name: string;
  sector: string;
  allocation_pct: number;
  expected_return: number;
}

export default function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  const sorted = [...holdings].sort((a, b) => b.allocation_pct - a.allocation_pct);

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <h2 className="text-lg font-semibold mb-4">Your Stocks</h2>
      <table className="w-full text-left">
        <thead>
          <tr className="border-b text-sm text-gray-500">
            <th className="py-2">Ticker</th>
            <th>Company</th>
            <th>Sector</th>
            <th className="text-right">
              Allocation
              <InfoTooltip text="What percentage of your total investment goes into this stock." />
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((h) => (
            <tr key={h.ticker} className="border-b hover:bg-gray-50">
              <td className="py-3 font-mono font-bold">{h.ticker}</td>
              <td>{h.company_name}</td>
              <td className="text-sm text-gray-600">{h.sector}</td>
              <td className="text-right font-semibold">{h.allocation_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

Note: the `expected_return` column is dropped — per the spec we don't surface the raw predictor value on the beginner page. The column would confuse (e.g., 100% numbers) without value to a beginner.

- [ ] **Step 2: Update AllocationChart to sort its input**

Replace `frontend/src/portfolio/AllocationChart.tsx`:

```tsx
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface Holding {
  ticker: string;
  company_name: string;
  allocation_pct: number;
}

const COLORS = ["#2563eb", "#7c3aed", "#059669", "#d97706", "#dc2626", "#0891b2", "#4f46e5", "#be123c"];

export default function AllocationChart({ holdings }: { holdings: Holding[] }) {
  const sorted = [...holdings].sort((a, b) => b.allocation_pct - a.allocation_pct);
  const data = sorted.map((h) => ({
    name: `${h.ticker} (${h.allocation_pct.toFixed(1)}%)`,
    value: h.allocation_pct,
  }));

  return (
    <div className="bg-white p-6 rounded-xl shadow">
      <h2 className="text-lg font-semibold mb-4">What You Own</h2>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/portfolio/HoldingsTable.tsx frontend/src/portfolio/AllocationChart.tsx
git commit -m "refactor(portfolio): sort holdings by allocation desc, clean up tables"
```

---

## Task 11: MethodologyPage + route + nav link

**Files:**
- Create: `frontend/src/methodology/MethodologyPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Create the methodology page**

Create `frontend/src/methodology/MethodologyPage.tsx`:

```tsx
export default function MethodologyPage() {
  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">How We Build Your Portfolio</h1>
      <p className="text-gray-600 mb-8">
        A plain-English walk-through of what happens when you click "Generate Portfolio".
      </p>

      <section id="overview" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">The Big Picture</h2>
        <p className="text-gray-700 mb-4">
          When you submit your profile, we run a four-step pipeline to build a portfolio tailored to your goals:
        </p>
        <ol className="list-decimal list-inside space-y-2 text-gray-700">
          <li><strong>Choose stocks</strong> that match your country and preferred sectors.</li>
          <li><strong>Estimate future returns</strong> for each stock using historical data.</li>
          <li><strong>Balance the portfolio</strong> to match your risk tolerance.</li>
          <li><strong>Simulate the future</strong> to show you a range of possible outcomes.</li>
        </ol>
      </section>

      <section id="stocks" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Choosing Stocks</h2>
        <p className="text-gray-700">
          We start with a universe of well-known, liquid companies listed on major exchanges in your selected country.
          From that pool, we focus on the sectors you're interested in — Technology, Healthcare, and so on.
          You can also add specific tickers you want included, or exclude any you'd rather avoid.
        </p>
      </section>

      <section id="prediction" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Estimating Future Returns</h2>
        <p className="text-gray-700 mb-3">
          For each candidate stock, we look at its historical price behavior and apply a machine-learning
          approach to estimate how it may perform over the coming weeks. These per-stock estimates feed
          the next step.
        </p>
        <p className="text-sm text-gray-500 italic">
          An estimate is not a promise — it's a quantitative guess based on patterns in past data.
        </p>
      </section>

      <section id="optimization" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Balancing the Portfolio</h2>
        <p className="text-gray-700 mb-3">
          Once we have per-stock estimates, we solve an optimization problem: how much of each stock
          should you hold to get the best expected return at your chosen risk level?
        </p>
        <p className="text-gray-700 mb-3">
          This is based on a well-established technique called <strong>mean-variance optimization</strong>.
          The intuition: don't put all your eggs in one basket. Spreading across multiple stocks and
          sectors reduces the damage any single bad pick can cause.
        </p>
      </section>

      <section id="risk" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">About Risk</h2>
        <p className="text-gray-700">
          A portfolio's risk is roughly how much its value tends to swing up and down. Higher-risk
          portfolios can grow faster — but can also fall harder in bad periods. The risk level you pick
          controls how aggressive the optimizer is allowed to be.
        </p>
      </section>

      <section id="simulation" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Simulating the Future</h2>
        <p className="text-gray-700 mb-3">
          Once the portfolio is built, we run a <strong>Monte Carlo simulation</strong>: we generate
          thousands of randomized future scenarios using the portfolio's estimated return and risk
          characteristics. Each simulation produces one possible ending value.
        </p>
        <p className="text-gray-700 mb-3">
          From those thousands of scenarios we pull out three headline numbers:
        </p>
        <ul className="list-disc list-inside space-y-1 text-gray-700">
          <li><strong>10th percentile</strong> — only 10% of simulated scenarios ended up worse than this.</li>
          <li><strong>50th percentile</strong> — the middle of the pack; half the scenarios did better, half worse.</li>
          <li><strong>90th percentile</strong> — only 10% of simulated scenarios ended up better than this.</li>
        </ul>
      </section>

      <section className="bg-yellow-50 border-2 border-yellow-200 p-6 rounded-xl mb-6">
        <h2 className="text-2xl font-bold mb-3 text-yellow-900">⚠️ Important Limitations</h2>
        <ul className="list-disc list-inside space-y-2 text-yellow-900">
          <li>Past performance is not a reliable indicator of future results.</li>
          <li>Our estimates can be wrong. Markets frequently behave in unexpected ways.</li>
          <li>This tool is for educational and exploratory purposes — it is not financial advice.</li>
          <li>Always consult a licensed financial advisor before making real investment decisions.</li>
        </ul>
      </section>

      <section id="glossary" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Glossary</h2>
        <dl className="space-y-3 text-gray-700">
          <div><dt className="font-semibold">Risk Score</dt><dd>A measure of how volatile your portfolio's value is. Higher = bigger swings.</dd></div>
          <div><dt className="font-semibold">Allocation</dt><dd>The percentage of your total investment placed in a specific stock.</dd></div>
          <div><dt className="font-semibold">Sector</dt><dd>A broad category of businesses (Technology, Healthcare, Energy, etc.).</dd></div>
          <div><dt className="font-semibold">Diversification</dt><dd>Spreading investments across many positions to reduce risk from any one going wrong.</dd></div>
          <div><dt className="font-semibold">Percentile</dt><dd>A point in a ranked distribution. The 10th percentile is the value below which 10% of outcomes fall.</dd></div>
          <div><dt className="font-semibold">Monte Carlo Simulation</dt><dd>A technique that uses thousands of random samples to estimate a range of possible outcomes.</dd></div>
          <div><dt className="font-semibold">Horizon</dt><dd>How long you plan to keep the investment before withdrawing.</dd></div>
        </dl>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Add the route in App.tsx**

Replace the entire contents of `frontend/src/App.tsx` with:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import LoginPage from "./auth/LoginPage";
import RegisterPage from "./auth/RegisterPage";
import Layout from "./components/Layout";
import DashboardPage from "./dashboard/DashboardPage";
import ProfileForm from "./profile/ProfileForm";
import PortfolioPage from "./portfolio/PortfolioPage";
import MethodologyPage from "./methodology/MethodologyPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/dashboard" element={
            <ProtectedRoute><Layout><DashboardPage /></Layout></ProtectedRoute>
          } />
          <Route path="/profile/new" element={
            <ProtectedRoute><Layout><ProfileForm /></Layout></ProtectedRoute>
          } />
          <Route path="/portfolio/:id" element={
            <ProtectedRoute><Layout><PortfolioPage /></Layout></ProtectedRoute>
          } />
          <Route path="/methodology" element={
            <ProtectedRoute><Layout><MethodologyPage /></Layout></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Add nav link in Layout.tsx**

Replace the entire contents of `frontend/src/components/Layout.tsx` with:

```tsx
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-6xl mx-auto px-4 py-3 flex justify-between items-center">
          <Link to="/dashboard" className="text-xl font-bold text-blue-600">
            Portfolio Builder
          </Link>
          <div className="flex gap-4 items-center">
            <Link to="/dashboard" className="text-gray-600 hover:text-gray-900">Dashboard</Link>
            <Link to="/profile/new" className="text-gray-600 hover:text-gray-900">New Portfolio</Link>
            <Link to="/methodology" className="text-gray-600 hover:text-gray-900">How it works</Link>
            <button onClick={handleLogout} className="text-gray-600 hover:text-gray-900">Logout</button>
          </div>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto px-4 py-8">
        {children}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Manual browser verification**

Open `http://localhost:5173/methodology`:
- Page renders all sections.
- Nav bar shows "How it works" link; clicking it loads the page.
- All anchors (`#overview`, `#stocks`, `#prediction`, `#optimization`, `#risk`, `#simulation`, `#glossary`) exist.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/methodology/MethodologyPage.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "feat(methodology): add /methodology page, route, and nav link"
```

---

## Task 12: PortfolioPage redesign and cleanup

**Files:**
- Modify: `frontend/src/portfolio/PortfolioPage.tsx`
- Delete: `frontend/src/portfolio/RiskComparison.tsx`
- Delete: `frontend/src/portfolio/BacktestChart.tsx`
- Delete: `frontend/src/portfolio/MonteCarloChart.tsx`

- [ ] **Step 1: Replace PortfolioPage with the new layout**

Replace the entire contents of `frontend/src/portfolio/PortfolioPage.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import api, { deletePortfolio, archivePortfolio } from "../api/client";
import Spinner from "../components/Spinner";
import ConfirmDeleteModal from "../components/ConfirmDeleteModal";
import DisclaimerBanner from "./DisclaimerBanner";
import AllocationChart from "./AllocationChart";
import HoldingsTable from "./HoldingsTable";
import HeroScenarioCard from "./HeroScenarioCard";
import RiskGauge from "./RiskGauge";
import DiversificationCard from "./DiversificationCard";
import ScenarioGrid from "./ScenarioGrid";

interface PortfolioData {
  id: string;
  status: string;
  risk_score: number;
  expected_return_low: number;
  expected_return_high: number;
  portfolio_return: number;
  total_value: number;
  holdings: Array<{
    ticker: string;
    company_name: string;
    sector: string;
    allocation_pct: number;
    expected_return: number;
  }>;
  simulation: {
    percentile_10: number;
    percentile_50: number;
    percentile_90: number;
    return_low: number;
    return_high: number;
    initial_value: number;
    horizon_years: number;
    n_simulations: number;
  };
}

export default function PortfolioPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    api.get(`/portfolios/${id}`).then((resp) => {
      setPortfolio(resp.data);
      setLoading(false);
    });
  }, [id]);

  if (loading || !portfolio) return <Spinner />;

  const sortedHoldings = [...portfolio.holdings].sort((a, b) => b.allocation_pct - a.allocation_pct);

  const handleArchive = async () => {
    if (!id) return;
    await archivePortfolio(id);
    navigate("/dashboard");
  };

  const handleDelete = async () => {
    if (!id) return;
    await deletePortfolio(id);
    navigate("/dashboard");
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <Link to="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
          ← Back to Dashboard
        </Link>
        <div className="flex gap-2">
          <button
            onClick={handleArchive}
            className="px-3 py-1.5 text-sm rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700"
          >
            Archive
          </button>
          <button
            onClick={() => setConfirmDelete(true)}
            className="px-3 py-1.5 text-sm rounded-lg bg-red-50 hover:bg-red-100 text-red-700"
          >
            Delete
          </button>
        </div>
      </div>

      <DisclaimerBanner />

      <HeroScenarioCard
        initialValue={portfolio.simulation.initial_value}
        horizonYears={portfolio.simulation.horizon_years}
        percentile10={portfolio.simulation.percentile_10}
        percentile50={portfolio.simulation.percentile_50}
        percentile90={portfolio.simulation.percentile_90}
        nSimulations={portfolio.simulation.n_simulations}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <RiskGauge riskScore={portfolio.risk_score} />
        <DiversificationCard holdings={sortedHoldings} />
      </div>

      <AllocationChart holdings={sortedHoldings} />

      <HoldingsTable holdings={sortedHoldings} />

      <ScenarioGrid
        initialValue={portfolio.simulation.initial_value}
        percentile10={portfolio.simulation.percentile_10}
        percentile50={portfolio.simulation.percentile_50}
        percentile90={portfolio.simulation.percentile_90}
        horizonYears={portfolio.simulation.horizon_years}
      />

      <div className="bg-blue-50 border border-blue-100 p-6 rounded-xl text-center">
        <p className="text-gray-700 mb-3">
          📚 Want to know how we calculated this?
        </p>
        <Link
          to="/methodology"
          className="inline-block px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
        >
          Read the full methodology →
        </Link>
      </div>

      <ConfirmDeleteModal
        open={confirmDelete}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={handleDelete}
      />
    </div>
  );
}
```

- [ ] **Step 2: Delete the deprecated components**

```bash
rm frontend/src/portfolio/RiskComparison.tsx frontend/src/portfolio/BacktestChart.tsx frontend/src/portfolio/MonteCarloChart.tsx
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Manual browser verification**

1. Navigate to an existing portfolio's page (`/portfolio/<id>`).
2. Verify the new layout: back link, archive/delete buttons, disclaimer, hero card, risk+diversification row, pie chart, holdings table (sorted by allocation desc), scenario grid, methodology CTA.
3. Hover over any "?" icon → tooltip appears with clear text.
4. Click "Learn more →" in a tooltip → lands on `/methodology` at the right anchor.
5. Click "Archive" → returns to dashboard, portfolio shown as archived.
6. Create a fresh portfolio, then click "Delete" → modal appears → confirm → redirected to dashboard, portfolio gone.
7. On dashboard: hover a card → trash icon → click → modal → confirm → card removed.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src/portfolio/
git commit -m "feat(portfolio): redesign portfolio page for beginners, remove deprecated components"
```

---

## Task 13: End-to-end verification

- [ ] **Step 1: Run backend test suite**

```bash
docker compose run --rm backend pytest -v --tb=short
```

Expected: all tests pass (including the three new delete tests).

- [ ] **Step 2: Run frontend TypeScript compiler + linter**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Expected: no type errors, no lint errors.

- [ ] **Step 3: Manual full-flow smoke test**

1. Register a new account.
2. Create a portfolio (1 sector) — verify generating overlay appears, result page shows new layout with sensible numbers.
3. Verify holdings are sorted by allocation descending in both the pie chart legend and the table.
4. Visit `/methodology` via nav link — verify all sections render.
5. Click "Learn more" in a portfolio-page tooltip — verify anchor navigation works.
6. Archive the portfolio — verify dashboard updates.
7. Create another portfolio — delete it via the portfolio page — verify it's gone from dashboard.
8. Create another — delete it via the dashboard card's trash icon — verify it's gone.

- [ ] **Step 4: Final commit (if any loose ends)**

If any fixes were needed:

```bash
git add -A
git commit -m "chore: final polish from e2e verification"
```

---

## Done

All three features delivered:
1. ✅ Delete portfolios from dashboard cards and portfolio page
2. ✅ Redesigned beginner-friendly portfolio page with plain-English framing, sorted holdings, hero scenario card, risk gauge, diversification card, and scenario grid
3. ✅ `/methodology` page with high-level explanations, tooltip deep-links, nav integration, and prominent limitations section
