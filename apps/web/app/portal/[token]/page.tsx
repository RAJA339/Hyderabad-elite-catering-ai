"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type QuoteBundle } from "@/lib/api";
import { QuoteView } from "@/components/quote-view";
import { SiteHeader } from "@/components/site-header";
import { Skeleton } from "@/components/ui/skeleton";

export default function Portal() {
  const { token } = useParams<{ token: string }>();
  const [b, setB] = useState<QuoteBundle | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<QuoteBundle>(`/api/portal/${token}`, { auth: false }).then(setB).catch((e) => setErr(e instanceof Error ? e.message : String(e))); }, [token]);
  return (
    <>
      <SiteHeader />
      {err ? <p className="mx-auto max-w-xl whitespace-pre-wrap p-10 text-center text-sm text-muted">{err.startsWith("Could not reach") ? err : "This quote link is invalid or expired. Ask Anvi on WhatsApp for a fresh one."}</p>
        : b ? <QuoteView bundle={b} token={token} onUpdate={setB} /> : <div className="mx-auto max-w-3xl space-y-4 p-5"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>}
    </>
  );
}
