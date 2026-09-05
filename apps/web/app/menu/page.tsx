import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteHeader } from "@/components/site-header";
import { MenuBuilder } from "@/components/menu-builder";

export const metadata: Metadata = { title: "Menus", description: "Nine complete menus, priced live on today’s Hyderabad wholesale rates. Pick a card, make your choices, get your quote." };

export default async function MenuPage({ searchParams }: { searchParams: Promise<{ package?: string }> }) {
  const { package: initial } = await searchParams;
  return (
    <>
      <SiteHeader />
      <main>
        <section className="mx-auto max-w-6xl px-5 pb-8 pt-12 md:pt-16">
          <span className="label flex items-center gap-2"><span className="h-px w-6 bg-accent" /> Amma chethi vanta · nine menus</span>
          <h1 className="mt-4 text-4xl font-semibold leading-[1.02] tracking-[-0.03em] sm:text-5xl">
            Pick a card. <span className="display-italic text-muted">Make</span> it yours.<br className="hidden sm:block" /> Watch the price as you go.
          </h1>
          <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-muted">
            Every menu below is a complete plate — rice, curries, chutneys, a sweet, a snack, disposables included. The “or” lines on our printed card are real choices here. Add anything from the kitchen; the per-plate price re-computes on this morning’s wholesale rates.
          </p>
        </section>
        <Suspense>
          <MenuBuilder initialPackage={initial} />
        </Suspense>
      </main>
    </>
  );
}
