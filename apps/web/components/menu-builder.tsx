"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, Leaf, Minus, Plus, RotateCcw, Sparkles } from "lucide-react";
import { api, type MenuCatalog, type MenuPackage, type MenuSelection, type PricedMenu } from "@/lib/api";
import { rupees, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/**
 * The owner's nine cards as a builder. Pick a card, the plate appears as printed; every
 * "[or]" line on the card is a choice; anything else on the menu can be added; the price
 * re-computes on today's rates as you go. Enter a phone number and the plate becomes a live
 * quote on the customer's own portal link, with the owner alerted.
 *
 * Money shown here is what the API returns; the page never computes a rupee itself.
 */

const CAT_LABEL: Record<string, string> = {
  welcome_drinks: "Welcome drinks", starters: "Starters", main_veg: "Curries", main_nonveg: "Non-veg", rice_breads: "Rice & breads",
  sides: "Chutneys & sides", live_counters: "Live counters", desserts: "Sweets", service: "Service",
};
const GUEST_STEPS = [25, 50, 75, 100, 150, 200, 300, 400, 500];
const CHIP = "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all";
const chip = (on: boolean, tone: "fg" | "good" = "fg") => cn(CHIP, on ? (tone === "good" ? "border-good bg-good/10 text-good" : "border-fg bg-fg text-bg") : "border-line bg-card hover:-translate-y-px hover:border-fg/40 hover:shadow-soft");
const OCCASIONS = ["Wedding", "Reception", "Engagement", "Housewarming", "Birthday", "Corporate", "Pooja", "Other"];

export function MenuBuilder({ initialPackage }: { initialPackage?: string }) {
  const [cat, setCat] = useState<MenuCatalog | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [diet, setDiet] = useState<"veg" | "non_veg">("veg");
  const [key, setKey] = useState<string | null>(initialPackage ?? null);
  const [guests, setGuests] = useState(100);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [add, setAdd] = useState<string[]>([]);
  const [remove, setRemove] = useState<string[]>([]);
  const [jain, setJain] = useState(false);
  const [priced, setPriced] = useState<PricedMenu | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<MenuCatalog>("/api/public/menu", { auth: false }).then((c) => {
      setCat(c);
      const first = initialPackage && c.packages.find((p) => p.key === initialPackage);
      if (first) setDiet(first.diet === "non_veg" ? "non_veg" : "veg");
    }).catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [initialPackage]);

  const pkg = useMemo(() => cat?.packages.find((p) => p.key === key) ?? null, [cat, key]);
  const dishes = useMemo(() => Object.fromEntries((cat?.dishes ?? []).map((d) => [d.slug, d])), [cat]);
  const visible = useMemo(() => (cat?.packages ?? []).filter((p) => p.diet === diet), [cat, diet]);

  function choose(p: MenuPackage) {
    setKey(p.key); setChoices({}); setAdd([]); setRemove([]); setPriced(null);
    if (p.diet === "veg") setJain(false);
    if (typeof window !== "undefined") window.history.replaceState(null, "", `/menu?package=${p.key}`);
  }

  // Price on every change, debounced so a guest stepper tap does not fire ten requests.
  const seq = useRef(0);
  useEffect(() => {
    if (!pkg) return;
    const n = ++seq.current;
    setBusy(true);
    const t = setTimeout(async () => {
      try {
        const body: MenuSelection = { package_key: pkg.key, guest_count: guests, choices, add, remove, diet: jain ? "jain" : null };
        const r = await api<PricedMenu>("/api/public/menu/price", { method: "POST", auth: false, body: JSON.stringify(body) });
        if (n === seq.current) { setPriced(r); setErr(null); }
      } catch (e) {
        if (n === seq.current) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (n === seq.current) setBusy(false);
      }
    }, 220);
    return () => clearTimeout(t);
  }, [pkg, guests, choices, add, remove, jain]);

  if (err && !cat) return <p className="mx-auto max-w-xl whitespace-pre-wrap px-5 py-16 text-center text-sm text-muted">{err}</p>;
  if (!cat) return <div className="mx-auto max-w-6xl px-5 py-16"><div className="shimmer h-40 rounded-2xl" /></div>;

  return (
    <div className="mx-auto max-w-6xl px-5 pb-32 lg:pb-24">
      {/* Diet switch + cards */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="hairline inline-flex rounded-full bg-card p-1 text-sm">
          {(["veg", "non_veg"] as const).map((d) => (
            <button key={d} onClick={() => { setDiet(d); const first = cat.packages.find((p) => p.diet === d); if (first && pkg?.diet !== d) choose(first); }}
              className={cn("rounded-full px-4 py-1.5 font-medium transition-colors", diet === d ? "bg-fg text-bg" : "text-muted hover:text-fg")}>
              {d === "veg" ? "Veg" : "Non-veg"}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted">Per-plate prices are for {cat.packages[0]?.indicative_guests ?? 100} guests on today’s wholesale rates. GST extra.</p>
      </div>

      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {visible.map((p, i) => {
          const active = p.key === key;
          return (
            <li key={p.key}>
              <button onClick={() => choose(p)} className={cn("group flex h-full w-full flex-col rounded-2xl border p-5 text-left transition-all", active ? "border-fg bg-card shadow-lift" : "border-line bg-card/60 hover:-translate-y-px hover:border-fg/40 hover:shadow-soft")}>
                <div className="flex items-center gap-2"><span className="display text-2xl text-muted/70 group-hover:text-accent">{String(i + 1).padStart(2, "0")}</span><span className="h-px flex-1 bg-line" />{p.tier === "signature" && p.diet === "veg" && p.key.endsWith("signature") && <span className="label !text-accent">most chosen</span>}</div>
                <h3 className="mt-3 text-lg font-semibold tracking-tight">{p.name}</h3>
                <p className="display-italic mt-0.5 text-[15px] text-muted">{p.tagline}</p>
                <div className="mt-4 flex items-end gap-2">
                  <span className="text-2xl font-semibold tabular-nums">{p.from_per_plate ? rupees(p.from_per_plate) : "—"}</span>
                  <span className="mb-1 text-xs text-muted">/ plate</span>
                  {p.list_price && p.from_per_plate && Number(p.from_per_plate) < Number(p.list_price) && <span className="mb-1 text-xs tabular-nums text-muted line-through decoration-muted/60">{rupees(p.list_price)}</span>}
                </div>
                <p className="mt-2 text-xs text-muted">{p.item_count} items · {p.slots.length ? `${p.slots.length} choices` : "as printed"}</p>
              </button>
            </li>
          );
        })}
      </ul>

      {pkg && (
        <div className="mt-8 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          {/* Left: the plate */}
          <div className="space-y-5">
            <div className="card p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <span className="label">{titleCase(pkg.diet)} · {pkg.name}</span>
                  <h2 className="mt-1 text-2xl font-semibold tracking-tight">{pkg.tagline}</h2>
                  <p className="mt-1 max-w-lg text-[14px] leading-relaxed text-muted">{pkg.description}</p>
                </div>
                {(Object.keys(choices).length > 0 || add.length > 0 || remove.length > 0 || jain) && (
                  <button onClick={() => { setChoices({}); setAdd([]); setRemove([]); setJain(false); }} className="chip"><RotateCcw size={12} /> As printed</button>
                )}
              </div>

              {/* Guests */}
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <span className="label">Guests</span>
                <div className="hairline inline-flex items-center rounded-full bg-bg">
                  <button aria-label="fewer" onClick={() => setGuests((g) => Math.max(25, g - 25))} className="grid h-9 w-9 place-items-center rounded-full hover:bg-line/60"><Minus size={14} /></button>
                  <input value={guests} onChange={(e) => setGuests(Math.min(500, Math.max(1, Number(e.target.value.replace(/\D/g, "")) || 1)))} inputMode="numeric" className="w-14 bg-transparent text-center text-sm font-semibold tabular-nums outline-none" />
                  <button aria-label="more" onClick={() => setGuests((g) => Math.min(500, g + 25))} className="grid h-9 w-9 place-items-center rounded-full hover:bg-line/60"><Plus size={14} /></button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {GUEST_STEPS.map((g) => <button key={g} onClick={() => setGuests(g)} className={cn("rounded-full px-2.5 py-1 text-xs tabular-nums transition-colors", guests === g ? "bg-fg text-bg" : "hover:bg-line/60")}>{g}</button>)}
                </div>
                {pkg.diet === "veg" && (
                  <button onClick={() => setJain((j) => !j)} className={cn(chip(jain, "good"), "ml-auto")}><Leaf size={12} /> Jain</button>
                )}
              </div>

              {/* Choose-one slots */}
              {pkg.slots.length > 0 && (
                <div className="mt-6 space-y-3">
                  <span className="label">Your choices</span>
                  {pkg.slots.map((s) => (
                    <div key={s.key} className="flex flex-wrap items-center gap-2">
                      <span className="w-24 text-sm text-muted">{s.label}</span>
                      {s.options.map((o) => {
                        const on = (choices[s.key] ?? s.default) === o;
                        return <button key={o} onClick={() => setChoices({ ...choices, [s.key]: o })} className={chip(on)}>{on && <Check size={12} />}{dishes[o]?.name ?? o}</button>;
                      })}
                    </div>
                  ))}
                </div>
              )}

              {/* The plate */}
              <div className="mt-6">
                <div className="flex items-center justify-between"><span className="label">On the plate</span><span className="text-xs text-muted">{priced?.items.length ?? pkg.item_count} items</span></div>
                <div className="mt-2 grid gap-x-6 gap-y-3 sm:grid-cols-2">
                  {cat.categories.filter((c) => priced?.items.some((i) => i.category === c)).map((c) => (
                    <div key={c}>
                      <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-muted">{CAT_LABEL[c] ?? titleCase(c)}</div>
                      <ul className="space-y-1 text-sm">
                        {priced?.items.filter((i) => i.category === c).map((i) => {
                          const removable = !cat.never_remove.includes(i.slug);
                          return (
                            <li key={i.slug} className="group flex items-center justify-between gap-2">
                              <span title={dishes[i.slug]?.name_te ?? undefined}>{i.name}</span>
                              {removable ? (
                                <button onClick={() => { if (add.includes(i.slug)) setAdd(add.filter((a) => a !== i.slug)); else setRemove([...remove, i.slug]); }}
                                  className="text-xs text-muted opacity-0 transition-opacity hover:text-bad group-hover:opacity-100">remove</button>
                              ) : <span className="text-[11px] text-muted">included</span>}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ))}
                </div>
                {pkg.includes.length > 0 && <p className="mt-4 text-xs text-muted">Included in every plate: {pkg.includes.join(" · ")}. {cat.optional_addons.includes("water") && "Packaged water is an add-on below."}</p>}
              </div>
            </div>

            <AddMore cat={cat} pkg={pkg} priced={priced} add={add} remove={remove} jain={jain}
              onAdd={(s) => { if (remove.includes(s)) setRemove(remove.filter((r) => r !== s)); else setAdd([...add, s]); }} />
          </div>

          {/* Right: price + quote */}
          <div id="quote-panel" className="scroll-mt-24 lg:sticky lg:top-20 lg:self-start">
            <PricePanel pkg={pkg} priced={priced} busy={busy} err={err} guests={guests} selection={{ package_key: pkg.key, guest_count: guests, choices, add, remove, diet: jain ? "jain" : null }} />
          </div>
        </div>
      )}
      {pkg && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-card/95 px-5 py-3 backdrop-blur lg:hidden">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
            <div>
              <span className="label">Per plate · {guests} guests</span>
              <div className={cn("text-xl font-semibold tabular-nums transition-opacity", busy && "opacity-50")}>{priced ? rupees(priced.per_plate) : "—"} <span className="text-xs font-normal text-muted">· {priced ? rupees(priced.grand_total) : "—"} incl. GST</span></div>
            </div>
            <a href="#quote-panel" className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-fg px-4 text-sm font-medium text-bg">Get quote <ArrowRight size={14} /></a>
          </div>
        </div>
      )}
    </div>
  );
}

function AddMore({ cat, pkg, priced, add, remove, jain, onAdd }: { cat: MenuCatalog; pkg: MenuPackage; priced: PricedMenu | null; add: string[]; remove: string[]; jain: boolean; onAdd: (s: string) => void }) {
  const [q, setQ] = useState("");
  const on = new Set(priced?.items.map((i) => i.slug) ?? []);
  const pool = cat.dishes.filter((d) => !on.has(d.slug) && d.category !== "service" && (pkg.diet === "non_veg" || d.diet === "veg") && (!jain || d.jain_ok)
    && (!q || d.name.toLowerCase().includes(q.toLowerCase()) || (d.name_te ?? "").includes(q)));
  const extras = cat.dishes.filter((d) => d.category === "service" && cat.optional_addons.includes(d.slug) && !on.has(d.slug));
  const byCat = cat.categories.map((c) => [c, pool.filter((d) => d.category === c)] as const).filter(([, l]) => l.length);
  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><span className="label">Add more</span><p className="mt-1 text-sm text-muted">Anything from our kitchen, priced per plate and added instantly.</p></div>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search a dish…" className="h-9 w-48 text-xs" />
      </div>
      {extras.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="w-24 text-sm text-muted">Optional</span>
          {extras.map((d) => <button key={d.slug} onClick={() => onAdd(d.slug)} className="chip"><Plus size={12} />{d.name}</button>)}
        </div>
      )}
      <div className="mt-4 space-y-3">
        {byCat.map(([c, list]) => (
          <div key={c} className="flex flex-wrap items-start gap-2">
            <span className="w-24 pt-1.5 text-sm text-muted">{CAT_LABEL[c] ?? titleCase(c)}</span>
            <div className="flex flex-1 flex-wrap gap-1.5">
              {list.map((d) => <button key={d.slug} onClick={() => onAdd(d.slug)} title={d.description ?? undefined} className="chip"><Plus size={12} />{d.name}</button>)}
            </div>
          </div>
        ))}
        {!byCat.length && !extras.length && <p className="text-sm text-muted">Everything we cook is already on this plate.</p>}
      </div>
      {(add.length > 0 || remove.length > 0) && <p className="mt-4 text-xs text-muted">{add.length ? `Added: ${add.map((s) => cat.dishes.find((d) => d.slug === s)?.name ?? s).join(", ")}. ` : ""}{remove.length ? `Removed: ${remove.map((s) => cat.dishes.find((d) => d.slug === s)?.name ?? s).join(", ")}.` : ""}</p>}
    </div>
  );
}

function PricePanel({ pkg, priced, busy, err, guests, selection }: { pkg: MenuPackage; priced: PricedMenu | null; busy: boolean; err: string | null; guests: number; selection: MenuSelection }) {
  const r = useRouter();
  const [f, setF] = useState({ name: "", phone: "", email: "", occasion: "", event_date: "" });
  const [state, setState] = useState<"idle" | "busy" | "error">("idle");
  const [ferr, setFerr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const listPer = priced?.list_price ? Number(priced.list_price) : null;
  const per = priced ? Number(priced.per_plate) : null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("busy"); setFerr(null);
    try {
      const res = await api<{ portal_token: string }>("/api/public/menu/enquire", { method: "POST", auth: false, body: JSON.stringify({ ...selection, ...f, email: f.email || null, occasion: f.occasion || null, event_date: f.event_date || null }) });
      r.push(`/portal/${res.portal_token}`);
    } catch (ex) {
      setState("error"); setFerr(ex instanceof Error ? ex.message : String(ex));
    }
  }

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-line bg-bg-2/60 p-6">
        <div className="flex items-end justify-between gap-3">
          <div>
            <span className="label">Per plate</span>
            <div className={cn("kpi mt-1 transition-opacity", busy && "opacity-50")}>{per != null ? rupees(per) : "—"}</div>
          </div>
          {listPer != null && per != null && per < listPer && (
            <div className="text-right"><span className="label">Printed card</span><div className="mt-1 text-lg tabular-nums text-muted line-through decoration-muted/60">{rupees(listPer)}</div></div>
          )}
        </div>
        <dl className="mt-5 grid grid-cols-3 gap-3 border-t border-line/80 pt-4 text-sm">
          <div><dt className="label">Guests</dt><dd className="mt-1 font-medium tabular-nums">{guests}</dd></div>
          <div><dt className="label">Food</dt><dd className="mt-1 font-medium tabular-nums">{priced ? rupees(priced.subtotal) : "—"}</dd></div>
          <div><dt className="label">Total incl. GST</dt><dd className="mt-1 font-semibold tabular-nums">{priced ? rupees(priced.grand_total) : "—"}</dd></div>
        </dl>
        {priced?.notes.map((n) => <p key={n} className="mt-3 text-xs text-muted">{n}</p>)}
        {priced?.changes.length ? <p className="mt-3 text-xs text-muted">Your plate: {priced.changes.join(" · ")}</p> : null}
        {err && <p className="mt-3 text-xs text-bad">{err}</p>}
      </div>
      <form onSubmit={submit} className="space-y-3 p-6">
        <div className="flex items-center gap-2 text-accent"><Sparkles size={14} /><span className="label !text-accent">Make it my quote</span></div>
        <p className="text-[13px] leading-relaxed text-muted">Your phone number turns this plate into a live quote on your own link — change it later, lock the price, pay the advance. The owner is alerted the moment you send it.</p>
        <div className="grid grid-cols-2 gap-2">
          <Input value={f.name} onChange={set("name")} placeholder="Your name" required autoComplete="name" />
          <Input value={f.phone} onChange={set("phone")} placeholder="+91 98765 43210" required inputMode="tel" autoComplete="tel" />
          <select value={f.occasion} onChange={set("occasion")} className="hairline h-10 rounded-xl bg-card px-3 text-sm outline-none"><option value="">Occasion…</option>{OCCASIONS.map((o) => <option key={o} value={o}>{o}</option>)}</select>
          <Input type="date" value={f.event_date} onChange={set("event_date")} />
          <Input type="email" value={f.email} onChange={set("email")} placeholder="Email (optional)" className="col-span-2" autoComplete="email" />
        </div>
        {ferr && <p className="text-xs text-bad">{ferr}</p>}
        <Button type="submit" size="lg" className="group w-full gap-2" disabled={state === "busy" || !priced}>{state === "busy" ? "Creating your quote…" : <>Get this quote on my phone <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" /></>}</Button>
        <p className="text-[11px] text-muted">Sending means you agree to be contacted about this event and to us storing these details (DPDP). Reply STOP anytime.</p>
      </form>
    </div>
  );
}
