"use client";
import { useState } from "react";
import { Check, Copy, Smartphone } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** What the API returns beside a pending advance when UPI is configured. */
export type UpiCard = {
  type: "upi";
  amount: string;
  quote_number: string;
  payment_id: string;
  payee: string;
  vpa: string | null;
  phone: string | null;
  link: string | null;
  qr_svg: string | null;
  claim_url: string | null;
  apps: string[];
  claimed_utr?: string | null;
};

const inr = (n: string) => "₹" + Number(n).toLocaleString("en-IN");

/**
 * The pay-by-UPI card. On a phone the button opens PhonePe/GPay with the amount filled in;
 * on a laptop the QR does the same from the camera. Either way the customer ends by typing
 * the UTR their app shows, which is what lets the owner confirm in one tap.
 */
export function UpiPay({ card, compact = false, onClaimed }: { card: UpiCard; compact?: boolean; onClaimed?: (utr: string) => void }) {
  const [utr, setUtr] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">(card.claimed_utr ? "done" : "idle");
  const [err, setErr] = useState<string | null>(null);
  const clean = utr.replace(/\D/g, "");

  async function claim() {
    if (clean.length !== 12 || !card.claim_url) return;
    setState("busy"); setErr(null);
    try {
      await api(card.claim_url, { method: "POST", auth: false, body: JSON.stringify({ utr: clean, payment_id: card.payment_id }) });
      setState("done"); onClaimed?.(clean);
    } catch (e) {
      setState("error"); setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className={cn("upi-card overflow-hidden rounded-2xl border border-line bg-card text-fg shadow-soft", compact ? "max-w-[340px]" : "")}>
      <div className="flex items-start justify-between gap-3 border-b border-line/70 px-4 py-3">
        <div>
          <div className="label">Advance to confirm your date</div>
          <div className="mt-0.5 text-2xl font-semibold tabular-nums tracking-tight">{inr(card.amount)}</div>
        </div>
        <div className="text-right text-[11px] leading-tight text-muted">{card.quote_number}<br />to {card.payee}</div>
      </div>

      {state === "done" ? (
        <div className="flex items-start gap-3 px-4 py-4">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-good/15 text-good"><Check size={16} /></span>
          <div className="text-sm">
            <div className="font-medium">Payment noted — we’re confirming it</div>
            <p className="mt-0.5 text-muted">UTR {card.claimed_utr ?? clean}. Our team checks it in the app and you’ll see “Paid” here within minutes.</p>
          </div>
        </div>
      ) : (
        <>
          <div className={cn("grid gap-4 px-4 py-4", compact ? "" : "sm:grid-cols-[auto_1fr]")}>
            {card.qr_svg && (
              <div className={cn("mx-auto rounded-xl border border-line bg-white p-2 text-black", compact ? "w-40" : "w-44")} aria-label="UPI QR code" dangerouslySetInnerHTML={{ __html: card.qr_svg }} />
            )}
            <div className="flex flex-col justify-center gap-2.5">
              {card.link && (
                <a href={card.link} className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-fg px-5 text-sm font-medium text-bg transition-transform hover:-translate-y-px active:translate-y-0">
                  <Smartphone size={15} /> Pay with any UPI app
                </a>
              )}
              <p className="text-center text-[11px] text-muted sm:text-left">{card.apps.join(" · ")}. {card.qr_svg ? "On a laptop, scan the code with your phone." : ""}</p>
              {card.vpa && <CopyRow label="UPI ID" value={card.vpa} />}
              {card.phone && <CopyRow label="Or pay to number" value={card.phone} />}
            </div>
          </div>
          {card.claim_url && (
            <div className="border-t border-line/70 px-4 py-3">
              <label className="label" htmlFor={`utr-${card.payment_id}`}>After paying, enter the 12-digit UTR from your app</label>
              <div className="mt-1.5 flex gap-2">
                <input id={`utr-${card.payment_id}`} inputMode="numeric" value={utr} onChange={(e) => setUtr(e.target.value)} placeholder="e.g. 425512345678" maxLength={14}
                       className="h-10 flex-1 rounded-xl border border-line bg-bg px-3 font-mono text-sm tabular-nums outline-none focus:border-fg/40" />
                <button onClick={claim} disabled={clean.length !== 12 || state === "busy"} className="h-10 rounded-xl bg-fg px-4 text-sm font-medium text-bg disabled:opacity-40">
                  {state === "busy" ? "Sending…" : "I’ve paid"}
                </button>
              </div>
              {err && <p className="mt-1.5 text-xs text-bad">{err}</p>}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function CopyRow({ label, value }: { label: string; value: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button type="button" onClick={async () => { try { await navigator.clipboard.writeText(value); setOk(true); setTimeout(() => setOk(false), 1500); } catch {} }}
            className="group flex items-center justify-between gap-3 rounded-xl border border-line bg-bg-2/60 px-3 py-2 text-left transition-colors hover:border-fg/30">
      <span><span className="label block">{label}</span><span className="font-mono text-sm">{value}</span></span>
      <span className="text-muted group-hover:text-fg">{ok ? <Check size={14} className="text-good" /> : <Copy size={14} />}</span>
    </button>
  );
}
