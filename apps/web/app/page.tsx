import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { ChatWidget } from "@/components/chat-widget";
import { Button } from "@/components/ui/button";

const WA = process.env.NEXT_PUBLIC_WA_NUMBER || "919876543210";

const pillars = [
  ["Live Hyderabad pricing", "Every quote is costed from today’s Bowenpally wholesale rates. You see the market benchmark next to our price."],
  ["Festival-smart offers", "Dasara, Diwali, Bathukamma, Ramzan, Sankranti — the best eligible offer is applied automatically and explained plainly."],
  ["Price lock certificate", "Lock your per-plate price till the event. Markets move; your price doesn’t."],
  ["Up to 500 guests", "One kitchen, one standard: halal non-veg, separate veg line, Jain on request, FSSAI licensed."],
];

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-5">
        <section className="grid gap-10 py-16 md:grid-cols-[1.1fr_0.9fr] md:py-24">
          <div className="flex flex-col justify-center gap-6">
            <span className="label">WhatsApp-first · Hyderabad & Secunderabad</span>
            <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl">Catering priced on today’s market. Planned in one chat.</h1>
            <p className="max-w-lg text-base text-muted md:text-lg">Tell Anvi the occasion, date and guest count. Get three complete packages with live per-plate prices, tweak anything in seconds, lock the price, done.</p>
            <div className="flex flex-wrap gap-3">
              <a href={`https://wa.me/${WA}?text=Hi%20Anvi%2C%20I%27d%20like%20to%20plan%20a%20catering%20menu`} target="_blank" rel="noreferrer"><Button size="lg">Chat on WhatsApp</Button></a>
              <Link href="/portal"><Button size="lg" variant="secondary">Open my quote</Button></Link>
            </div>
            <dl className="mt-4 grid grid-cols-3 gap-6 border-t border-line pt-6 text-sm">
              <div><dt className="label">Response</dt><dd className="mt-1 font-medium">Under a minute</dd></div>
              <div><dt className="label">Guests</dt><dd className="mt-1 font-medium">25 – 500</dd></div>
              <div><dt className="label">Menus</dt><dd className="mt-1 font-medium">Veg · Non-veg · Jain</dd></div>
            </dl>
          </div>
          <div><ChatWidget inline /></div>
        </section>
        <section className="grid gap-4 border-t border-line py-14 md:grid-cols-4">
          {pillars.map(([t, d]) => (
            <div key={t} className="space-y-2"><h3 className="text-sm font-semibold">{t}</h3><p className="text-sm text-muted">{d}</p></div>
          ))}
        </section>
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line py-8 text-xs text-muted">
          <span>© {new Date().getFullYear()} Hyderabad Elite Catering · FSSAI licensed · GST extra</span>
          <span>Your data is stored with consent (DPDP). Reply STOP anytime.</span>
        </footer>
      </main>
    </>
  );
}
