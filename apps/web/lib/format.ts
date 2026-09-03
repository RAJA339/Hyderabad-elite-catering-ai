const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const rupees = (v: string | number | null | undefined, cents = false) =>
  v == null || v === "" ? "—" : (cents ? inr2 : inr).format(Number(v));

export const pct = (v: string | number | null | undefined, digits = 1) => (v == null ? "—" : `${Number(v).toFixed(digits)}%`);

export const dateShort = (d: string | Date | null | undefined) =>
  d ? new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";

export const timeAgo = (d: string | Date) => {
  const s = (Date.now() - new Date(d).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

export const titleCase = (s: string | null | undefined) => (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const STAGE_ORDER = ["new", "qualifying", "qualified", "quoted", "negotiating", "locked", "advance_paid", "confirmed", "completed", "lost"];
