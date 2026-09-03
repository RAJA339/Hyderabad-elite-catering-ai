import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card p-5", className)} {...p} />;
}
export function CardTitle({ className, ...p }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-sm font-semibold tracking-tight", className)} {...p} />;
}
export function Stat({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: React.ReactNode; tone?: "good" | "warn" | "bad" }) {
  const toneCls = tone === "good" ? "text-good" : tone === "warn" ? "text-warn" : tone === "bad" ? "text-bad" : "";
  return (
    <Card className="flex flex-col gap-2">
      <span className="label">{label}</span>
      <span className={cn("kpi", toneCls)}>{value}</span>
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </Card>
  );
}
