"use client";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { rupees, titleCase } from "@/lib/format";
import { Bars, ChartCard, StatTile, LineChart, ColumnChart, StackedBar, Funnel, CalendarHeat, fmtCompact, fmtNum, fmtPct } from "@/components/charts";
import { PageTitle } from "@/components/admin-shell";

export type Analytics = {
  days: number;
  series: { day: string; leads: number; wa: number; web: number; quotes: number; booked_value: number; paid_value: number; avg_margin: number | null; p50_latency_ms: number | null }[];
  totals: Totals; prev_totals: Totals;
  funnel: { name: string; value: number }[];
  tiers: { tier: string; quotes: number; booked: number; avg_per_plate: number | null; avg_margin: number | null; value: number }[];
  occasions: { occasion: string; leads: number; value: number }[];
  guest_bands: { band: string; quotes: number; avg_per_plate: number | null; avg_margin: number | null }[];
  margin_hist: { bucket: string; n: number }[];
  kitchen: { day: string; committed: number; capacity: number; bookings: number }[];
  response: { p50_ms: number | null; p95_ms: number | null; tokens_in: number; tokens_out: number; replies: number; handoff_rate: number | null };
  cost_movers: { name: string; unit: string; price: number; change_7d: number }[];
  close_probability: { bucket: string; n: number }[];
};
type Totals = { leads: number; quotes: number; booked_value: number; paid_value: number; avg_margin: number | null; conversion_pct: number | null; avg_per_plate: number | null; escalations: number; repeat_pct: number | null };

const RANGES = [7, 30, 90] as const;
const delta = (a: number | null | undefined, b: number | null | undefined) => (a == null || b == null || b === 0 ? null : ((a - b) / Math.abs(b)) * 100);
const dayLabel = (d: string) => new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

export function InsightsView({ data, days, onRange, loading }: { data: Analytics; days: number; onRange: (d: number) => void; loading?: boolean }) {
  const t = data.totals, p = data.prev_totals;
  const labels = data.series.map((s) => dayLabel(s.day));
  const empty = t.leads === 0 && t.quotes === 0;
  return (
    <>
      <PageTitle title="Insights" sub="Where the money comes from, where it leaks, and what Anvi is doing about it."
        right={
          <div className="hairline inline-flex items-center gap-0.5 rounded-full bg-card p-0.5" role="group" aria-label="Date range">
            {RANGES.map((r) => (
              <button key={r} type="button" onClick={() => onRange(r)} aria-pressed={days === r}
                      className={cn("inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-colors", days === r ? "bg-fg text-bg" : "text-muted hover:bg-line/50 hover:text-fg")}>
                {days === r && <Check size={12} strokeWidth={3} />} Last {r} days
              </button>
            ))}
          </div>
        } />

      {empty && (
        <div className="card mb-4 flex items-center justify-between gap-4 p-5 text-sm">
          <div><div className="font-medium">Nothing in this range yet</div><div className="text-muted">Every chart fills in as leads, quotes and payments come through Anvi. Try a longer range, or send yourself a test enquiry from the site.</div></div>
        </div>
      )}

      {/* KPI row */}
      <div className={cn("grid gap-4 md:grid-cols-2 xl:grid-cols-4 transition-opacity", loading && "opacity-50")}>
        <StatTile label="Booked value" value={fmtCompact(t.booked_value)} delta={delta(t.booked_value, p.booked_value)} spark={data.series.map((s) => s.booked_value)} hint="no previous period" />
        <StatTile label="New leads" value={fmtNum(t.leads)} delta={delta(t.leads, p.leads)} spark={data.series.map((s) => s.leads)} hint="no previous period" />
        <StatTile label="Lead → advance paid" value={t.conversion_pct == null ? "—" : fmtPct(t.conversion_pct)} delta={delta(t.conversion_pct, p.conversion_pct)} hint="no previous period" />
        <StatTile label="Average margin" value={t.avg_margin == null ? "—" : fmtPct(t.avg_margin)} delta={delta(t.avg_margin, p.avg_margin)} spark={data.series.map((s) => s.avg_margin ?? 0)} hint="no quotes yet" />
      </div>

      {/* Money and demand over time */}
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <ChartCard className="xl:col-span-2" title="Booked vs collected, by day" sub="Locked quotes and advances received" loading={loading}
                   table={{ columns: ["Day", "Booked", "Collected"], rows: data.series.map((s) => [dayLabel(s.day), rupees(s.booked_value), rupees(s.paid_value)]) }}>
          <LineChart labels={labels} series={[{ name: "Booked", values: data.series.map((s) => s.booked_value) }, { name: "Collected", values: data.series.map((s) => s.paid_value) }]} format={fmtCompact} />
        </ChartCard>
        <ChartCard title="New leads, by channel" sub="WhatsApp and website" loading={loading}
                   table={{ columns: ["Day", "WhatsApp", "Website"], rows: data.series.map((s) => [dayLabel(s.day), s.wa, s.web]) }}>
          <ColumnChart width={360} labels={labels} series={[{ name: "WhatsApp", values: data.series.map((s) => s.wa) }, { name: "Website", values: data.series.map((s) => s.web) }]} />
        </ChartCard>
      </div>

      {/* Funnel, tier mix, margin */}
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <ChartCard title="Funnel" sub="Conversion between each step" loading={loading}
                   table={{ columns: ["Step", "Count"], rows: data.funnel.map((f) => [f.name, f.value]) }}>
          <Funnel steps={data.funnel} />
        </ChartCard>
        <ChartCard title="Which tier books" sub="Locked and accepted quotes by tier" loading={loading}
                   table={{ columns: ["Tier", "Quoted", "Booked", "Avg per plate", "Avg margin"], rows: data.tiers.map((x) => [titleCase(x.tier), x.quotes, x.booked, x.avg_per_plate == null ? "—" : rupees(x.avg_per_plate), x.avg_margin == null ? "—" : fmtPct(x.avg_margin)]) }}>
          <StackedBar ordinal segments={data.tiers.map((x) => ({ name: titleCase(x.tier), value: x.booked }))} />
          <ul className="mt-4 divide-y divide-line text-xs">
            {data.tiers.map((x) => (
              <li key={x.tier} className="flex items-center justify-between py-1.5"><span>{titleCase(x.tier)}</span>
                <span className="flex gap-4 tabular-nums text-muted"><span>{x.quotes} quoted</span><span className="text-fg">{x.avg_per_plate == null ? "—" : `${rupees(x.avg_per_plate)}/plate`}</span><span>{x.avg_margin == null ? "—" : fmtPct(x.avg_margin)}</span></span></li>
            ))}
          </ul>
        </ChartCard>
        <ChartCard title="Margin distribution" sub="Quotes by margin band · floor 24%, target 40%" loading={loading}
                   table={{ columns: ["Margin", "Quotes"], rows: data.margin_hist.map((m) => [m.bucket, m.n]) }}>
          <ColumnChart ordinal width={360} labels={data.margin_hist.map((m) => m.bucket)} series={[{ name: "Quotes", values: data.margin_hist.map((m) => m.n) }]} height={180} />
        </ChartCard>
      </div>

      {/* Who is buying, at what size, and how Anvi is performing */}
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <ChartCard title="Occasions" sub="Leads and locked value" loading={loading}
                   table={{ columns: ["Occasion", "Leads", "Booked value"], rows: data.occasions.map((o) => [titleCase(o.occasion) || "Unknown", o.leads, rupees(o.value)]) }}>
          <Bars className="mt-1" data={data.occasions.map((o) => ({ label: titleCase(o.occasion) || "Unknown", value: o.leads }))} />
          <p className="mt-4 text-[11px] text-muted">Booked value: {data.occasions.filter((o) => o.value > 0).slice(0, 3).map((o) => `${titleCase(o.occasion) || "Unknown"} ${fmtCompact(o.value)}`).join(" · ") || "none yet"}</p>
        </ChartCard>
        <ChartCard title="Per plate by event size" sub="Bigger events, lower rate — the volume ladder at work" loading={loading}
                   table={{ columns: ["Guests", "Quotes", "Avg per plate", "Avg margin"], rows: data.guest_bands.map((g) => [g.band, g.quotes, g.avg_per_plate == null ? "—" : rupees(g.avg_per_plate), g.avg_margin == null ? "—" : fmtPct(g.avg_margin)]) }}>
          <ColumnChart ordinal width={360} labels={data.guest_bands.map((g) => g.band)} series={[{ name: "Avg per plate", values: data.guest_bands.map((g) => g.avg_per_plate ?? 0) }]} format={(v: number) => `₹${Math.round(v)}`} height={180} />
        </ChartCard>
        <ChartCard title="Anvi" sub="Response time, hand-offs, and the close-probability she assigns" loading={loading}
                   table={{ columns: ["Metric", "Value"], rows: [["Replies", data.response.replies], ["p50 response", data.response.p50_ms == null ? "—" : `${(data.response.p50_ms / 1000).toFixed(1)}s`], ["p95 response", data.response.p95_ms == null ? "—" : `${(data.response.p95_ms / 1000).toFixed(1)}s`], ["Hand-off rate", data.response.handoff_rate == null ? "—" : fmtPct(data.response.handoff_rate)], ["Tokens in / out", `${fmtNum(data.response.tokens_in)} / ${fmtNum(data.response.tokens_out)}`]] }}>
          <div className="grid grid-cols-3 gap-3 text-center">
            {[["p50", data.response.p50_ms], ["p95", data.response.p95_ms]].map(([k, v]) => (
              <div key={String(k)} className="rounded-xl bg-bg-2/60 p-3"><div className="label">{k} reply</div><div className="mt-1 text-lg font-semibold">{v == null ? "—" : `${(Number(v) / 1000).toFixed(1)}s`}</div></div>
            ))}
            <div className="rounded-xl bg-bg-2/60 p-3"><div className="label">Hand-off</div><div className="mt-1 text-lg font-semibold">{data.response.handoff_rate == null ? "—" : fmtPct(data.response.handoff_rate)}</div></div>
          </div>
          <div className="mt-4"><div className="label mb-2">Open leads by close probability</div>
            <ColumnChart ordinal width={360} labels={data.close_probability.map((c) => c.bucket)} series={[{ name: "Leads", values: data.close_probability.map((c) => c.n) }]} height={130} /></div>
        </ChartCard>
      </div>

      {/* Kitchen and costs */}
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <ChartCard className="xl:col-span-2" title="Kitchen, next 60 days" sub="Committed guests against the 500-guest daily capacity" loading={loading}
                   table={{ columns: ["Day", "Committed", "Capacity", "Bookings"], rows: data.kitchen.map((k) => [dayLabel(k.day), k.committed, k.capacity, k.bookings]) }}>
          <CalendarHeat cells={data.kitchen.map((k) => ({ label: dayLabel(k.day), value: k.committed, max: k.capacity, sub: `${k.bookings} booking${k.bookings === 1 ? "" : "s"}` }))} />
        </ChartCard>
        <ChartCard title="Cost movers, 7 days" sub="Wholesale ingredients that moved the most" loading={loading}
                   table={{ columns: ["Ingredient", "Price", "7d"], rows: data.cost_movers.map((c) => [c.name, `${rupees(c.price)}/${c.unit}`, `${c.change_7d > 0 ? "+" : ""}${c.change_7d.toFixed(1)}%`]) }}>
          <ul className="divide-y divide-line text-sm">
            {data.cost_movers.length === 0 && <li className="py-2 text-muted">No price movement recorded this week.</li>}
            {data.cost_movers.map((c) => (
              <li key={c.name} className="flex items-center justify-between py-2">
                <span>{c.name}<span className="ml-2 text-xs text-muted">{rupees(c.price)}/{c.unit}</span></span>
                <span className={cn("inline-flex items-center gap-1 text-xs font-semibold tabular-nums", c.change_7d > 0 ? "text-bad" : c.change_7d < 0 ? "text-good" : "text-muted")}>{c.change_7d > 0 ? "▲" : c.change_7d < 0 ? "▼" : "•"} {Math.abs(c.change_7d).toFixed(1)}%</span>
              </li>
            ))}
          </ul>
        </ChartCard>
      </div>
    </>
  );
}
