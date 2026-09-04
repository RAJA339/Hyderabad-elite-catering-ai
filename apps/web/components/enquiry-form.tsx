"use client";
import { useState } from "react";
import { ArrowRight, Check, PhoneCall } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const OCCASIONS = ["Wedding", "Reception", "Housewarming", "Birthday", "Corporate", "Engagement", "Naming ceremony", "Other"];

/**
 * For the customer who would rather be called than chat. Six fields, one tap, and the owner
 * is told on every configured channel within a second. The details land in the same lead
 * Anvi uses, so if they open the chat next, she already knows them.
 */
export function EnquiryForm() {
  const [f, setF] = useState({ name: "", phone: "", email: "", occasion: "", event_date: "", guests: "", diet: "veg", message: "" });
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("busy"); setErr(null);
    try {
      await api("/api/public/enquiry", { method: "POST", auth: false, body: JSON.stringify({ ...f, guests: f.guests ? Number(f.guests) : null }) });
      setState("done");
    } catch (ex) {
      setState("error"); setErr(ex instanceof Error ? ex.message : String(ex));
    }
  }

  return (
    <section id="enquire" className="mx-auto max-w-6xl scroll-mt-24 px-5 pb-24">
      <div className="card grid gap-8 overflow-hidden p-7 md:grid-cols-[0.9fr_1.1fr] md:p-10">
        <div className="flex flex-col justify-between">
          <div>
            <span className="label flex items-center gap-2"><span className="h-px w-6 bg-accent" /> Prefer a call?</span>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">Leave the basics. <span className="display-italic text-muted">We</span> call you.</h2>
            <p className="mt-4 max-w-md text-[15px] leading-relaxed text-muted">Six fields. The owner is alerted the moment you press send, and calls back within two hours between 9am and 9pm. Anvi keeps a priced menu ready for when you pick up.</p>
          </div>
          <dl className="mt-8 grid grid-cols-3 gap-4 border-t border-line/80 pt-5 text-sm">
            <div><dt className="label">Callback</dt><dd className="mt-1 font-medium">Under 2 hours</dd></div>
            <div><dt className="label">Hours</dt><dd className="mt-1 font-medium">9am – 9pm</dd></div>
            <div><dt className="label">Your data</dt><dd className="mt-1 font-medium">Consent-first</dd></div>
          </dl>
        </div>

        {state === "done" ? (
          <div className="flex flex-col items-start justify-center gap-4 rounded-2xl border border-line bg-bg-2/60 p-7">
            <span className="grid h-11 w-11 place-items-center rounded-full bg-good/15 text-good"><Check size={20} /></span>
            <h3 className="text-xl font-semibold tracking-tight">Got it, {f.name.split(" ")[0] || "thank you"}.</h3>
            <p className="text-[15px] leading-relaxed text-muted">The owner has your details and will call {f.phone}. If you’d like the menu and price before that, Anvi can do it now — she already knows what you told us.</p>
            <a href="#chat" className="inline-flex items-center gap-1.5 text-sm font-medium hover:text-accent">Price it with Anvi <ArrowRight size={14} /></a>
          </div>
        ) : (
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            <Field label="Your name"><Input value={f.name} onChange={set("name")} placeholder="Full name" required autoComplete="name" /></Field>
            <Field label="Phone"><Input value={f.phone} onChange={set("phone")} placeholder="+91 98765 43210" required inputMode="tel" autoComplete="tel" /></Field>
            <Field label="Email (optional)"><Input type="email" value={f.email} onChange={set("email")} placeholder="For the quote PDF" autoComplete="email" /></Field>
            <Field label="Occasion">
              <select value={f.occasion} onChange={set("occasion")} required className="hairline h-10 w-full rounded-xl bg-bg px-3 text-sm outline-none focus:border-fg/40">
                <option value="" disabled>Choose…</option>
                {OCCASIONS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </Field>
            <Field label="Event date"><Input type="date" value={f.event_date} onChange={set("event_date")} /></Field>
            <Field label="Guests">
              <div className="flex gap-2">
                <Input value={f.guests} onChange={set("guests")} placeholder="120" inputMode="numeric" className="flex-1" />
                <select value={f.diet} onChange={set("diet")} className="hairline h-10 rounded-xl bg-bg px-3 text-sm outline-none">
                  <option value="veg">Veg</option><option value="non_veg">Non-veg</option><option value="mixed">Mixed</option><option value="jain">Jain</option>
                </select>
              </div>
            </Field>
            <div className="sm:col-span-2">
              <Field label="Anything else (optional)">
                <textarea value={f.message} onChange={set("message")} rows={2} placeholder="Venue, budget per plate, live counters you have in mind…" className="hairline w-full resize-none rounded-xl bg-bg px-3 py-2 text-sm outline-none focus:border-fg/40" />
              </Field>
            </div>
            {err && <p className="text-xs text-bad sm:col-span-2">{err}</p>}
            <div className="flex items-center justify-between gap-3 sm:col-span-2">
              <p className="text-[11px] text-muted">By sending, you agree we may contact you about this event and store these details (DPDP).</p>
              <Button type="submit" size="lg" className="group gap-2 pr-4" disabled={state === "busy"}>
                <PhoneCall size={15} /> {state === "busy" ? "Sending…" : "Request a call"} <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
              </Button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="label mb-1.5 block">{label}</span>{children}</label>;
}
