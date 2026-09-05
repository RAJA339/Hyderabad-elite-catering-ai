"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { api, type MenuCatalog } from "@/lib/api";
import { rupees } from "@/lib/format";

/** The nine cards on the landing page, priced live. Each opens the builder on that card. */
export function MenusSection() {
  const [cat, setCat] = useState<MenuCatalog | null>(null);
  useEffect(() => { api<MenuCatalog>("/api/public/menu", { auth: false }).then(setCat).catch(() => setCat(null)); }, []);
  const groups = [["veg", "Veg"], ["non_veg", "Non-veg"]] as const;
  return (
    <section id="menus" className="mx-auto max-w-6xl scroll-mt-24 px-5 pt-20" aria-labelledby="menus-heading">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <span className="label flex items-center gap-2"><span className="h-px w-6 bg-accent" /> Amma chethi vanta</span>
          <h2 id="menus-heading" className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">Nine complete menus. <span className="display-italic text-muted">One</span> honest price each.</h2>
        </div>
        <p className="max-w-sm text-[15px] leading-relaxed text-muted">Rice, curries, chutneys, a sweet, a snack, disposables — all in the plate. Priced this morning on Bowenpally rates, for 100 guests. Bigger events pay less per plate.</p>
      </div>
      {groups.map(([diet, label]) => {
        const list = (cat?.packages ?? []).filter((p) => p.diet === diet);
        return (
          <div key={diet} className="mb-8">
            <div className="mb-3 flex items-center gap-3"><span className="label">{label}</span><span className="h-px flex-1 bg-line" /></div>
            <ul className={["grid gap-3 sm:grid-cols-2", diet === "veg" ? "lg:grid-cols-5" : "lg:grid-cols-4"].join(" ")}>
              {(list.length ? list : Array.from({ length: diet === "veg" ? 5 : 4 }, (_, i) => null as null | (typeof list)[number] & {})).map((p, i) => (
                <li key={p?.key ?? i}>
                  {p ? (
                    <Link href={`/menu?package=${p.key}`} className="group flex h-full flex-col rounded-2xl border border-line bg-card p-5 transition-all hover:-translate-y-px hover:border-fg/40 hover:shadow-soft">
                      <div className="flex items-center gap-2"><span className="display text-2xl text-muted/70 transition-colors group-hover:text-accent">{String(i + 1).padStart(2, "0")}</span><span className="h-px flex-1 bg-line" /><ArrowUpRight size={14} className="text-muted transition-colors group-hover:text-accent" /></div>
                      <h3 className="mt-3 text-lg font-semibold tracking-tight">{p.name}</h3>
                      <p className="display-italic mt-0.5 flex-1 text-[15px] text-muted">{p.tagline}</p>
                      <div className="mt-4 flex items-end gap-2">
                        <span className="text-2xl font-semibold tabular-nums">{p.from_per_plate ? rupees(p.from_per_plate) : "—"}</span><span className="mb-1 text-xs text-muted">/ plate</span>
                        {p.list_price && p.from_per_plate && Number(p.from_per_plate) < Number(p.list_price) && <span className="mb-1 text-xs tabular-nums text-muted line-through decoration-muted/60">{rupees(p.list_price)}</span>}
                      </div>
                      <p className="mt-1 text-xs text-muted">{p.item_count} items{p.slots.length ? ` · ${p.slots.length} choices` : ""}</p>
                    </Link>
                  ) : <div className="shimmer h-44 rounded-2xl" />}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <Link href="/menu" className="inline-flex items-center gap-1.5 text-sm font-medium hover:text-accent">Open the menu builder <ArrowUpRight size={14} /></Link>
    </section>
  );
}
