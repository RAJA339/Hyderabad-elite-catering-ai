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
  if (err && !data) {
    const behind = /not found|404/i.test(err);
    return (
      <div className="card max-w-xl p-6 text-sm">
        <div className="font-semibold">{behind ? "The API is behind the website" : "Couldn’t load insights"}</div>
        <p className="mt-2 text-muted">{behind
          ? "The website has the Insights page but the API it talks to does not have the analytics endpoint yet. Railway has not deployed the latest commit. Open Railway → Deployments and make sure the newest commit is Active, then reload this page."
          : err}</p>
      </div>
    );
  }
  // First load shows a skeleton; every later range change keeps the frame and dims it.
  if (!data) return <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>;
  return <InsightsView data={data} days={days} onRange={setDays} loading={loading} />;
}
