import { cn } from "@/lib/utils";
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-line/70", className)} />;
}
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="hairline rounded-xl border-dashed p-8 text-center text-sm text-muted">{children}</div>;
}
