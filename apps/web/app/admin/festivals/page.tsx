"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { rupees, pct, dateShort } from "@/lib/format";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageTitle } from "@/components/admin-shell";

type F = { key: string; name: string; starts_on: string; ends_on: string; quotes: number; booked: number; revenue: string; discounts_given: string; avg_margin: string | null };
type Rule = { key: string; name: string; kind: string; value: string; festival_key: string | null; booking_window_days_before_festival: number | null; guest_min: number | null; diet: string | null; stackable: boolean; is_active: boolean };

export default function Festivals() {
  const [fs, setFs] = useState<F[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  useEffect(() => { api<{ festivals: F[] }>("/api/admin/festival-performance").then((r) => setFs(r.festivals)).catch(() => {}); api<{ rules: Rule[] }>("/api/festivals/rules").then((r) => setRules(r.rules)).catch(() => {}); }, []);
  const today = new Date().toISOString().slice(0, 10);
  return (
    <>
      <PageTitle title="Festival intelligence" sub="Calendar, demand windows, discount rules and what each festival actually earned." />
      <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <Card className="overflow-x-auto p-0">
          <div className="px-5 py-4"><CardTitle>Performance by festival</CardTitle></div>
          <table className="w-full text-sm">
            <thead className="border-y border-line text-left"><tr className="label">{["Festival", "Window", "Quotes", "Booked", "Revenue", "Discounts", "Margin"].map((h) => <th key={h} className="px-4 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {fs.map((f) => (
                <tr key={f.key} className={f.ends_on < today ? "text-muted" : ""}>
                  <td className="px-4 py-2 font-medium">{f.name}{f.starts_on <= today && f.ends_on >= today && <Badge tone="accent" className="ml-2">live</Badge>}</td>
                  <td className="px-4 py-2">{dateShort(f.starts_on)} – {dateShort(f.ends_on)}</td>
                  <td className="px-4 py-2 tabular-nums">{f.quotes}</td><td className="px-4 py-2 tabular-nums">{f.booked}</td>
                  <td className="px-4 py-2 tabular-nums">{rupees(f.revenue)}</td><td className="px-4 py-2 tabular-nums">{rupees(f.discounts_given)}</td><td className="px-4 py-2">{f.avg_margin ? pct(f.avg_margin) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card>
          <CardTitle>Discount rules (margin-protected)</CardTitle>
          <ul className="mt-3 divide-y divide-line text-sm">
            {rules.map((r) => (
              <li key={r.key} className="py-2">
                <div className="flex items-center justify-between"><span className="font-medium">{r.name}</span><Badge tone={r.is_active ? "good" : "neutral"}>{r.kind === "percent" ? `${r.value}%` : r.kind === "per_plate_off" ? `₹${r.value}/plate` : r.kind}</Badge></div>
                <div className="text-xs text-muted">{[r.festival_key && `festival ${r.festival_key}`, r.booking_window_days_before_festival && `≥${r.booking_window_days_before_festival}d early`, r.guest_min && `≥${r.guest_min} guests`, r.diet, r.stackable && "stackable"].filter(Boolean).join(" · ") || "always"}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
