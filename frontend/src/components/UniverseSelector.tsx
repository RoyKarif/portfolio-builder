// List of curated ETFs as checkboxes + "add custom ticker" input.
// Output: a list of selected tickers.

import { useState } from "react";
import type { Asset } from "../types/api";

interface Props {
  universe: Asset[];
  selected: string[];
  onChange: (tickers: string[]) => void;
}

export function UniverseSelector({ universe, selected, onChange }: Props) {
  const [customTicker, setCustomTicker] = useState("");
  const selectedSet = new Set(selected);

  const toggle = (ticker: string) => {
    const next = new Set(selectedSet);
    if (next.has(ticker)) next.delete(ticker);
    else next.add(ticker);
    onChange(Array.from(next));
  };

  const addCustom = () => {
    const t = customTicker.trim().toUpperCase();
    if (!t || selectedSet.has(t)) return;
    onChange([...selected, t]);
    setCustomTicker("");
  };

  // Group by asset_class for visual organization.
  const grouped = universe.reduce<Record<string, Asset[]>>((acc, a) => {
    (acc[a.asset_class] ??= []).push(a);
    return acc;
  }, {});

  // Custom tickers (not in universe but in `selected`).
  const customs = selected.filter(
    (t) => !universe.some((a) => a.ticker === t),
  );

  return (
    <div>
      <label className="block text-sm font-medium mb-2">בחירת נכסים</label>

      {Object.entries(grouped).map(([cls, assets]) => (
        <div key={cls} className="mb-3">
          <div className="text-xs uppercase text-gray-500 mb-1">{cls}</div>
          <div className="grid grid-cols-2 gap-2">
            {assets.map((a) => (
              <label
                key={a.ticker}
                className="flex items-center space-x-2 space-x-reverse text-sm"
              >
                <input
                  type="checkbox"
                  checked={selectedSet.has(a.ticker)}
                  onChange={() => toggle(a.ticker)}
                />
                <span className="font-mono font-bold">{a.ticker}</span>
                <span className="text-gray-600 truncate">{a.name}</span>
              </label>
            ))}
          </div>
        </div>
      ))}

      {customs.length > 0 && (
        <div className="mb-3">
          <div className="text-xs uppercase text-gray-500 mb-1">מותאמים</div>
          <div className="flex flex-wrap gap-2">
            {customs.map((t) => (
              <span
                key={t}
                className="bg-blue-100 px-2 py-1 rounded text-sm flex items-center space-x-1 space-x-reverse"
              >
                <span className="font-mono">{t}</span>
                <button
                  type="button"
                  onClick={() => toggle(t)}
                  className="text-blue-700 hover:text-red-600"
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex space-x-2 space-x-reverse">
        <input
          type="text"
          placeholder="הוסף ticker (למשל TSLA)"
          value={customTicker}
          onChange={(e) => setCustomTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustom())}
          className="flex-1 border rounded px-2 py-1 text-sm"
        />
        <button
          type="button"
          onClick={addCustom}
          className="bg-gray-200 px-3 py-1 rounded text-sm hover:bg-gray-300"
        >
          הוסף
        </button>
      </div>
    </div>
  );
}
