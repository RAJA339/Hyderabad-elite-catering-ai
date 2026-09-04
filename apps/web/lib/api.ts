export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "hecai.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch {}
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** A failed fetch says only "Failed to fetch", which hides whether the API URL is wrong,
 * unreachable, blocked by CORS, or http:// on an https:// page. Name the URL and the
 * likeliest cause instead. */
export class ApiUnreachable extends Error {
  constructor(public url: string, cause: unknown) {
    const page = typeof window === "undefined" ? "" : window.location.origin;
    const mixed = page.startsWith("https://") && url.startsWith("http://");
    const hint = url.includes("localhost")
      ? "The site is using the default localhost API. Set NEXT_PUBLIC_API_URL to your deployed API and redeploy."
      : mixed
        ? "The page is https but the API URL is http, so the browser blocks it. Use https:// in NEXT_PUBLIC_API_URL."
        : "The API is unreachable, or CORS_ORIGINS on the API does not list this site's exact address.";
    super(`Could not reach ${url}. ${hint}`);
    this.cause = cause;
  }
}

export async function api<T = unknown>(path: string, init: RequestInit & { auth?: boolean } = {}): Promise<T> {
  const { auth = true, ...rest } = init;
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(rest.headers as Record<string, string>) };
  const token = auth ? getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;
  const url = `${API}${path}`;
  let r: Response;
  try {
    r = await fetch(url, { ...rest, headers, cache: "no-store" });
  } catch (e) {
    throw new ApiUnreachable(url, e);
  }
  if (r.status === 401 && auth && typeof window !== "undefined" && !location.pathname.startsWith("/admin/login")) {
    setToken(null);
    location.href = "/admin/login";
  }
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail ?? msg; } catch {}
    throw new ApiError(r.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return r.json() as Promise<T>;
}

// ── Types (subset of API responses) ─────────────────────────────────────────
export type Lead = {
  id: string; stage: string; source: string; occasion: string | null; event_date: string | null; guest_count: number | null;
  diet: string | null; venue_area: string | null; conversion_probability: string | null; handoff_active: boolean;
  created_at: string; updated_at: string; full_name: string | null; phone: string; latest_total: string | null; latest_per_plate: string | null;
};
export type Overview = {
  pipeline: { stage: string; n: number; value: string }[];
  margin: { avg_margin: string | null; min_margin: string | null; quotes_30d: number; booked_value_30d: string };
  funnel: { wa_leads: number; web_leads: number; quoted: number; locked: number; paid: number };
  clv: { avg_clv: string | null; avg_bookings: string | null; repeat_customers: number; customers: number };
  open_escalations: number;
};
export type QuoteBundle = {
  quote: { id: string; quote_number: string; version: number; tier: string; status: string; guest_count: number; diet: string; event_date: string;
    subtotal: string; discount_total: string; surcharge_total: string; tax_total: string; grand_total: string; per_plate: string; margin_pct: string;
    market_snapshot: MarketSnapshot | null; valid_until: string | null };
  items: { slug: string; name: string; category: string; unit_price: string }[];
  lead: { occasion: string | null; venue_area: string | null; guest_count: number; full_name: string | null };
  events: { type: string; payload: Record<string, unknown>; per_plate_before: string | null; per_plate_after: string | null; created_at: string }[];
  payments?: { kind: string; amount: string; status: string; payment_link: string | null; paid_at: string | null }[];
  lock: { locked_per_plate: string; valid_until: string; certificate_hash: string } | null;
  chat?: { role: string; content: string; created_at: string }[];
};
export type MarketSnapshot = {
  as_of: string | null; our_per_plate: string; our_cost_per_plate: string; market_benchmark_per_plate: string; you_save_vs_benchmark: string;
  ingredients: { key: string; name: string; unit: string; wholesale: string; retail: string | null; change_7d_pct: string; volatile?: boolean }[];
  surcharge_total: string; notes: string[];
};
