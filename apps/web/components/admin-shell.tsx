"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BarChart3, CalendarDays, Database, LineChart, LogOut, Sparkles, Tags, Users } from "lucide-react";
import { getToken, setToken } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/admin", label: "Overview", icon: BarChart3 },
  { href: "/admin/insights", label: "Insights", icon: LineChart },
  { href: "/admin/leads", label: "Pipeline", icon: Users },
  { href: "/admin/pricing", label: "Pricing & margin", icon: Tags },
  { href: "/admin/kitchen", label: "Kitchen calendar", icon: CalendarDays },
  { href: "/admin/festivals", label: "Festivals", icon: Sparkles },
  { href: "/admin/rag", label: "Knowledge (RAG)", icon: Database },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  // The login page lives under /admin, and Next composes layouts rather than replacing them,
  // so without this the shell redirects the login page to itself and renders nothing.
  const isLogin = path === "/admin/login";
  useEffect(() => {
    if (isLogin) return;
    if (!getToken()) router.replace("/admin/login");
    else setReady(true);
  }, [router, isLogin]);
  if (isLogin) return <>{children}</>;
  if (!ready) return null;
  return (
    <div className="flex min-h-dvh">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-line p-4 md:flex">
        <Link href="/" className="mb-6 flex items-center gap-2 px-2 text-sm font-semibold tracking-tight"><span className="h-2.5 w-2.5 rounded-full bg-accent" /> HEC Command Center</Link>
        <nav className="flex flex-1 flex-col gap-1">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = href === "/admin" ? path === href : path.startsWith(href);
            return (
              <Link key={href} href={href} className={cn("flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm", active ? "bg-fg text-bg" : "text-muted hover:bg-line/50 hover:text-fg")}>
                <Icon size={15} /> {label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center justify-between px-2">
          <ThemeToggle />
          <button onClick={() => { setToken(null); router.replace("/admin/login"); }} className="flex items-center gap-1.5 text-xs text-muted hover:text-fg"><LogOut size={13} /> Sign out</button>
        </div>
      </aside>
      <main className="scroll-thin flex-1 overflow-x-hidden p-5 md:p-8">
        <div className="mb-4 flex gap-2 overflow-x-auto md:hidden">
          {nav.map(({ href, label }) => <Link key={href} href={href} className={cn("hairline shrink-0 rounded-full px-3 py-1 text-xs", path === href && "bg-fg text-bg")}>{label}</Link>)}
        </div>
        {children}
      </main>
    </div>
  );
}

export function PageTitle({ title, sub, right }: { title: string; sub?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1>{sub && <p className="mt-1 text-sm text-muted">{sub}</p>}</div>
      {right}
    </div>
  );
}
