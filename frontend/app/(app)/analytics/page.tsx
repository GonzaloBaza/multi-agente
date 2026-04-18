"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, MessageSquare, Users, TrendingUp, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { Flag } from "@/components/ui/flag";

type Analytics = {
  totals: { conversations: number; messages: number; active_today: number; resolved: number };
  daily: { day: string; count: number }[];
  by_channel: Record<string, number>;
  by_queue: Record<string, number>;
  by_country: Record<string, number>;
  by_lifecycle: Record<string, number>;
};

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const q = useQuery<Analytics>({
    queryKey: ["analytics", days],
    queryFn: () => api.get(`/inbox/analytics?days=${days}`),
    staleTime: 60_000,
  });

  if (q.isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-fg-dim">
        <Loader2 className="w-5 h-5 animate-spin" />
      </div>
    );
  }
  if (!q.data) return <div className="flex-1 flex items-center justify-center text-fg-dim">Sin datos</div>;
  const d = q.data;
  const maxDaily = Math.max(1, ...d.daily.map((x) => x.count));

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Analytics</h1>
          <p className="text-xs text-fg-dim mt-0.5">Métricas operativas del bot</p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="bg-bg border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        >
          <option value={7}>Últimos 7 días</option>
          <option value={30}>Últimos 30 días</option>
          <option value={90}>Últimos 90 días</option>
        </select>
      </div>

      <div className="flex-1 overflow-y-auto scroll-thin p-6 space-y-6">
        {/* Totals */}
        <div className="grid grid-cols-4 gap-4">
          <Stat icon={<MessageSquare className="w-4 h-4 text-accent" />} label="Conversaciones" value={d.totals.conversations} />
          <Stat icon={<Users className="w-4 h-4 text-info" />} label="Mensajes" value={d.totals.messages} />
          <Stat icon={<TrendingUp className="w-4 h-4 text-warn" />} label="Activas hoy" value={d.totals.active_today} />
          <Stat icon={<CheckCircle2 className="w-4 h-4 text-success" />} label="Resueltas" value={d.totals.resolved} />
        </div>

        {/* Daily chart */}
        <Card title="Conversaciones por día">
          <div className="flex items-end gap-1 h-40">
            {d.daily.map((day) => (
              <div key={day.day} className="flex-1 flex flex-col items-center gap-1 group">
                <div className="text-[9px] text-fg-dim opacity-0 group-hover:opacity-100 transition-opacity">
                  {day.count}
                </div>
                <div
                  className="w-full bg-accent/30 hover:bg-accent rounded-t transition-colors"
                  style={{ height: `${(day.count / maxDaily) * 100}%`, minHeight: 2 }}
                  title={`${day.day}: ${day.count} convs`}
                />
              </div>
            ))}
          </div>
          <div className="text-[10px] text-fg-dim mt-1 text-center">
            {d.daily[0]?.day} → {d.daily[d.daily.length - 1]?.day}
          </div>
        </Card>

        <div className="grid grid-cols-2 gap-4">
          <Card title="Por canal">
            <BreakdownList data={d.by_channel} />
          </Card>
          <Card title="Por cola de atención">
            <BreakdownList data={d.by_queue} />
          </Card>
          <Card title="Por país (top 10)">
            <BreakdownList data={d.by_country} renderKey={(k) => (
              <span className="flex items-center gap-1.5"><Flag iso={k} size={10} /> {k}</span>
            )} />
          </Card>
          <Card title="Por lifecycle">
            <BreakdownList data={d.by_lifecycle} />
          </Card>
        </div>
      </div>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center gap-2 text-xs text-fg-dim">{icon} {label}</div>
      <div className="text-2xl font-bold mt-1 tabular-nums">{value.toLocaleString("es-AR")}</div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="text-[10px] uppercase tracking-wider text-fg-muted mb-3">{title}</div>
      {children}
    </div>
  );
}

function BreakdownList({ data, renderKey }: { data: Record<string, number>; renderKey?: (k: string) => React.ReactNode }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([_, v]) => v));
  if (entries.length === 0) return <div className="text-fg-dim text-xs italic">Sin datos</div>;
  return (
    <div className="space-y-1.5">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center gap-3">
          <div className="text-xs flex-1 truncate">{renderKey ? renderKey(k) : k}</div>
          <div className="flex-1 bg-bg rounded h-1.5 relative">
            <div className="bg-accent h-1.5 rounded" style={{ width: `${(v / max) * 100}%` }} />
          </div>
          <div className="text-xs tabular-nums text-fg w-10 text-right">{v}</div>
        </div>
      ))}
    </div>
  );
}
