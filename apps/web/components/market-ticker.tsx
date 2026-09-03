"use client";
import { useEffect, useState } from "react";
import { API } from "@/lib/api";

type Row = { key: string; name: string; unit: string; price: string; change_7d: number };

// Shown until the API answers, so the strip never renders empty.
const FALLBACK: Row[] = [
  { key: "chicken", name: "Chicken", unit: "kg", price: "232", change_7d: 16 },
  { key: "mutton", name: "Mutton", unit: "kg", price: "760", change_7d: 0 },
  { key: "paneer", name: "Paneer", unit: "kg", price: "360", change_7d: 0 },
  { key: "onion", name: "Onion", unit: "kg", price: "32", change_7d: 25 },
  { key: "tomato", name: "Tomato", unit: "kg", price: "28", change_7d: -7 },
  { key: "rice", name: "Basmati", unit: "kg", price: "95", change_7d: 0 },
  { key: "oil", name: "Refined oil", unit: "l", price: "128", change_7d: 0 },
  { key: "milk", name: "Milk", unit: "l", price: "56", change_7d: 0 },
];

export function MarketTicker() {
  const [rows, setRows] = useState<Row[]>(FALLBACK);
  const [asOf, setAsOf] = useState<string | null>(null);
  useEffect(() => {
    fetch(`${API}/api/public/market-ticker`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d?.prices?.length) { setRows(d.prices); setAsOf(d.as_of); } })
      .catch(() => {});
  }, []);
  const items = [...rows, ...rows]; // doubled for a seamless loop
  return (
    <div className="relative overflow-hidden border-y border-line/70 bg-bg-2/60">
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-bg to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-bg to-transparent" />
      <div className="flex items-center">
        <div className="z-20 flex shrink-0 items-center gap-2 border-r border-line/70 bg-bg px-4 py-2.5 text-[11px] font-medium uppercase tracking-[0.14em] text-muted">
          <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-good" />
          Bowenpally wholesale{asOf ? " · today" : ""}
        </div>
        <div className="marquee flex w-max items-center gap-8 whitespace-nowrap py-2.5 pl-8 text-[13px]">
          {items.map((r, i) => {
            const up = r.change_7d > 0, down = r.change_7d < 0;
            return (
              <span key={`${r.key}-${i}`} className="flex items-center gap-2 tabular-nums">
                <span className="text-muted">{r.name}</span>
                <span className="font-semibold">₹{Number(r.price).toLocaleString("en-IN")}<span className="text-muted">/{r.unit}</span></span>
                <span className={up ? "text-warn" : down ? "text-good" : "text-muted"}>{up ? "▲" : down ? "▼" : "•"} {Math.abs(r.change_7d).toFixed(0)}%</span>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
