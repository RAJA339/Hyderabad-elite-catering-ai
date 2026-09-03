"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Lead } from "@/lib/api";
import { rupees, titleCase, timeAgo, STAGE_ORDER } from "@/lib/format";
import { Badge, stageTone } from "@/components/ui/badge";
import { PageTitle } from "@/components/admin-shell";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const COLUMNS = ["new", "qualifying", "qualified", "quoted", "negotiating", "locked", "advance_paid", "confirmed"];

export default function Pipeline() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [view, setView] = useState<"board" | "list">("board");
  useEffect(() => { api<{ leads: Lead[] }>("/api/leads?limit=300").then((r) => setLeads(r.leads)).catch(() => {}); }, []);
  const by = (s: string) => leads.filter((l) => l.stage === s);
  return (
    <>
      <PageTitle title="Lead pipeline" sub="Every conversation, its source, stage and latest live quote." right={
        <div className="flex gap-1">{(["board", "list"] as const).map((v) => <Button key={v} size="sm" variant={view === v ? "primary" : "secondary"} onClick={() => setView(v)}>{titleCase(v)}</Button>)}
          <a href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/leads/export/customers.csv`}><Button size="sm" variant="secondary">Export CSV</Button></a></div>} />
      {view === "board" ? (
        <div className="scroll-thin flex gap-3 overflow-x-auto pb-4">
          {COLUMNS.map((s) => (
            <div key={s} className="w-64 shrink-0">
              <div className="mb-2 flex items-center justify-between px-1"><span className="label">{titleCase(s)}</span><span className="text-xs text-muted tabular-nums">{by(s).length}</span></div>
              <div className="space-y-2">
                {by(s).map((l) => (
                  <Link key={l.id} href={`/admin/leads/${l.id}`} className={cn("card block p-3 hover:border-fg/40", l.handoff_active && "border-warn/60")}>
                    <div className="flex items-center justify-between"><span className="text-sm font-medium">{l.full_name || l.phone}</span><span className="text-[10px] text-muted">{l.source}</span></div>
                    <div className="mt-1 text-xs text-muted">{titleCase(l.occasion) || "—"} · {l.guest_count ?? "?"} guests · {l.event_date ?? "no date"}</div>
                    <div className="mt-2 flex items-center justify-between text-xs"><span className="tabular-nums font-medium">{l.latest_total ? rupees(l.latest_total) : "—"}</span><span className="text-muted">{timeAgo(l.updated_at)}</span></div>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left"><tr className="label">{["Client", "Source", "Occasion", "Event", "Guests", "Diet", "Area", "Stage", "Quote"].map((h) => <th key={h} className="px-4 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {[...leads].sort((a, b) => STAGE_ORDER.indexOf(a.stage) - STAGE_ORDER.indexOf(b.stage)).map((l) => (
                <tr key={l.id} className="hover:bg-line/30">
                  <td className="px-4 py-2"><Link href={`/admin/leads/${l.id}`} className="font-medium">{l.full_name || l.phone}</Link></td>
                  <td className="px-4 py-2 text-muted">{l.source}</td><td className="px-4 py-2">{titleCase(l.occasion) || "—"}</td><td className="px-4 py-2">{l.event_date ?? "—"}</td>
                  <td className="px-4 py-2 tabular-nums">{l.guest_count ?? "—"}</td><td className="px-4 py-2">{titleCase(l.diet) || "—"}</td><td className="px-4 py-2">{l.venue_area ?? "—"}</td>
                  <td className="px-4 py-2"><Badge tone={stageTone(l.stage)}>{titleCase(l.stage)}</Badge></td><td className="px-4 py-2 tabular-nums">{l.latest_total ? rupees(l.latest_total) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
