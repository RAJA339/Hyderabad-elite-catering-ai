"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { pct } from "@/lib/format";
import { Card, CardTitle, Stat } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageTitle } from "@/components/admin-shell";

type Health = { index: { chunks: number; sources: number; last_indexed: string | null }; queries: { queries_7d: number; avg_latency_ms: number | null; cache_hit_pct: string | null }; last_eval: { ran_at: string; context_precision: string; context_recall: string; faithfulness: string; answer_relevancy: string } | null };
type Q = { plan: { intent: string; rewritten: string; diet: string | null; guest_count: number | null; festival_keys: string[] }; cache_hit: boolean; latency_ms: number; context: string[]; hits: { id: string; score: number; breadcrumb: string; source_type: string }[] };

export default function Rag() {
  const [h, setH] = useState<Health | null>(null);
  const [q, setQ] = useState("Do you have Jain options for 200 guests?");
  const [res, setRes] = useState<Q | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api<Health>("/api/admin/rag-health").then(setH).catch(() => {});
  useEffect(() => { load(); }, []);
  async function run() { setBusy(true); try { setRes(await api<Q>("/api/rag/query", { method: "POST", body: JSON.stringify({ query: q }) })); } finally { setBusy(false); } }
  async function reindex() { setBusy(true); try { await api("/api/rag/reindex", { method: "POST" }); load(); } finally { setBusy(false); } }
  return (
    <>
      <PageTitle title="Knowledge layer" sub="Hybrid retrieval (pgvector + BM25 → RRF → rerank), live SQL enrichment, semantic cache, nightly eval." right={<Button size="sm" variant="secondary" onClick={reindex} disabled={busy}>Reindex now</Button>} />
      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Active chunks" value={h?.index.chunks ?? "—"} hint={`${h?.index.sources ?? 0} sources · ${h?.index.last_indexed ? new Date(h.index.last_indexed).toLocaleString("en-IN") : "never indexed"}`} />
        <Stat label="Queries · 7d" value={h?.queries.queries_7d ?? "—"} hint={`avg ${h?.queries.avg_latency_ms ?? "—"} ms · cache ${h?.queries.cache_hit_pct ?? 0}%`} />
        <Stat label="Faithfulness" value={h?.last_eval ? pct(Number(h.last_eval.faithfulness) * 100, 0) : "—"} tone={h?.last_eval && Number(h.last_eval.faithfulness) < 0.85 ? "bad" : "good"} hint="gate ≥ 85%" />
        <Stat label="Context recall" value={h?.last_eval ? pct(Number(h.last_eval.context_recall) * 100, 0) : "—"} hint={h?.last_eval ? `precision ${pct(Number(h.last_eval.context_precision) * 100, 0)}` : "run eval"} />
      </div>
      <Card className="mt-4">
        <CardTitle>Retrieval playground</CardTitle>
        <form onSubmit={(e) => { e.preventDefault(); run(); }} className="mt-3 flex gap-2"><Input value={q} onChange={(e) => setQ(e.target.value)} /><Button type="submit" disabled={busy}>Retrieve</Button></form>
        {res && (
          <div className="mt-4 grid gap-4 md:grid-cols-[0.4fr_0.6fr]">
            <div className="space-y-2 text-sm">
              <div className="label">Query plan</div>
              <pre className="hairline overflow-x-auto rounded-xl bg-bg p-3 font-mono text-xs">{JSON.stringify({ ...res.plan, cache_hit: res.cache_hit, latency_ms: res.latency_ms }, null, 2)}</pre>
              <div className="label">Reranked hits</div>
              <ul className="space-y-1 text-xs">{res.hits.map((x) => <li key={x.id} className="flex justify-between"><span>{x.breadcrumb} <span className="text-muted">({x.source_type})</span></span><span className="tabular-nums text-muted">{x.score.toFixed(3)}</span></li>)}</ul>
            </div>
            <div className="space-y-2"><div className="label">Assembled context</div>{res.context.map((c, i) => <pre key={i} className="hairline max-h-40 overflow-auto whitespace-pre-wrap rounded-xl bg-bg p-3 text-xs">{c}</pre>)}</div>
          </div>
        )}
      </Card>
    </>
  );
}
