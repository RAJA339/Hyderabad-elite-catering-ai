"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type QuoteBundle } from "@/lib/api";
import { QuoteView } from "@/components/quote-view";
import { SiteHeader } from "@/components/site-header";

export default function Shared() {
  const { slug } = useParams<{ slug: string }>();
  const [b, setB] = useState<QuoteBundle | null>(null);
  useEffect(() => { api<QuoteBundle>(`/api/portal/shared/${slug}`, { auth: false }).then(setB).catch(() => {}); }, [slug]);
  return <><SiteHeader />{b ? <QuoteView bundle={b} readOnly /> : <p className="p-10 text-center text-sm text-muted">Loading shared quote…</p>}</>;
}
