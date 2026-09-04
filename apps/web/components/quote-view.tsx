"use client";
import { useState } from "react";
import { Lock, Share2, ShieldCheck } from "lucide-react";
import { api, type QuoteBundle } from "@/lib/api";
import { rupees, titleCase, dateShort } from "@/lib/format";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MarketWidget } from "@/components/market-widget";
import { UpiPay } from "@/components/upi-pay";

const CATS = ["welcome_drinks", "starters", "main_veg", "main_nonveg", "rice_breads", "live_counters", "desserts"];

export function QuoteView({ bundle, token, readOnly = false, onUpdate }: { bundle: QuoteBundle; token?: string; readOnly?: boolean; onUpdate?: (b: QuoteBundle) => void }) {
  const q = bundle.quote;
  const [req, setReq] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [share, setShare] = useState<string | null>(null);
  const locked = q.status === "locked" || q.status === "accepted";
  async function change(text: string) {
    if (!token || !text.trim()) return;
    setBusy(true); setReply(null);
    try { const r = await api<QuoteBundle & { reply: string }>(`/api/portal/${token}/change`, { method: "POST", auth: false, body: JSON.stringify({ request: text }) }); setReply(r.reply); onUpdate?.(r); setReq(""); }
    catch (e) { setReply((e as Error).message); } finally { setBusy(false); }
  }
  async function doShare() { if (!token) return; const r = await api<{ whatsapp_share: string; url: string }>(`/api/portal/${token}/share`, { method: "POST", auth: false }); setShare(r.url); window.open(r.whatsapp_share, "_blank"); }
  return (
    <div className="mx-auto max-w-3xl space-y-4 px-5 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="label">Quote {q.quote_number} · v{q.version}</span>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{titleCase(bundle.lead.occasion) || "Your event"} · {q.guest_count} guests</h1>
          <p className="text-sm text-muted">{dateShort(q.event_date)} · {bundle.lead.venue_area ?? "Hyderabad"} · {titleCase(q.diet)} · {titleCase(q.tier)} package</p>
        </div>
        <Badge tone={locked ? "good" : "accent"}>{locked ? "Price locked" : `Valid till ${dateShort(q.valid_until)}`}</Badge>
      </div>

      <Card className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div><span className="label">Per plate</span><div className="kpi">{rupees(q.per_plate)}</div></div>
        <div><span className="label">Subtotal</span><div className="text-lg tabular-nums">{rupees(q.subtotal)}</div></div>
        <div><span className="label">Offers</span><div className="text-lg tabular-nums text-good">−{rupees(q.discount_total)}</div></div>
        <div><span className="label">Total incl. GST</span><div className="text-lg font-semibold tabular-nums">{rupees(q.grand_total)}</div></div>
      </Card>

      {bundle.lock && (
        <Card className="flex items-center gap-3 border-good/40">
          <ShieldCheck className="text-good" />
          <div className="text-sm"><span className="font-medium">Price Locked certificate</span> <span className="font-mono text-xs text-muted">{bundle.lock.certificate_hash.slice(0, 12).toUpperCase()}</span><div className="text-xs text-muted">{rupees(bundle.lock.locked_per_plate)}/plate guaranteed till {dateShort(bundle.lock.valid_until)}, whatever the market does.</div></div>
        </Card>
      )}

      <Card>
        <div className="flex items-center justify-between"><CardTitle>Live menu</CardTitle><span className="text-xs text-muted">{bundle.items.length} items</span></div>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {CATS.filter((c) => bundle.items.some((i) => i.category === c)).map((c) => (
            <div key={c}>
              <div className="label mb-1">{titleCase(c)}</div>
              <ul className="space-y-1 text-sm">{bundle.items.filter((i) => i.category === c).map((i) => <li key={i.slug} className="flex justify-between"><span>{i.name}</span><span className="tabular-nums text-muted">{rupees(i.unit_price)}</span></li>)}</ul>
            </div>
          ))}
        </div>
        {!readOnly && token && (
          <div className="mt-5 border-t border-line pt-4">
            {locked ? <p className="flex items-center gap-2 text-xs text-muted"><Lock size={12} /> Price is locked. Message us on WhatsApp for changes.</p> : (
              <form onSubmit={(e) => { e.preventDefault(); change(req); }} className="space-y-2">
                <label className="label">Request a change (re-priced instantly)</label>
                <div className="flex gap-2"><input value={req} onChange={(e) => setReq(e.target.value)} placeholder="e.g. add 40 guests · remove mutton · make it Jain · add live pasta counter" className="hairline h-10 flex-1 rounded-xl bg-bg px-3 text-sm outline-none" /><Button type="submit" disabled={busy}>{busy ? "Pricing…" : "Update"}</Button></div>
                <div className="flex flex-wrap gap-1.5">{["Add 20 more guests", "Add live chaat counter", "Make it Jain", "Remove mutton"].map((s) => <button type="button" key={s} onClick={() => change(s)} className="hairline rounded-full px-2.5 py-1 text-xs hover:bg-line/50">{s}</button>)}</div>
                {reply && <p className="whitespace-pre-wrap rounded-xl bg-line/40 p-3 text-sm">{reply}</p>}
              </form>
            )}
          </div>
        )}
      </Card>

      <MarketWidget snap={q.market_snapshot} />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardTitle>What changed</CardTitle>
          <ul className="mt-3 space-y-2 text-xs">
            {bundle.events.slice(0, 8).map((e, i) => (
              <li key={i} className="flex justify-between gap-3"><span><span className="font-medium">{titleCase(e.type)}</span>{Array.isArray(e.payload?.changes) ? <span className="text-muted"> · {(e.payload.changes as string[]).join("; ")}</span> : null}</span>
                <span className="shrink-0 tabular-nums text-muted">{e.per_plate_before && e.per_plate_after ? `${rupees(e.per_plate_before)} → ${rupees(e.per_plate_after)}` : dateShort(e.created_at)}</span></li>
            ))}
          </ul>
        </Card>
        {bundle.payments && (
          <Card>
            <CardTitle>Payments & invoice</CardTitle>
            <ul className="mt-3 space-y-2 text-sm">
              {bundle.payments.length === 0 && <li className="text-muted">An advance confirms your date. Ask Anvi to set it up.</li>}
              {bundle.payments.map((p, i) => <li key={i} className="flex items-center justify-between"><span>{titleCase(p.kind)} · {rupees(p.amount)}</span>{p.status === "paid" ? <Badge tone="good">Paid {dateShort(p.paid_at)}</Badge> : p.payment_link ? <a className="link text-xs" href={p.payment_link}>Pay now</a> : p.provider === "upi" && p.provider_ref ? <Badge tone="warn">Confirming UTR {p.provider_ref}</Badge> : <Badge>Pending</Badge>}</li>)}
            </ul>
            {bundle.upi && <div id="pay" className="mt-4 scroll-mt-24"><UpiPay card={bundle.upi} /></div>}
          </Card>
        )}
      </div>

      {!readOnly && token && (
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={doShare}><Share2 size={14} /> Share with family / office</Button>
          {share && <span className="text-xs text-muted">Tracked link: {share}</span>}
        </div>
      )}

      {bundle.chat && bundle.chat.length > 0 && (
        <Card>
          <CardTitle>Chat history</CardTitle>
          <div className="scroll-thin mt-3 max-h-72 space-y-2 overflow-y-auto">
            {bundle.chat.map((m, i) => <div key={i} className={m.role === "customer" ? "text-right" : ""}><span className={"inline-block max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-xs " + (m.role === "customer" ? "bg-fg text-bg" : "bg-line/50")}>{m.content}</span></div>)}
          </div>
        </Card>
      )}
    </div>
  );
}
