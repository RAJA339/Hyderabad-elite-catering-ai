"use client";
import { cn } from "@/lib/utils";

/** Dependency-free, theme-aware micro charts. */
export function Bars({ data, max, className, format }: { data: { label: string; value: number; tone?: string }[]; max?: number; className?: string; format?: (v: number) => string }) {
  const m = max ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <div className={cn("space-y-2", className)}>
      {data.map((d) => (
        <div key={d.label} className="grid grid-cols-[110px_1fr_auto] items-center gap-3 text-xs">
          <span className="truncate text-muted">{d.label}</span>
          <div className="h-2 overflow-hidden rounded-full bg-line/60">
            <div className={cn("h-full rounded-full bg-fg transition-all", d.tone)} style={{ width: `${Math.min(100, (d.value / m) * 100)}%` }} />
          </div>
          <span className="tabular-nums">{format ? format(d.value) : d.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Sparkline({ points, className, stroke = "currentColor" }: { points: number[]; className?: string; stroke?: string }) {
  if (!points.length) return null;
  const w = 120, h = 32, min = Math.min(...points), max = Math.max(...points);
  const d = points.map((p, i) => `${(i / Math.max(points.length - 1, 1)) * w},${h - ((p - min) / Math.max(max - min, 1e-9)) * (h - 4) - 2}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={cn("h-8 w-[120px]", className)} preserveAspectRatio="none">
      <polyline points={d} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
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
