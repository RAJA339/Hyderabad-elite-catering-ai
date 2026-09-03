"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardTitle } from "@/components/ui/card";
import { PageTitle } from "@/components/admin-shell";
import { cn } from "@/lib/utils";

type Day = { day: string; committed: number; bookings: number; capacity: number };

export default function Kitchen() {
  const [days, setDays] = useState<Day[]>([]);
  useEffect(() => { api<{ days: Day[] }>("/api/admin/kitchen-calendar?days=59").then((r) => setDays(r.days)).catch(() => {}); }, []);
  const tone = (d: Day) => { const r = d.committed / d.capacity; return r >= 0.9 ? "bg-bad/80 text-white" : r >= 0.6 ? "bg-warn/70" : r > 0 ? "bg-good/40" : "bg-line/40"; };
  return (
    <>
      <PageTitle title="Kitchen load calendar" sub="Committed guests per day against the 500-guest capacity. The agent refuses dates that would exceed it." />
      <Card>
        <CardTitle>Next 60 days</CardTitle>
        <div className="mt-4 grid grid-cols-7 gap-1.5 md:grid-cols-10 lg:grid-cols-15">
          {days.map((d) => (
            <div key={d.day} title={`${d.day}: ${d.committed}/${d.capacity} guests · ${d.bookings} bookings`} className={cn("flex aspect-square flex-col items-center justify-center rounded-lg text-[10px] tabular-nums", tone(d))}>
              <span className="font-medium">{new Date(d.day).getDate()}</span>
              <span className="opacity-80">{d.committed || ""}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-4 text-xs text-muted"><span className="flex items-center gap-1"><i className="h-3 w-3 rounded bg-line/40" /> free</span><span className="flex items-center gap-1"><i className="h-3 w-3 rounded bg-good/40" /> booked</span><span className="flex items-center gap-1"><i className="h-3 w-3 rounded bg-warn/70" /> 60%+</span><span className="flex items-center gap-1"><i className="h-3 w-3 rounded bg-bad/80" /> 90%+</span></div>
      </Card>
    </>
  );
}
