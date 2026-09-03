"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { rupees, pct, titleCase } from "@/lib/format";
import { Card, CardTitle, Stat } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageTitle } from "@/components/admin-shell";
import { Meter } from "@/components/charts";

type Cost = { slug: string; name: string; category: string; diet: string; food_cost_per_guest: string; total_cost_per_guest: string; suggested_price_per_guest: string; market_retail_equiv_per_guest: string | null; cost_change_7d_pct: string; computed_at: string };
type Price = { key: string; name: string; unit: string; market: string; price_per_unit: string; observed_at: string; source: string };

export default function Pricing() {
  const [costs, setCosts] = useState<Cost[]>([]);
  const [prices, setPrices] = useState<Price[]>([]);
  const [csv, setCsv] = useState("ingredient_key,market,price_per_unit\nchicken,wholesale,");
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => { api<{ items: Cost[] }>("/api/pricing/costs").then((r) => setCosts(r.items)).catch(() => {}); api<{ prices: Price[] }>("/api/pricing/market").then((r) => setPrices(r.prices)).catch(() => {}); };
  useEffect(() => { load(); }, []);
  const margin = (c: Cost) => ((Number(c.suggested_price_per_guest) - Number(c.total_cost_per_guest)) / Number(c.suggested_price_per_guest)) * 100;
  const avg = costs.length ? costs.reduce((a, c) => a + margin(c), 0) / costs.length : 0;
  const spiking = costs.filter((c) => Number(c.cost_change_7d_pct) >= 12);
  async function ingest() { setMsg(null); try { const r = await api<{ written: number; alerts: unknown[] }>("/api/pricing/ingest", { method: "POST", body: JSON.stringify({ csv, source_label: "admin_manual" }) }); setMsg(`Saved ${r.written} prices, ${r.alerts.length} alerts. Costs recomputed.`); load(); } catch (e) { setMsg((e as Error).message); } }
  const wholesale = prices.filter((p) => p.market === "wholesale");
  return (
    <>
      <PageTitle title="Pricing & margin health" sub="Food cost vs selling price per item, recomputed after every market ingestion." />
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="Avg item margin" value={pct(avg)} tone={avg < 32 ? "bad" : avg < 40 ? "warn" : "good"} hint={<Meter value={avg} floor={32} target={40} className="mt-1" />} />
        <Stat label="Items with cost spike ≥12%" value={spiking.length} tone={spiking.length ? "warn" : "good"} hint={spiking.slice(0, 3).map((c) => c.name).join(", ") || "Stable week"} />
        <Stat label="Ingredients tracked" value={wholesale.length} hint={wholesale[0] ? `Latest ${new Date(wholesale[0].observed_at).toLocaleString("en-IN")}` : ""} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
        <Card className="overflow-x-auto p-0">
          <div className="px-5 py-4"><CardTitle>Menu item costing</CardTitle></div>
          <table className="w-full text-sm">
            <thead className="border-y border-line text-left"><tr className="label">{["Item", "Category", "Food cost", "Total cost", "Our price", "Margin", "7d Δ"].map((h) => <th key={h} className="px-4 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {costs.map((c) => { const m = margin(c); const ch = Number(c.cost_change_7d_pct); return (
                <tr key={c.slug} className="hover:bg-line/30">
                  <td className="px-4 py-2 font-medium">{c.name} <span className="text-[10px] text-muted">{c.diet}</span></td>
                  <td className="px-4 py-2 text-muted">{titleCase(c.category)}</td>
                  <td className="px-4 py-2 tabular-nums">{rupees(c.food_cost_per_guest, true)}</td><td className="px-4 py-2 tabular-nums">{rupees(c.total_cost_per_guest, true)}</td>
                  <td className="px-4 py-2 tabular-nums font-medium">{rupees(c.suggested_price_per_guest)}</td>
                  <td className="px-4 py-2"><Badge tone={m < 32 ? "bad" : m < 40 ? "warn" : "good"}>{pct(m, 0)}</Badge></td>
                  <td className="px-4 py-2"><span className={ch >= 12 ? "text-warn" : ch <= -5 ? "text-good" : "text-muted"}>{ch > 0 ? "+" : ""}{ch.toFixed(1)}%</span></td>
                </tr>); })}
            </tbody>
          </table>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardTitle>Today’s wholesale (Bowenpally)</CardTitle>
            <ul className="scroll-thin mt-3 max-h-80 divide-y divide-line overflow-y-auto text-sm">
              {wholesale.map((p) => <li key={p.key} className="flex justify-between py-1.5"><span>{p.name}</span><span className="tabular-nums">{rupees(p.price_per_unit)}<span className="text-muted">/{p.unit}</span></span></li>)}
            </ul>
          </Card>
          <Card>
            <CardTitle>Ingest supplier prices (CSV)</CardTitle>
            <textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={6} className="hairline mt-3 w-full rounded-xl bg-bg p-3 font-mono text-xs outline-none" />
            <div className="mt-2 flex items-center justify-between"><span className="text-xs text-muted">{msg}</span><Button size="sm" onClick={ingest}>Ingest & recompute</Button></div>
          </Card>
        </div>
      </div>
    </>
  );
}
