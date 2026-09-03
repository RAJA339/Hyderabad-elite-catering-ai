import type { MarketSnapshot } from "@/lib/api";
import { rupees } from "@/lib/format";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingDown, TrendingUp } from "lucide-react";

/** "Today's Hyderabad Market Price vs Our Price" — shown on every quote. */
export function MarketWidget({ snap }: { snap: MarketSnapshot | null }) {
  if (!snap) return null;
  return (
    <Card className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <CardTitle>Today’s Hyderabad market vs our price</CardTitle>
          <p className="mt-1 text-xs text-muted">Wholesale rates from Bowenpally / Rythu Bazar{snap.as_of ? ` · ${snap.as_of}` : ""}</p>
        </div>
        <Badge tone="good">You save {rupees(snap.you_save_vs_benchmark)}/plate</Badge>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div><span className="label">Our price</span><div className="text-xl font-semibold tabular-nums">{rupees(snap.our_per_plate)}</div></div>
        <div><span className="label">Market benchmark</span><div className="text-xl font-semibold tabular-nums text-muted line-through decoration-muted/60">{rupees(snap.market_benchmark_per_plate)}</div></div>
        <div><span className="label">Food cost transparency</span><div className="text-xl font-semibold tabular-nums">{rupees(snap.our_cost_per_plate)}</div></div>
      </div>
      <ul className="divide-y divide-line text-sm">
        {snap.ingredients.map((i) => {
          const ch = Number(i.change_7d_pct);
          return (
            <li key={i.key} className="flex items-center justify-between py-2">
              <span>{i.name} <span className="text-muted">/ {i.unit}</span></span>
              <span className="flex items-center gap-3 tabular-nums">
                <span>{rupees(i.wholesale)}</span>
                <span className={ch > 0 ? "flex items-center gap-1 text-warn" : ch < 0 ? "flex items-center gap-1 text-good" : "text-muted"}>
                  {ch > 0 ? <TrendingUp size={12} /> : ch < 0 ? <TrendingDown size={12} /> : null}{ch > 0 ? "+" : ""}{ch.toFixed(0)}%
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      {snap.notes.length > 0 && <p className="text-xs text-muted">{snap.notes[0]}</p>}
    </Card>
  );
}
