import Link from "next/link";
import { ArrowRight, ShieldCheck, Sparkles, TrendingUp, Users } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { ChatWidget } from "@/components/chat-widget";
import { MarketTicker } from "@/components/market-ticker";
import { SignatureTable } from "@/components/signature-table";
import { Button } from "@/components/ui/button";

const WA = process.env.NEXT_PUBLIC_WA_NUMBER || "919876543210";

const steps = [
  ["01", "Tell Anvi the basics", "Occasion, date, guest count, veg or non-veg. Three to five messages, no forms."],
  ["02", "Get three priced menus", "Classic, Signature and Royal — each costed on today’s Bowenpally wholesale rates with the market benchmark beside it."],
  ["03", "Tweak, lock, done", "Add guests, remove mutton, make it Jain. The price updates instantly. Lock it and it can’t rise before your event."],
];

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main className="relative">
        {/* Hero */}
        <section className="grain glow-hero relative overflow-hidden">
          <div className="relative z-[1] mx-auto grid max-w-6xl gap-10 px-5 pb-14 pt-12 md:grid-cols-[1.05fr_0.95fr] md:pb-20 md:pt-20 lg:gap-16">
            <div className="flex flex-col justify-center">
              <span className="reveal reveal-1 label flex items-center gap-2"><span className="h-px w-6 bg-accent" /> WhatsApp-first · Hyderabad &amp; Secunderabad</span>
              <h1 className="reveal reveal-2 mt-5 text-[2.75rem] font-semibold leading-[0.98] tracking-[-0.03em] sm:text-6xl lg:text-[4.6rem]">
                Catering priced on <span className="display-italic text-accent">today’s</span> market.<br className="hidden sm:block" /> Planned in one chat.
              </h1>
              <p className="reveal reveal-3 mt-6 max-w-lg text-[17px] leading-relaxed text-muted">
                Anvi qualifies your event, designs three complete menus, prices them on live ingredient rates, and locks the number — before you finish your chai.
              </p>
              <div className="reveal reveal-4 mt-8 flex flex-wrap items-center gap-3">
                <a href={`https://wa.me/${WA}?text=Hi%20Anvi%2C%20I%27d%20like%20to%20plan%20a%20catering%20menu`} target="_blank" rel="noreferrer">
                  <Button size="lg" className="group gap-2 pr-4">Chat on WhatsApp <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" /></Button>
                </a>
                <Link href="/portal"><Button size="lg" variant="secondary">Open my quote</Button></Link>
              </div>
              <dl className="reveal reveal-5 mt-10 grid max-w-md grid-cols-3 gap-6 border-t border-line/80 pt-6">
                <div><dt className="label">Response</dt><dd className="mt-1 text-sm font-medium">Under a minute</dd></div>
                <div><dt className="label">Guests</dt><dd className="mt-1 text-sm font-medium tabular-nums">25 – 500</dd></div>
                <div><dt className="label">Menus</dt><dd className="mt-1 text-sm font-medium">Veg · Non-veg · Jain</dd></div>
              </dl>
            </div>
            <div id="chat" className="reveal reveal-3 relative scroll-mt-24">
              <div className="pointer-events-none absolute -inset-6 -z-10 rounded-[32px] bg-[radial-gradient(closest-side,rgb(var(--glow)/0.25),transparent)] blur-2xl" />
              <ChatWidget inline />
            </div>
          </div>
        </section>

        <MarketTicker />

        <SignatureTable />

        {/* How it works */}
        <section className="mx-auto max-w-6xl px-5 py-20">
          <div className="mb-10 flex items-end justify-between gap-6">
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Three messages. <span className="display-italic text-muted">One</span> finished quote.</h2>
            <span className="label hidden sm:block">How it works</span>
          </div>
          <ol className="grid gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-3">
            {steps.map(([n, t, d]) => (
              <li key={n} className="group bg-card p-7 transition-colors hover:bg-bg-2">
                <span className="display text-4xl text-muted/70 transition-colors group-hover:text-accent">{n}</span>
                <h3 className="mt-5 text-lg font-semibold tracking-tight">{t}</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-muted">{d}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Pillars — bento */}
        <section className="mx-auto max-w-6xl px-5 pb-24">
          <div className="grid gap-4 md:grid-cols-6">
            <div className="card relative overflow-hidden p-7 md:col-span-4">
              <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />
              <div className="flex items-center gap-2 text-accent"><TrendingUp size={16} /><span className="label !text-accent">The moat</span></div>
              <h3 className="mt-4 text-2xl font-semibold tracking-tight">Every dish is a recipe. Every recipe is priced on this morning’s market.</h3>
              <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-muted">Chicken, onion, paneer, rice — we ingest Hyderabad wholesale rates hourly and recost the whole menu. You see our price beside the market benchmark. When costs spike we say so, and offer a smarter swap instead of a quiet mark-up.</p>
              <div className="mt-6 grid max-w-md grid-cols-3 gap-4 rounded-xl border border-line bg-bg-2/60 p-4">
                <div><div className="label">Our price</div><div className="mt-1 text-xl font-semibold tabular-nums">₹485</div></div>
                <div><div className="label">Market</div><div className="mt-1 text-xl font-semibold tabular-nums text-muted line-through decoration-muted/50">₹518</div></div>
                <div><div className="label">Food cost</div><div className="mt-1 text-xl font-semibold tabular-nums">₹269</div></div>
              </div>
              <p className="mt-2 text-[11px] text-muted">Signature veg · 120 guests · per plate, illustrative</p>
            </div>
            <div className="card flex flex-col p-7 md:col-span-2">
              <Sparkles size={18} className="text-accent" />
              <h3 className="mt-4 text-lg font-semibold tracking-tight">Festival-smart offers</h3>
              <p className="mt-2 flex-1 text-[15px] leading-relaxed text-muted">Dasara, Diwali, Bathukamma, Ramzan, Sankranti. The best eligible offer is applied automatically and explained in one plain sentence — never one that loses us money.</p>
            </div>
            <div className="card flex flex-col p-7 md:col-span-2">
              <ShieldCheck size={18} className="text-accent" />
              <h3 className="mt-4 text-lg font-semibold tracking-tight">Price-lock certificate</h3>
              <p className="mt-2 flex-1 text-[15px] leading-relaxed text-muted">Lock your per-plate price until the event. Markets move; your number doesn’t. Big bookings get a signed certificate.</p>
            </div>
            <div className="card flex flex-col p-7 md:col-span-2">
              <Users size={18} className="text-accent" />
              <h3 className="mt-4 text-lg font-semibold tracking-tight">Up to 500 guests</h3>
              <p className="mt-2 flex-1 text-[15px] leading-relaxed text-muted">One kitchen, one standard. Halal non-veg, a separate veg line, Jain on request. FSSAI licensed.</p>
            </div>
            <div className="card flex flex-col justify-between p-7 md:col-span-2">
              <div><div className="label">Client portal</div><h3 className="mt-3 text-lg font-semibold tracking-tight">Your quote, live, on one link</h3><p className="mt-2 text-[15px] leading-relaxed text-muted">Change the menu, watch the price move, pay the advance, share with family.</p></div>
              <Link href="/portal" className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium hover:text-accent">Open portal <ArrowRight size={14} /></Link>
            </div>
          </div>
        </section>

        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-8 text-xs text-muted">
            <span>© {new Date().getFullYear()} Hyderabad Elite Catering · FSSAI licensed · GST extra</span>
            <span>Your data is stored with consent (DPDP). Reply STOP anytime.</span>
          </div>
        </footer>
      </main>
    </>
  );
}
