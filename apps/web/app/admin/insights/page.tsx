"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { InsightsView, type Analytics } from "@/components/insights-view";
import { Skeleton } from "@/components/ui/skeleton";

export default function InsightsPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setLoading(true);
    api<Analytics>(`/api/admin/analytics?days=${days}`).then((d) => { if (live) { setData(d); setErr(null); } }).catch((e) => { if (live) setErr(e instanceof Error ? e.message : String(e)); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [days]);
  if (err && !data) return <p className="text-sm text-bad">{err}</p>;
  // First load shows a skeleton; every later range change keeps the frame and dims it.
  if (!data) return <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>;
  return <InsightsView data={data} days={days} onRange={setDays} loading={loading} />;
}
