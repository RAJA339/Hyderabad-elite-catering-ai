import Link from "next/link";
import { ThemeToggle } from "@/components/theme-toggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-bg/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold tracking-tight">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent" /> Hyderabad Elite Catering
        </Link>
        <nav className="flex items-center gap-4 text-sm text-muted">
          <Link href="/portal" className="hover:text-fg">Client portal</Link>
          <Link href="/admin" className="hover:text-fg">Admin</Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
