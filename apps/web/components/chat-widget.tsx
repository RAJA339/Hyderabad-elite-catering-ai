"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUp, MessageCircle, Sparkles, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

type Msg = { role: "you" | "anvi"; text: string; at: number; buttons?: { id: string; title: string }[]; error?: boolean };

const sid = () => {
  try {
    return localStorage.getItem("hecai.sid") || (() => { const s = crypto.randomUUID(); localStorage.setItem("hecai.sid", s); return s; })();
  } catch { return "anon-" + Math.random().toString(36).slice(2); }
};

const STARTERS = [
  "Housewarming, 14 Oct, 120 guests, veg",
  "Wedding reception for 400, non-veg, Gachibowli",
  "Corporate lunch, 80 people, Jain options",
];

const fmtTime = (t: number) => new Date(t).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });

export function ChatWidget({ inline = false }: { inline?: boolean }) {
  const [open, setOpen] = useState(inline);
  const [msgs, setMsgs] = useState<Msg[]>([{ role: "anvi", at: Date.now(), text: "Namaste! I’m Anvi. Tell me the occasion, date and guest count — I’ll price a complete menu on today’s Hyderabad market rates." }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);

  async function send(text: string) {
    const t = text.trim();
    if (!t || busy) return;
    setMsgs((m) => [...m, { role: "you", text: t, at: Date.now() }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api<{ reply: string; buttons: { id: string; title: string }[] }>("/api/chat", {
        method: "POST", auth: false, body: JSON.stringify({ session_id: sid(), message: t }),
      });
      setMsgs((m) => [...m, { role: "anvi", text: r.reply, buttons: r.buttons, at: Date.now() }]);
    } catch (e) {
      // Show the real cause: a hidden failure is impossible to fix.
      const detail = e instanceof ApiError ? `${e.status}: ${e.message}` : e instanceof Error ? e.message : String(e);
      const hint = e instanceof ApiError ? "" : " — is the API running on port 8000?";
      setMsgs((m) => [...m, { role: "anvi", error: true, at: Date.now(), text: `I couldn’t reach the kitchen just now.\n${detail}${hint}` }]);
    } finally {
      setBusy(false);
      box.current?.focus();
    }
  }

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
  };
  const showStarters = msgs.length === 1 && !busy;

  const panel = (
    <div className={cn("glass relative flex flex-col overflow-hidden rounded-[22px]", inline ? "h-[600px]" : "h-[560px] w-[380px]")}>
      <div className="flex items-center justify-between border-b border-line/70 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="relative grid h-9 w-9 place-items-center rounded-full bg-fg text-bg">
            <Sparkles size={15} />
            <span className="live-dot absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-card bg-good" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">Anvi</div>
            <div className="text-[11px] text-muted">Catering consultant · replies in seconds</div>
          </div>
        </div>
        {!inline && <button onClick={() => setOpen(false)} aria-label="Close" className="rounded-full p-1.5 text-muted hover:bg-line/50 hover:text-fg"><X size={16} /></button>}
      </div>

      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {msgs.map((m, i) => (
          <div key={i} className={cn("flex flex-col gap-1", m.role === "you" ? "items-end" : "items-start")}>
            <div className={cn("max-w-[86%] whitespace-pre-wrap", m.role === "you" ? "bubble-out" : "bubble-in", m.error && "border border-bad/40 bg-bad/5 text-bad")}>
              {m.text}
            </div>
            {m.buttons?.length ? (
              <div className="mt-1 flex max-w-[86%] flex-wrap gap-1.5">
                {m.buttons.map((b) => <button key={b.id} onClick={() => send(b.title)} className="chip">{b.title}</button>)}
              </div>
            ) : null}
            <span className="px-1 text-[10px] text-muted/80">{m.role === "anvi" ? "Anvi · " : ""}{fmtTime(m.at)}</span>
          </div>
        ))}
        {busy && (
          <div className="flex items-end gap-1 pl-1">
            <div className="bubble-in flex items-center gap-1 py-3.5">
              <span className="typing-dot h-1.5 w-1.5 rounded-full bg-muted" /><span className="typing-dot h-1.5 w-1.5 rounded-full bg-muted" /><span className="typing-dot h-1.5 w-1.5 rounded-full bg-muted" />
            </div>
          </div>
        )}
        {showStarters && (
          <div className="pt-2">
            <div className="label mb-2">Try one</div>
            <div className="flex flex-wrap gap-1.5">{STARTERS.map((s) => <button key={s} onClick={() => send(s)} className="chip">{s}</button>)}</div>
          </div>
        )}
        <div ref={end} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="border-t border-line/70 p-3">
        <div className="hairline flex items-end gap-2 rounded-2xl bg-card p-1.5 pl-3.5 transition-shadow focus-within:shadow-lift focus-within:ring-2 focus-within:ring-accent/30">
          <textarea ref={box} rows={1} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey}
            placeholder="Occasion, date, guests, veg or non-veg…" className="max-h-28 min-h-[38px] flex-1 resize-none bg-transparent py-2 text-[15px] outline-none placeholder:text-muted/70" />
          <button type="submit" disabled={busy || !input.trim()} aria-label="Send" className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-fg text-bg transition-all hover:opacity-90 disabled:opacity-30">
            <ArrowUp size={16} />
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between px-1 text-[10px] text-muted/80"><span>Enter to send · Shift+Enter for a new line</span><span>Prices from live market data</span></div>
      </form>
    </div>
  );

  if (inline) return panel;
  return (
    <div className="fixed bottom-5 right-5 z-50">
      {open ? panel : (
        <button onClick={() => setOpen(true)} className="flex h-12 items-center gap-2 rounded-full bg-fg px-5 text-sm font-medium text-bg shadow-lift transition-transform hover:-translate-y-0.5">
          <MessageCircle size={16} /> Plan my menu
        </button>
      )}
    </div>
  );
}
