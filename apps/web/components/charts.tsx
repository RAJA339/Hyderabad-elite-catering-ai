"use client";
import { useId, useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, BarChart3, Minus, Table2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * A dependency-free chart kit, drawn in SVG against the site's tokens.
 *
 * Series colours come from --viz-1…4 (validated for both themes), ordered scales from
 * --viz-ord-1…4, and everything else — grid, axis, text — from the page's own ink, so a
 * chart never carries a colour the page does not. Marks are thin, gridlines are hairlines,
 * every chart has a hover layer and a table twin, and text never wears a series colour.
 */

export const fmtCompact = (v: number) =>
  Math.abs(v) >= 1e7 ? `₹${(v / 1e7).toFixed(v % 1e7 === 0 ? 0 : 2)}Cr`
  : Math.abs(v) >= 1e5 ? `₹${(v / 1e5).toFixed(v % 1e5 === 0 ? 0 : 1)}L`
  : Math.abs(v) >= 1e3 ? `₹${(v / 1e3).toFixed(v % 1e3 === 0 ? 0 : 1)}K`
  : `₹${Math.round(v)}`;
export const fmtNum = (v: number) => v.toLocaleString("en-IN", { maximumFractionDigits: 0 });
export const fmtPct = (v: number) => `${v.toFixed(1)}%`;

const SERIES = ["var(--viz-1)", "var(--viz-2)", "var(--viz-3)", "var(--viz-4)"];
const ORD = ["var(--viz-ord-1)", "var(--viz-ord-2)", "var(--viz-ord-3)", "var(--viz-ord-4)"];

/** Clean tick values: 0 … a round max in ~4 steps. */
function ticks(max: number, n = 4): number[] {
  if (max <= 0) return [0, 1];
  const raw = max / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const top = Math.ceil(max / step) * step;
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
}

/* ── Container: title, optional right slot, and the table twin ─────────────── */
export function ChartCard({ title, sub, right, table, children, className, loading }: {
  title: string; sub?: string; right?: React.ReactNode; className?: string; loading?: boolean;
  table?: { columns: string[]; rows: (string | number)[][] };
  children: React.ReactNode;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure className={cn("card flex flex-col p-5", className)}>
      <figcaption className="mb-3 flex items-start justify-between gap-3">
        <div><div className="text-sm font-semibold tracking-tight">{title}</div>{sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}</div>
        <div className="flex items-center gap-2">
          {right}
          {table && (
            <button type="button" onClick={() => setShowTable((v) => !v)} aria-pressed={showTable} title={showTable ? "Show chart" : "Show as table"}
                    className="grid h-7 w-7 place-items-center rounded-lg text-muted transition-colors hover:bg-line/50 hover:text-fg">
              {showTable ? <BarChart3 size={14} /> : <Table2 size={14} />}
            </button>
          )}
        </div>
      </figcaption>
      <div className={cn("relative flex-1 transition-opacity", loading && "opacity-50")}>
        {showTable && table ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-line text-left"><tr>{table.columns.map((c) => <th key={c} className="label py-1.5 pr-3 font-medium">{c}</th>)}</tr></thead>
              <tbody className="divide-y divide-line">{table.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={cn("py-1.5 pr-3", j > 0 && "tabular-nums")}>{c}</td>)}</tr>)}</tbody>
            </table>
          </div>
        ) : children}
      </div>
    </figure>
  );
}

/* ── Stat tile: value · delta vs previous period · sparkline ─────────────── */
export function StatTile({ label, value, delta, deltaLabel = "vs prior", upIsGood = true, spark, hint, className }: {
  label: string; value: string; delta?: number | null; deltaLabel?: string; upIsGood?: boolean; spark?: number[]; hint?: string; className?: string;
}) {
  const dir = delta == null || Math.abs(delta) < 0.05 ? 0 : delta > 0 ? 1 : -1;
  const good = dir === 0 ? null : (dir > 0) === upIsGood;
  return (
    <div className={cn("card flex flex-col gap-2 p-5", className)}>
      <span className="label">{label}</span>
      <span className="text-[28px] font-semibold leading-none tracking-tight">{value}</span>
      <div className="flex items-end justify-between gap-3">
        <span className={cn("inline-flex items-center gap-1 whitespace-nowrap text-xs", good == null ? "text-muted" : good ? "text-good" : "text-bad")}>
          {dir === 0 ? <Minus size={12} /> : dir > 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
          {delta == null ? (hint ?? "—") : <>{delta > 0 ? "+" : ""}{delta.toFixed(delta % 1 === 0 ? 0 : 1)}% <span className="text-muted">{deltaLabel}</span></>}
        </span>
        {spark && spark.length > 1 && <Sparkline points={spark} className="h-6 w-[72px] shrink-0 text-muted/60" accentLast />}
      </div>
    </div>
  );
}

/* ── Line chart: multi-series, crosshair, one tooltip for every series ────── */
export function LineChart({ labels, series, format = fmtNum, height = 220, area = true }: {
  labels: string[]; series: { name: string; values: number[] }[]; format?: (v: number) => string; height?: number; area?: boolean;
}) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = height, padL = 44, padR = 16, padT = 12, padB = 26;
  const iw = W - padL - padR, ih = H - padT - padB;
  const max = Math.max(1, ...series.flatMap((s) => s.values));
  const tk = ticks(max); const top = tk[tk.length - 1];
  const n = labels.length;
  const x = (i: number) => padL + (n > 1 ? (i / (n - 1)) * iw : iw / 2);
  const y = (v: number) => padT + ih - (v / top) * ih;
  const paths = series.map((s) => s.values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" "));
  const labelEvery = Math.max(1, Math.ceil(n / 6));
  const showLabel = (i: number) => i === n - 1 || (i % labelEvery === 0 && n - 1 - i >= Math.max(1, labelEvery / 2));
  const hi = hover;
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" style={{ height }} role="img" aria-label={series.map((s) => s.name).join(", ")}
           onPointerLeave={() => setHover(null)}
           onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); const px = ((e.clientX - r.left) / r.width) * W; const i = Math.round(((px - padL) / iw) * (n - 1)); setHover(Math.max(0, Math.min(n - 1, i))); }}>
        <defs>{series.map((s, si) => <linearGradient key={s.name} id={`${id}-g${si}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={SERIES[si]} stopOpacity="0.14" /><stop offset="1" stopColor={SERIES[si]} stopOpacity="0" /></linearGradient>)}</defs>
        {tk.map((t) => <g key={t}><line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} className="stroke-line" strokeWidth="1" /><text x={padL - 6} y={y(t) + 3} textAnchor="end" className="fill-muted" fontSize="10">{format(t)}</text></g>)}
        {labels.map((l, i) => showLabel(i) ? <text key={l + i} x={x(i)} y={H - 8} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"} className="fill-muted" fontSize="10">{l}</text> : null)}
        {series.map((s, si) => (
          <g key={s.name}>
            {area && series.length === 1 && n > 1 && <path d={`${paths[si]} L${x(n - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill={`url(#${id}-g${si})`} />}
            <path d={paths[si]} fill="none" stroke={SERIES[si]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            {n > 0 && <circle cx={x(n - 1)} cy={y(s.values[n - 1])} r="4" fill={SERIES[si]} className="stroke-card" strokeWidth="2" />}
          </g>
        ))}
        {hi != null && (
          <g>
            <line x1={x(hi)} x2={x(hi)} y1={padT} y2={padT + ih} className="stroke-muted" strokeWidth="1" />
            {series.map((s, si) => <circle key={s.name} cx={x(hi)} cy={y(s.values[hi])} r="4.5" fill={SERIES[si]} className="stroke-card" strokeWidth="2" />)}
          </g>
        )}
      </svg>
      {hi != null && (
        <div className="pointer-events-none absolute top-2 z-10 rounded-xl border border-line bg-card px-3 py-2 text-xs shadow-soft"
             style={{ left: `${Math.min(78, Math.max(2, (x(hi) / W) * 100))}%`, transform: x(hi) / W > 0.7 ? "translateX(-100%)" : undefined }}>
          <div className="label mb-1">{labels[hi]}</div>
          {series.map((s, si) => <div key={s.name} className="flex items-center gap-2"><span className="inline-block h-0.5 w-3 rounded" style={{ background: SERIES[si] }} /><span className="font-semibold tabular-nums">{format(s.values[hi])}</span><span className="text-muted">{s.name}</span></div>)}
        </div>
      )}
      {series.length > 1 && <Legend items={series.map((s, i) => ({ name: s.name, color: SERIES[i], kind: "line" }))} />}
    </div>
  );
}

/* ── Column chart: thin columns, rounded caps, per-mark hover, selective labels ── */
export function ColumnChart({ labels, series, format = fmtNum, height = 200, width = 640, stacked = true, ordinal = false }: {
  labels: string[]; series: { name: string; values: number[] }[]; format?: (v: number) => string; height?: number; width?: number; stacked?: boolean; ordinal?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = width, H = height, padL = 40, padR = 8, padT = 18, padB = 26;
  const iw = W - padL - padR, ih = H - padT - padB;
  const n = labels.length;
  const totals = labels.map((_, i) => stacked ? series.reduce((a, s) => a + (s.values[i] ?? 0), 0) : Math.max(...series.map((s) => s.values[i] ?? 0)));
  const tk = ticks(Math.max(1, ...totals)); const top = tk[tk.length - 1];
  const band = iw / Math.max(n, 1);
  const bw = Math.min(24, band * 0.6);
  const y = (v: number) => padT + ih - (v / top) * ih;
  const ordColor = (i: number) => ORD[Math.min(ORD.length - 1, Math.floor((i / Math.max(n - 1, 1)) * (ORD.length - 1)))];
  const maxI = totals.indexOf(Math.max(...totals));
  // Thin the axis only for long series (dates); a handful of categories always shows every label.
  const labelEvery = n > 8 ? Math.max(1, Math.ceil(n / (W < 480 ? 4 : 8))) : 1;
  const showLabel = (i: number) => labelEvery === 1 || i === n - 1 || (i % labelEvery === 0 && n - 1 - i >= Math.max(2, labelEvery * 0.75));
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" style={{ height }} role="img" onPointerLeave={() => setHover(null)}>
        {tk.map((t) => <g key={t}><line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} className="stroke-line" strokeWidth="1" /><text x={padL - 6} y={y(t) + 3} textAnchor="end" className="fill-muted" fontSize="10">{format(t)}</text></g>)}
        {labels.map((l, i) => {
          const cx = padL + band * i + band / 2;
          let acc = 0;
          const isHover = hover === i;
          return (
            <g key={l + i}>
              <rect x={padL + band * i} y={padT} width={band} height={ih} fill="transparent" onPointerEnter={() => setHover(i)} />
              {series.map((s, si) => {
                const v = s.values[i] ?? 0; if (v <= 0) return null;
                const y0 = stacked ? y(acc + v) : y(v); const h = Math.max(0, (stacked ? y(acc) : y(0)) - y0);
                const gap = stacked && acc > 0 ? 2 : 0; acc += v;
                const topmost = si === series.length - 1 || !stacked;
                return <rect key={s.name} x={cx - bw / 2} y={y0 + gap} width={bw} height={Math.max(0, h - gap)} rx={topmost ? 4 : 0} ry={topmost ? 4 : 0}
                             fill={ordinal ? ordColor(i) : SERIES[si]} opacity={hover == null || isHover ? 1 : 0.55} style={{ transition: "opacity .15s" }} />;
              })}
              {(i === maxI || i === n - 1) && totals[i] > 0 && <text x={cx} y={y(totals[i]) - 5} textAnchor="middle" className="fill-fg" fontSize="10" fontWeight="600">{format(totals[i])}</text>}
              {showLabel(i) && <text x={cx} y={H - 8} textAnchor={i === n - 1 ? "end" : i === 0 ? "start" : "middle"} className="fill-muted" fontSize="10">{l}</text>}
            </g>
          );
        })}
      </svg>
      {hover != null && (
        <div className="pointer-events-none absolute top-1 z-10 rounded-xl border border-line bg-card px-3 py-2 text-xs shadow-soft"
             style={{ left: `${Math.min(80, ((padL + band * hover + band / 2) / W) * 100)}%`, transform: (padL + band * hover) / W > 0.7 ? "translateX(-100%)" : undefined }}>
          <div className="label mb-1">{labels[hover]}</div>
          {series.map((s, si) => <div key={s.name} className="flex items-center gap-2"><span className="inline-block h-2 w-2 rounded-sm" style={{ background: ordinal ? ordColor(hover) : SERIES[si] }} /><span className="font-semibold tabular-nums">{format(s.values[hover] ?? 0)}</span><span className="text-muted">{s.name}</span></div>)}
        </div>
      )}
      {series.length > 1 && <Legend items={series.map((s, i) => ({ name: s.name, color: SERIES[i], kind: "rect" }))} />}
    </div>
  );
}

/* ── Stacked horizontal bar: part-to-whole with 2px surface gaps ──────────── */
export function StackedBar({ segments, format = fmtNum, ordinal = false }: { segments: { name: string; value: number }[]; format?: (v: number) => string; ordinal?: boolean }) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  const palette = ordinal ? ORD : SERIES;
  const [hover, setHover] = useState<number | null>(null);
  return (
    <div>
      <div className="flex h-5 w-full gap-0.5 overflow-hidden rounded-full" onPointerLeave={() => setHover(null)}>
        {segments.map((s, i) => s.value > 0 && (
          <div key={s.name} onPointerEnter={() => setHover(i)} title={`${s.name}: ${format(s.value)}`}
               className="relative h-full transition-opacity" style={{ width: `${(s.value / total) * 100}%`, background: palette[i % palette.length], opacity: hover == null || hover === i ? 1 : 0.55 }}>
            {(s.value / total) > 0.16 && <span className={cn("absolute inset-0 grid place-items-center text-[10px] font-semibold", ordinal && i < 2 ? "text-black/80" : "text-white")}>{Math.round((s.value / total) * 100)}%</span>}
          </div>
        ))}
      </div>
      <Legend items={segments.map((s, i) => ({ name: `${s.name} · ${format(s.value)}`, color: palette[i % palette.length], kind: "rect" }))} />
    </div>
  );
}

/* ── Funnel: ordinal ramp, conversion between steps ────────────────────────── */
export function Funnel({ steps, format = fmtNum }: { steps: { name: string; value: number }[]; format?: (v: number) => string }) {
  const max = Math.max(1, ...steps.map((s) => s.value));
  return (
    <div className="space-y-2.5">
      {steps.map((s, i) => {
        const prev = i > 0 ? steps[i - 1].value : null;
        const rate = prev ? Math.round((s.value / Math.max(prev, 1)) * 100) : null;
        return (
          <div key={s.name} className="grid grid-cols-[96px_1fr_auto] items-center gap-3 text-xs">
            <span className="truncate text-muted">{s.name}</span>
            <div className="h-3 overflow-hidden rounded-r-[4px] bg-line/40" title={`${s.name}: ${format(s.value)}`}>
              <div className="h-full rounded-r-[4px]" style={{ width: `${(s.value / max) * 100}%`, background: ORD[Math.min(ORD.length - 1, i)] }} />
            </div>
            <span className="w-24 text-right tabular-nums"><span className="font-semibold">{format(s.value)}</span>{rate != null && <span className="ml-1.5 text-muted">{rate}%</span>}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ── Heatmap: a calendar grid on a single-hue ramp ─────────────────────────── */
export function CalendarHeat({ cells, format = fmtNum }: { cells: { label: string; value: number; max: number; sub?: string }[]; format?: (v: number) => string }) {
  const [hover, setHover] = useState<number | null>(null);
  const step = (c: { value: number; max: number }) => c.value <= 0 ? -1 : Math.min(3, Math.floor((c.value / Math.max(c.max, 1)) * 4));
  return (
    <div className="relative">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(28px,1fr))] gap-1" onPointerLeave={() => setHover(null)}>
        {cells.map((c, i) => {
          const s = step(c);
          return <div key={c.label} onPointerEnter={() => setHover(i)} className="aspect-square rounded-[5px] border border-line/60 transition-transform hover:scale-110"
                      style={{ background: s < 0 ? "rgb(var(--line) / 0.35)" : ORD[s] }} aria-label={`${c.label}: ${format(c.value)}`} />;
        })}
      </div>
      {hover != null && (
        <div className="pointer-events-none absolute -top-1 left-0 z-10 -translate-y-full rounded-xl border border-line bg-card px-3 py-2 text-xs shadow-soft">
          <div className="label">{cells[hover].label}</div>
          <div className="font-semibold tabular-nums">{format(cells[hover].value)} <span className="font-normal text-muted">of {format(cells[hover].max)}</span></div>
          {cells[hover].sub && <div className="text-muted">{cells[hover].sub}</div>}
        </div>
      )}
      <div className="mt-2 flex items-center gap-1.5 text-[10px] text-muted">Light <span className="inline-flex gap-0.5">{ORD.map((c) => <span key={c} className="h-2.5 w-2.5 rounded-[3px]" style={{ background: c }} />)}</span> Full</div>
    </div>
  );
}

function Legend({ items }: { items: { name: string; color: string; kind: "line" | "rect" }[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
      {items.map((it) => <span key={it.name} className="inline-flex items-center gap-1.5">{it.kind === "line" ? <span className="inline-block h-0.5 w-3 rounded" style={{ background: it.color }} /> : <span className="inline-block h-2 w-2 rounded-sm" style={{ background: it.color }} />}{it.name}</span>)}
    </div>
  );
}

/* ── Kept for existing consumers ───────────────────────────────────────────── */
export function Bars({ data, max, className, format }: { data: { label: string; value: number; tone?: string }[]; max?: number; className?: string; format?: (v: number) => string }) {
  const m = max ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <div className={cn("space-y-2", className)}>
      {data.map((d) => (
        <div key={d.label} className="grid grid-cols-[110px_1fr_auto] items-center gap-3 text-xs">
          <span className="truncate text-muted">{d.label}</span>
          <div className="h-2 overflow-hidden rounded-r-[4px] bg-line/50"><div className={cn("h-full rounded-r-[4px] transition-all", d.tone)} style={{ width: `${Math.min(100, (d.value / m) * 100)}%`, background: d.tone ? undefined : "var(--viz-1)" }} /></div>
          <span className="tabular-nums">{format ? format(d.value) : d.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Sparkline({ points, className, stroke = "currentColor", accentLast = false }: { points: number[]; className?: string; stroke?: string; accentLast?: boolean }) {
  const d = useMemo(() => {
    if (!points.length) return "";
    const w = 120, h = 32, min = Math.min(...points), max = Math.max(...points);
    return points.map((p, i) => `${(i / Math.max(points.length - 1, 1)) * w},${h - ((p - min) / Math.max(max - min, 1e-9)) * (h - 6) - 3}`).join(" ");
  }, [points]);
  if (!points.length) return null;
  const last = d.split(" ").pop()!.split(",");
  return (
    <svg viewBox="0 0 120 32" className={cn("h-8 w-[120px]", className)} preserveAspectRatio="none">
      <polyline points={d} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {accentLast && <circle cx={last[0]} cy={last[1]} r="2.5" fill="var(--viz-1)" vectorEffect="non-scaling-stroke" />}
    </svg>
  );
}

export function Meter({ value, floor, target, className }: { value: number; floor: number; target: number; className?: string }) {
  const tone = value < floor ? "bg-bad" : value < target ? "bg-warn" : "bg-good";
  return (
    <div className={cn("relative h-2 w-full rounded-full bg-line/60", className)}>
      <div className={cn("h-full rounded-full", tone)} style={{ width: `${Math.min(100, value)}%` }} />
      <div className="absolute top-[-3px] h-[14px] w-px bg-muted" style={{ left: `${floor}%` }} title={`floor ${floor}%`} />
      <div className="absolute top-[-3px] h-[14px] w-px bg-fg" style={{ left: `${target}%` }} title={`target ${target}%`} />
    </div>
  );
}
