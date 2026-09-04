"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { rupees, pct, titleCase, dateShort } from "@/lib/format";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge, stageTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageTitle } from "@/components/admin-shell";
import { STAGE_ORDER } from "@/lib/format";
import { cn } from "@/lib/utils";

type Detail = {
  lead: Record<string, unknown> & { stage: string; full_name: string | null; phone: string; handoff_active: boolean; qualification: { fields: Record<string, unknown>; missing: string[] } };
  messages: { id: string; role: string; kind: string; content: string | null; transcript: string | null; tool_calls: { name: string; args: Record<string, unknown> }[] | null; created_at: string }[];
  quotes: { id: string; quote_number: string; version: number; tier: string; status: string; guest_count: number; per_plate: string; grand_total: string; margin_pct: string; created_at: string }[];
  events: { type: string; actor_type: string; payload: Record<string, unknown>; per_plate_before: string | null; per_plate_after: string | null; created_at: string }[];
  payments: { id: string; quote_number: string; kind: string; amount: string; provider: string; provider_ref: string | null; status: string; paid_at: string | null; created_at: string }[];
};

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [reply, setReply] = useState("");
  const load = () => api<Detail>(`/api/leads/${id}`).then(setD).catch(() => {});
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return null;
  const l = d.lead;
  async function send(returnToAi: boolean) {
    if (!reply.trim()) return;
    await api(`/api/leads/${id}/reply`, { method: "POST", body: JSON.stringify({ text: reply, return_to_ai: returnToAi }) });
    setReply(""); load();
  }
  async function setStage(stage: string) { await api(`/api/leads/${id}/stage`, { method: "POST", body: JSON.stringify({ stage }) }); load(); }
  async function confirmPayment(pid: string) { await api(`/api/leads/${id}/payments/${pid}/confirm`, { method: "POST" }); load(); }
  return (
    <>
      <PageTitle title={l.full_name || l.phone} sub={`${titleCase(l.occasion as string) || "Occasion TBD"} · ${l.event_date ?? "date TBD"} · ${l.guest_count ?? "?"} guests · ${titleCase(l.diet as string) || "diet TBD"} · ${l.venue_area ?? "area TBD"}`}
        right={<div className="flex items-center gap-2"><Badge tone={stageTone(l.stage)}>{titleCase(l.stage)}</Badge>
          <select value={l.stage} onChange={(e) => setStage(e.target.value)} className="hairline h-8 rounded-lg bg-card px-2 text-xs">{STAGE_ORDER.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}</select></div>} />
      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="flex h-[70vh] flex-col p-0">
          <div className="flex items-center justify-between border-b border-line px-5 py-3"><CardTitle>Conversation</CardTitle>{l.handoff_active && <Badge tone="warn">Human hand-off active</Badge>}</div>
          <div className="scroll-thin flex-1 space-y-3 overflow-y-auto p-5">
            {d.messages.map((m) => (
              <div key={m.id} className={cn("flex flex-col", m.role === "customer" ? "items-start" : "items-end")}>
                <div className={cn("max-w-[80%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm", m.role === "customer" ? "bg-line/50" : m.role === "human" ? "bg-accent/15" : "bg-fg text-bg")}>
                  {m.transcript ? <><span className="label block opacity-70">voice note</span>{m.transcript}</> : m.content}
                </div>
                {m.tool_calls?.length ? <div className="mt-1 flex flex-wrap gap-1">{m.tool_calls.map((t, i) => <span key={i} className="rounded-full bg-line/60 px-2 py-0.5 font-mono text-[10px] text-muted">⚙ {t.name}</span>)}</div> : null}
                <span className="mt-0.5 text-[10px] text-muted">{new Date(m.created_at).toLocaleString("en-IN")}</span>
              </div>
            ))}
          </div>
          <div className="flex gap-2 border-t border-line p-3">
            <input value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Reply as a human on WhatsApp…" className="h-10 flex-1 rounded-xl bg-bg px-3 text-sm outline-none" />
            <Button size="md" variant="secondary" onClick={() => send(false)}>Send</Button>
            <Button size="md" onClick={() => send(true)}>Send & return to AI</Button>
          </div>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardTitle>Qualification</CardTitle>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              {Object.entries(l.qualification?.fields ?? {}).map(([k, v]) => <div key={k}><dt className="label">{titleCase(k)}</dt><dd>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd></div>)}
            </dl>
            {l.qualification?.missing?.length ? <p className="mt-3 text-xs text-warn">Missing: {l.qualification.missing.map(titleCase).join(", ")}</p> : <p className="mt-3 text-xs text-good">Fully qualified</p>}
          </Card>
          <Card>
            <CardTitle>Quote versions</CardTitle>
            <ul className="mt-3 divide-y divide-line text-sm">
              {d.quotes.map((q) => (
                <li key={q.id} className="flex items-center justify-between py-2">
                  <span><span className="font-medium">{q.quote_number}</span> <span className="text-muted">v{q.version} · {titleCase(q.tier)} · {q.guest_count} guests</span></span>
                  <span className="flex items-center gap-2 tabular-nums"><span>{rupees(q.grand_total)}</span><Badge tone={Number(q.margin_pct) < 32 ? "bad" : Number(q.margin_pct) < 40 ? "warn" : "good"}>{pct(q.margin_pct)}</Badge><Badge>{q.status}</Badge></span>
                </li>
              ))}
              {d.quotes.length === 0 && <li className="py-2 text-muted">No quote yet.</li>}
            </ul>
          </Card>
          <Card>
            <CardTitle>Payments</CardTitle>
            <ul className="mt-3 divide-y divide-line text-sm">
              {(d.payments ?? []).map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 py-2">
                  <span><span className="font-medium">{titleCase(p.kind)}</span> <span className="text-muted">· {p.quote_number} · {titleCase(p.provider)}</span>
                    {p.provider_ref && <span className="ml-1 font-mono text-[11px] text-muted">{p.provider_ref}</span>}</span>
                  <span className="flex items-center gap-2 tabular-nums">
                    <span>{rupees(p.amount)}</span>
                    {p.status === "paid" ? <Badge tone="good">Paid {dateShort(p.paid_at)}</Badge>
                      : <Button size="sm" onClick={() => confirmPayment(p.id)} title={p.provider_ref ? "Check the UTR in your UPI app, then confirm" : "Confirm you have received this"}>
                          {p.provider_ref ? "Confirm received" : "Mark paid"}
                        </Button>}
                  </span>
                </li>
              ))}
              {(d.payments ?? []).length === 0 && <li className="py-2 text-muted">No advance requested yet.</li>}
            </ul>
          </Card>
          <Card>
            <CardTitle>Menu change log</CardTitle>
            <ul className="mt-3 space-y-2 text-xs">
              {d.events.slice().reverse().slice(0, 12).map((e, i) => (
                <li key={i} className="flex justify-between gap-3"><span><span className="font-medium">{titleCase(e.type)}</span> <span className="text-muted">by {e.actor_type}</span>{Array.isArray(e.payload?.changes) ? <span className="text-muted"> · {(e.payload.changes as string[]).join("; ")}</span> : null}</span>
                  <span className="shrink-0 tabular-nums text-muted">{e.per_plate_before && e.per_plate_after ? `${rupees(e.per_plate_before)} → ${rupees(e.per_plate_after)}` : dateShort(e.created_at)}</span></li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
