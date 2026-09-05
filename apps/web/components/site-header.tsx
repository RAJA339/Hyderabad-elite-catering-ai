import Link from "next/link";
import { ThemeToggle } from "@/components/theme-toggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40">
      <div className="mx-auto mt-3 max-w-6xl px-4">
        <div className="glass flex h-12 items-center justify-between rounded-full px-4 pl-5">
          <Link href="/" className="flex items-center gap-2.5 whitespace-nowrap text-sm font-semibold tracking-tight">
            <span className="relative inline-flex h-2 w-2"><span className="absolute inline-flex h-full w-full rounded-full bg-accent opacity-60 blur-[2px]" /><span className="relative inline-flex h-2 w-2 rounded-full bg-accent" /></span>
            Hyderabad Elite Catering
          </Link>
          <nav className="flex items-center gap-0.5 text-[13px] sm:gap-1">
            <Link href="/menu" className="rounded-full px-3 py-1.5 text-muted transition-colors hover:bg-line/50 hover:text-fg">Menus</Link>
            <Link href="/#enquire" className="hidden rounded-full px-3 py-1.5 text-muted transition-colors hover:bg-line/50 hover:text-fg sm:block">Request a call</Link>
            <Link href="/portal" className="hidden rounded-full px-3 py-1.5 text-muted transition-colors hover:bg-line/50 hover:text-fg sm:block">Client portal</Link>
            <Link href="/admin" className="rounded-full px-3 py-1.5 text-muted transition-colors hover:bg-line/50 hover:text-fg">Admin</Link>
            <span className="mx-1 h-4 w-px bg-line" />
            <ThemeToggle />
          </nav>
        </div>
      </div>
    </header>
  );
}
