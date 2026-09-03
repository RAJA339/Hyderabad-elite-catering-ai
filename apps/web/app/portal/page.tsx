"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function PortalLogin() {
  const r = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [err, setErr] = useState<string | null>(null);
  async function request() { setErr(null); try { await api("/api/portal/otp/request", { method: "POST", auth: false, body: JSON.stringify({ phone }) }); setStep("code"); } catch (e) { setErr((e as Error).message); } }
  async function verify() { setErr(null); try { const res = await api<{ portal_token: string | null }>("/api/portal/otp/verify", { method: "POST", auth: false, body: JSON.stringify({ phone, code }) }); if (res.portal_token) r.push(`/portal/${res.portal_token}`); else setErr("No quote found for this number yet."); } catch (e) { setErr((e as Error).message); } }
  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-sm px-5 py-16">
        <h1 className="text-2xl font-semibold tracking-tight">Your quote, live.</h1>
        <p className="mt-1 text-sm text-muted">Sign in with a one-time code sent to your WhatsApp, or use the magic link Anvi sent you.</p>
        <div className="card mt-6 space-y-3 p-5">
          {step === "phone" ? (<><Input placeholder="WhatsApp number, e.g. 9198765xxxxx" value={phone} onChange={(e) => setPhone(e.target.value)} /><Button className="w-full" onClick={request}>Send code</Button></>)
            : (<><Input placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" /><Button className="w-full" onClick={verify}>Open my quote</Button></>)}
          {err && <p className="text-xs text-bad">{err}</p>}
        </div>
      </main>
    </>
  );
}
