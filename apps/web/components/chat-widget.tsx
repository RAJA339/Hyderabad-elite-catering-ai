"use client";
import { useEffect, useRef, useState } from "react";
import { MessageCircle, Send, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Msg = { role: "you" | "anvi"; text: string; buttons?: { id: string; title: string }[] };
const sid = () => { try { return localStorage.getItem("hecai.sid") || (() => { const s = crypto.randomUUID(); localStorage.setItem("hecai.sid", s); return s; })(); } catch { return "anon-" + Math.random().toString(36).slice(2); } };

export function ChatWidget({ inline = false }: { inline?: boolean }) {
  const [open, setOpen] = useState(inline);
  const [msgs, setMsgs] = useState<Msg[]>([{ role: "anvi", text: "Namaste! I’m Anvi. Tell me the occasion, date and guest count — I’ll price a full menu in a minute." }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setMsgs((m) => [...m, { role: "you", text }]);
    setInput(""); setBusy(true);
    try {
      const r = await api<{ reply: string; buttons: { id: string; title: string }[] }>("/api/chat", { method: "POST", auth: false, body: JSON.stringify({ session_id: sid(), message: text }) });
      setMsgs((m) => [...m, { role: "anvi", text: r.reply, buttons: r.buttons }]);
    } catch {
      setMsgs((m) => [...m, { role: "anvi", text: "Hmm, I lost connection for a second. Try again, or WhatsApp us directly." }]);
    } finally { setBusy(false); }
  }

  const panel = (
    <div className={cn("card flex flex-col overflow-hidden", inline ? "h-[560px]" : "h-[520px] w-[360px]")}>
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-good" /><span className="text-sm font-semibold">Anvi · Catering consultant</span></div>
        {!inline && <button onClick={() => setOpen(false)} aria-label="Close"><X size={16} /></button>}
      </div>
      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto p-4">
        {msgs.map((m, i) => (
          <div key={i} className={cn("flex", m.role === "you" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed", m.role === "you" ? "bg-fg text-bg" : "bg-line/50")}>
              {m.text}
              {m.buttons?.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.buttons.map((b) => <button key={b.id} onClick={() => send(b.title)} className="hairline rounded-full bg-card px-2.5 py-1 text-xs hover:bg-bg">{b.title}</button>)}
                </div>
              ) : null}
            </div>
          </div>
        ))}
        {busy && <div className="text-xs text-muted">Anvi is typing…</div>}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex gap-2 border-t border-line p-3">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="e.g. Housewarming, 14 Oct, 120 guests, veg" className="h-10 flex-1 rounded-xl bg-bg px-3 text-sm outline-none" />
        <Button type="submit" size="md" disabled={busy} aria-label="Send"><Send size={14} /></Button>
      </form>
    </div>
  );
  if (inline) return panel;
  return (
    <div className="fixed bottom-5 right-5 z-50">
      {open ? panel : (
        <button onClick={() => setOpen(true)} className="flex h-12 items-center gap-2 rounded-full bg-fg px-4 text-sm font-medium text-bg shadow-soft">
          <MessageCircle size={16} /> Plan my menu
        </button>
      )}
    </div>
  );
}
