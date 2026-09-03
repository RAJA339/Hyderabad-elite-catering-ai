import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  neutral: "bg-line/60 text-fg", good: "bg-good/15 text-good", warn: "bg-warn/15 text-warn", bad: "bg-bad/15 text-bad", accent: "bg-accent/15 text-accent",
};
export function Badge({ children, tone = "neutral", className }: { children: React.ReactNode; tone?: keyof typeof tones; className?: string }) {
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium", tones[tone], className)}>{children}</span>;
}
export const stageTone = (s: string) =>
  ["locked", "advance_paid", "confirmed", "completed"].includes(s) ? "good" : ["quoted", "negotiating"].includes(s) ? "accent" : s === "lost" ? "bad" : "neutral";
