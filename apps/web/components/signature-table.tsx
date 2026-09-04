import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { BainganArt, BiryaniArt, ChaiArt, HaleemArt, MeethaArt } from "@/components/dish-art";

/**
 * The signature-dish gallery on the landing page.
 *
 * Each dish is drawn (see dish-art.tsx), so the section renders identically in both themes,
 * weighs a few kilobytes and never shows a broken image. When photography is ready, drop the
 * file at public/food/<slug>.jpg and set `photo` below: the photo takes the art's place and
 * the caption, palette and layout stay exactly as they are.
 */
type Dish = {
  slug: string;
  name: string;
  tagline: string;
  method: string;
  from: number; // illustrative per-plate share, ₹
  wash: [string, string]; // warm ground behind the art: light theme, dark theme
  Art: (p: { id?: string }) => React.JSX.Element;
  photo?: string;
  feature?: boolean;
};

const dishes: Dish[] = [
  { slug: "dum-biryani", name: "Kacchi Dum Biryani", tagline: "The reason Hyderabad is Hyderabad.", method: "Raw marinated mutton under saffron basmati, sealed with dough, three hours on dum. Bowenpally mutton, priced this morning.", from: 185, wash: ["#F3D9A8", "#3A2410"], Art: BiryaniArt, feature: true },
  { slug: "haleem", name: "Haleem", tagline: "Twelve hours. One pot.", method: "Wheat, lentils and mutton pounded to silk, finished with ghee, birista and lime. Ramzan-season pricing applied automatically.", from: 120, wash: ["#EFC9A0", "#33200E"], Art: HaleemArt },
  { slug: "bagara-baingan", name: "Bagara Baingan", tagline: "The gravy that finishes the biryani.", method: "Baby aubergines in a peanut, sesame and tamarind masala. Sits beside every non-veg and veg menu.", from: 55, wash: ["#EFC2A6", "#33170F"], Art: BainganArt },
  { slug: "double-ka-meetha", name: "Double ka Meetha", tagline: "Bread, ghee, saffron, patience.", method: "Fried bread soaked in reduced saffron milk, dressed with pistachio and silver leaf. The dessert that ends every wedding.", from: 45, wash: ["#F6E3BC", "#3A2A12"], Art: MeethaArt },
  { slug: "irani-chai", name: "Irani Chai & Osmania", tagline: "How every meeting in this city ends.", method: "Thick, sweet, dum-brewed tea with a salty-sweet Osmania biscuit. Served at the end of every plated service.", from: 25, wash: ["#EAD6C0", "#2E2117"], Art: ChaiArt },
];

export function SignatureTable() {
  return (
    <section className="mx-auto max-w-6xl px-5 pt-20" aria-labelledby="table-heading">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <span className="label flex items-center gap-2"><span className="h-px w-6 bg-accent" /> The Hyderabad table</span>
          <h2 id="table-heading" className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
            Cooked the old way. <span className="display-italic text-muted">Priced</span> the new way.
          </h2>
        </div>
        <p className="max-w-sm text-[15px] leading-relaxed text-muted">Every dish below is a recipe with a live cost. The per-plate figure is what the ingredients ran this morning — not a menu printed last year.</p>
      </div>

      <ul className="grid gap-4 md:grid-cols-6">
        {dishes.map((d, i) => <DishTile key={d.slug} d={d} index={i} />)}
      </ul>

      <p className="mt-4 text-[11px] text-muted">Per-plate figures are the dish’s share of a Signature menu for 120 guests, illustrative. Anvi quotes the live number.</p>
    </section>
  );
}

function DishTile({ d, index }: { d: Dish; index: number }) {
  const style = { "--wash": d.wash[0], "--wash-dark": d.wash[1] } as React.CSSProperties;
  const Art = d.Art;
  const art = d.photo ? (
    <Image src={d.photo} alt={d.name} fill sizes={d.feature ? "(min-width: 768px) 40vw, 100vw" : "(min-width: 768px) 33vw, 100vw"} className="object-cover transition-transform duration-[1400ms] ease-out group-hover:scale-[1.03]" />
  ) : (
    <Art id={d.slug} />
  );
  const caption = (
    <div className="flex flex-col p-6 md:p-7">
      <div className="flex items-center gap-3">
        <span className="display text-2xl text-muted/70 transition-colors group-hover:text-accent">{String(index + 1).padStart(2, "0")}</span>
        <span className="h-px flex-1 bg-line" />
        <span className="label">from</span>
        <span className="text-sm font-semibold tabular-nums">₹{d.from}</span>
      </div>
      <h3 className={["mt-3 font-semibold tracking-tight", d.feature ? "text-3xl sm:text-4xl" : "text-xl"].join(" ")}>{d.name}</h3>
      <p className="display-italic mt-1 text-lg text-muted">{d.tagline}</p>
      <p className="mt-3 max-w-md text-[14px] leading-relaxed text-muted">{d.method}</p>
      {d.feature && (
        <Link href="#chat" className="mt-6 inline-flex w-fit items-center gap-1.5 text-sm font-medium hover:text-accent">Ask Anvi to price it <ArrowUpRight size={14} /></Link>
      )}
    </div>
  );

  if (d.feature) {
    return (
      <li style={style} className="dish group relative overflow-hidden rounded-2xl border border-line bg-card shadow-soft transition-shadow hover:shadow-lift md:col-span-6 lg:col-span-4">
        <div className="grid h-full md:grid-cols-[1fr_1.05fr]">
          <div className="order-2 flex flex-col justify-end md:order-1">{caption}</div>
          <div className="dish-stage dish-stage-lg order-1 relative min-h-[320px] md:order-2 md:min-h-[480px]">{art}</div>
        </div>
      </li>
    );
  }
  return (
    <li style={style} className="dish group relative overflow-hidden rounded-2xl border border-line bg-card shadow-soft transition-shadow hover:shadow-lift md:col-span-3 lg:col-span-2">
      <div className="dish-stage relative aspect-[4/3] lg:aspect-[5/4]">{art}</div>
      {caption}
    </li>
  );
}
