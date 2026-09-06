import Link from "next/link";
import { ArrowRight, ArrowUpRight, ChefHat, ShieldCheck, Sparkles, Utensils } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { ChatWidget } from "@/components/chat-widget";
import { MarketTicker } from "@/components/market-ticker";
import { SignatureTable } from "@/components/signature-table";
import { MenusSection } from "@/components/menus-section";
import { EnquiryForm } from "@/components/enquiry-form";
import { FoodScene } from "@/components/food-scene";

const WA = (process.env.NEXT_PUBLIC_WA_NUMBER || "").replace(/\D/g, "");
const steps = [
  ["01", "Dream up the occasion.", "A wedding, a housewarming, a lunch for your team. Tell Anvi your date, guest count and dietary preferences."],
  ["02", "Make the menu yours.", "Explore our complete menus or build your own. Compare per-plate prices based on Hyderabad ingredient rates."],
  ["03", "Bring everyone together.", "Fine-tune your selection, confirm your quote and arrange your celebration with our team."],
];

export default function Home() {
  return <div className="elite-home">
    <SiteHeader />
    <main id="main-content">
      <section className="elite-hero" aria-labelledby="hero-heading">
        <div className="hero-copy">
          <p className="eyebrow reveal">HYDERABAD & SECUNDERABAD <span /> MADE TO CELEBRATE</p>
          <h1 id="hero-heading" className="reveal reveal-2">A feast for<br />the <em>unforgettable.</em></h1>
          <p className="hero-description reveal reveal-3">The warmth of a Hyderabadi welcome. The richness of a table made just for you. Exceptional food, thoughtfully planned.</p>
          <div className="hero-actions reveal reveal-4"><Link href="/menu" className="gold-button">Discover our menus <ArrowUpRight size={18} /></Link><a href={WA ? `https://wa.me/${WA}?text=Hi%2C%20I%27d%20like%20to%20plan%20a%20catering%20menu` : "#chat"} className="text-button" {...(WA ? { target: "_blank", rel: "noreferrer" } : {})}>{WA ? "Plan on WhatsApp" : "Plan with Anvi"}<ArrowRight size={17} /></a></div>
          <div className="hero-details reveal reveal-5"><div><strong>25—500</strong><span>guests, beautifully hosted</span></div><div><strong>One table. Every taste.</strong><span>Vegetarian · Non-veg · Jain</span></div></div>
        </div>
        <FoodScene />
        <div className="hero-bottom"><span>ROOTED IN TRADITION. CRAFTED FOR YOUR OCCASION.</span><a href="#table">Explore the table <span>↓</span></a></div>
      </section>
      <div className="occasion-strip" aria-label="Catering occasions"><span>WEDDINGS</span><i>✦</i><span>HOUSEWARMINGS</span><i>✦</i><span>CORPORATE GATHERINGS</span><i>✦</i><span>EVERY REASON TO CELEBRATE</span></div>
      <SignatureTable />
      <section className="promise-section"><div><p className="eyebrow">THE ELITE WAY</p><h2>Generous hospitality.<br /><em>Thoughtful in every detail.</em></h2></div><div className="promise-grid">{[
        [ChefHat, "A taste of home", "Hyderabadi favourites and Telugu classics, brought together in complete menus."],
        [Utensils, "A place for everyone", "Vegetarian and non-vegetarian menus, with Jain options on request."],
        [ShieldCheck, "Clarity in every quote", "See your menu and per-plate price. Review your event details in your client portal."],
      ].map(([Icon, title, copy]) => { const Symbol = Icon as typeof ChefHat; return <div className="promise-item" key={String(title)}><Symbol size={24} strokeWidth={1.3} /><h3>{String(title)}</h3><p>{String(copy)}</p></div>; })}</div></section>
      <MenusSection />
      <div className="market-wrap"><MarketTicker /></div>
      <section className="planning-section"><div className="planning-heading"><p className="eyebrow">FROM THE FIRST HELLO TO THE LAST BITE</p><h2>Your occasion.<br /><em>Effortlessly planned.</em></h2></div><ol>{steps.map(([n, title, copy]) => <li key={n}><span>{n}</span><div><h3>{title}</h3><p>{copy}</p></div></li>)}</ol></section>
      <section id="chat" className="concierge-section"><div><p className="eyebrow"><Sparkles size={16} /> MEET YOUR MENU CONCIERGE</p><h2>A beautiful gathering<br />starts with <em>a hello.</em></h2><p>Meet Anvi, your catering assistant. Share what you have in mind, explore menus and work out the details at your own pace.</p><Link className="text-button" href="/portal">Already planning with us? Open your portal <ArrowUpRight size={17} /></Link></div><ChatWidget inline /></section>
      <EnquiryForm />
    </main>
    <footer className="elite-footer"><div className="footer-top"><Link href="/" className="footer-wordmark">Hyderabad<br /><em>Elite Catering.</em></Link><div><p>GOOD FOOD. GREAT COMPANY.<br />MEMORIES THAT STAY.</p><a className="text-button" href="#enquire">Let’s plan your gathering <ArrowUpRight size={18} /></a></div></div><div className="footer-bottom"><span>© {new Date().getFullYear()} Hyderabad Elite Catering</span><nav aria-label="Footer"><Link href="/menu">Menus</Link><Link href="/portal">Client portal</Link><Link href="/admin">Admin</Link></nav><span>Hyderabad & Secunderabad · GST extra</span></div></footer>
  </div>;
}
