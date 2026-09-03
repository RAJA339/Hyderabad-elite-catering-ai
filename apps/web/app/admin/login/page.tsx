"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function Login() {
  const r = useRouter();
  const [email, setEmail] = useState("owner@hec.example");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      const res = await api<{ access_token: string }>("/api/auth/login", { method: "POST", auth: false, body: JSON.stringify({ email, password, tenant: "hec" }) });
      setToken(res.access_token); r.replace("/admin");
    } catch (e) { setErr((e as Error).message || "Login failed"); } finally { setBusy(false); }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg p-5">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 p-6">
        <div><h1 className="text-lg font-semibold tracking-tight">Command Center</h1><p className="text-sm text-muted">Sign in with your staff account.</p></div>
        <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" required />
        <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" required />
        {err && <p className="text-xs text-bad">{err}</p>}
        <Button type="submit" className="w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
      </form>
    </div>
  );
}
