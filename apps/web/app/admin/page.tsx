"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Lead, type Overview } from "@/lib/api";
import { rupees, pct, titleCase, timeAgo, STAGE_ORDER } from "@/lib/format";
import { Card, CardTitle, Stat } from "@/components/ui/card";
import { Badge, stageTone } from "@/components/ui/badge";
import { Bars, Meter } from "@/components/charts";
import { Skeleton } from "@/components/ui/skeleton";
import { PageTitle } from "@/components/admin-shell";

export default function AdminOverview() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [alerts, setAlerts] = useState<{ name: string; move_pct: string; now: string; unit: string }[]>([]);
  useEffect(() => {
    api<Overview>("/api/admin/overview").then(setOv).catch(() => {});
    api<{ leads: Lead[] }>("/api/leads?limit=8").then((r) => setLeads(r.leads)).catch(() => {});
    api<{ alerts: typeof alerts }>("/api/pricing/alerts").then((r) => setAlerts(r.alerts)).catch(() => {});
  }, []);
  if (!ov) return <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>;
  const avgMargin = Number(ov.margin.avg_margin ?? 0);
  const pipeline = STAGE_ORDER.map((s) => ({ label: titleCase(s), value: Number(ov.pipeline.find((p) => p.stage === s)?.n ?? 0) })).filter((p) => p.value > 0);
  const conv = ov.funnel.wa_leads + ov.funnel.web_leads ? Math.round((ov.funnel.paid / (ov.funnel.wa_leads + ov.funnel.web_leads)) * 100) : 0;
  return (
    <>
      <PageTitle title="Overview" sub="Live pipeline, margin health and the 500-guest kitchen at a glance." />
      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Booked value · 30d" value={rupees(ov.margin.booked_value_30d)} hint={`${ov.margin.quotes_30d} quotes issued`} />
        <Stat label="Avg margin · 30d" value={pct(ov.margin.avg_margin)} tone={avgMargin < 32 ? "bad" : avgMargin < 40 ? "warn" : "good"} hint={<Meter value={avgMargin} floor={32} target={40} className="mt-1" />} />
        <Stat label="Lead → paid" value={`${conv}%`} hint={`${ov.funnel.wa_leads} WhatsApp · ${ov.funnel.web_leads} web`} />
        <Stat label="Open hand-offs" value={ov.open_escalations} tone={ov.open_escalations ? "warn" : undefined} hint={`${ov.clv.repeat_customers} repeat clients · CLV ${rupees(ov.clv.avg_clv)}`} />
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Card><CardTitle>Pipeline by stage</CardTitle><Bars className="mt-4" data={pipeline} /></Card>
        <Card>
          <CardTitle>Conversion funnel · 90d</CardTitle>
          <Bars className="mt-4" data={[
            { label: "Leads", value: ov.funnel.wa_leads + ov.funnel.web_leads }, { label: "Quoted", value: ov.funnel.quoted },
            { label: "Price locked", value: ov.funnel.locked }, { label: "Advance paid", value: ov.funnel.paid }]} />
        </Card>
        <Card>
          <div className="flex items-center justify-between"><CardTitle>Supplier price alerts</CardTitle><Link href="/admin/pricing" className="text-xs text-muted link">All prices</Link></div>
          <ul className="mt-3 divide-y divide-line text-sm">
            {alerts.length === 0 && <li className="py-2 text-muted">No ingredient moved beyond its threshold this week.</li>}
            {alerts.slice(0, 6).map((a) => (
              <li key={a.name} className="flex items-center justify-between py-2">
                <span>{a.name}</span>
                <span className="flex items-center gap-2 tabular-nums"><span className="text-muted">{rupees(a.now)}/{a.unit}</span><Badge tone={Number(a.move_pct) > 0 ? "warn" : "good"}>{Number(a.move_pct) > 0 ? "+" : ""}{a.move_pct}%</Badge></span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <Card className="mt-4 p-0">
        <div className="flex items-center justify-between px-5 py-4"><CardTitle>Recent leads</CardTitle><Link href="/admin/leads" className="text-xs text-muted link">Open pipeline</Link></div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-y border-line text-left"><tr className="label">{["Client", "Occasion", "Event", "Guests", "Stage", "Latest quote", "Updated"].map((h) => <th key={h} className="px-5 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {leads.map((l) => (
                <tr key={l.id} className="hover:bg-line/30">
                  <td className="px-5 py-2.5"><Link href={`/admin/leads/${l.id}`} className="font-medium">{l.full_name || l.phone}</Link>{l.handoff_active && <Badge tone="warn" className="ml-2">human</Badge>}</td>
                  <td className="px-5 py-2.5">{titleCase(l.occasion) || "—"}</td>
                  <td className="px-5 py-2.5">{l.event_date ?? "—"}</td>
                  <td className="px-5 py-2.5 tabular-nums">{l.guest_count ?? "—"}</td>
                  <td className="px-5 py-2.5"><Badge tone={stageTone(l.stage)}>{titleCase(l.stage)}</Badge></td>
                  <td className="px-5 py-2.5 tabular-nums">{l.latest_total ? `${rupees(l.latest_total)} · ${rupees(l.latest_per_plate)}/plate` : "—"}</td>
                  <td className="px-5 py-2.5 text-muted">{timeAgo(l.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
