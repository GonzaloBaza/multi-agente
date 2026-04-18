"use client";

/**
 * /dashboard — panel consolidado con 3 tabs: Live, Histórico y Autónomo.
 *
 * Paridad con widget/dashboard.html (principal diferencia: usamos las cards
 * y componentes de la UI nueva, no Chart.js — los gráficos son barras
 * simples hechas con divs). Los tres tabs consumen los mismos endpoints que
 * la UI vieja:
 *   - Live:       /inbox/metrics  +  /api/inbox/conversations
 *   - Histórico:  /admin/reports/{overview,leaderboard,categories,timeline}
 *   - Autónomo:   /admin/autonomous/{status,recent,run-now,retry-now,toggle}
 *
 * Auth: supervisor+. Admin ve lo mismo que supervisor (no hay feature gated
 * solo a admin en este panel, aunque los endpoints /admin/reports y
 * /admin/autonomous requieren supervisor como mínimo).
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Bot,
  CheckCircle2,
  Clock,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  TrendingUp,
  Users,
  XCircle,
} from "lucide-react";
import { RoleGate } from "@/lib/auth";
import { NoAccess } from "@/components/ui/coming-soon";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Tab = "live" | "historico" | "autonomo";

export default function DashboardPage() {
  return (
    <RoleGate min="supervisor" denyFallback={<NoAccess requiredRole="supervisor o admin" />}>
      <DashboardInner />
    </RoleGate>
  );
}

function DashboardInner() {
  const [tab, setTab] = useState<Tab>("live");

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-border">
        <h1 className="text-lg font-semibold">Dashboard</h1>
        <p className="text-xs text-fg-dim mt-0.5">
          Métricas en vivo, reportes históricos y monitor del sistema autónomo.
        </p>
      </div>

      {/* Tabs */}
      <div className="px-6 border-b border-border flex gap-1">
        {(
          [
            { key: "live",      label: "🟢 En vivo",    icon: Activity },
            { key: "historico", label: "📈 Histórico",  icon: BarChart3 },
            { key: "autonomo",  label: "🤖 Autónomo",   icon: Bot },
          ] as const
        ).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              "px-4 py-2.5 text-xs font-medium -mb-px border-b-2 transition-colors",
              tab === key
                ? "border-accent text-fg"
                : "border-transparent text-fg-muted hover:text-fg",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto scroll-thin p-6">
        {tab === "live" && <LiveTab />}
        {tab === "historico" && <HistoricoTab />}
        {tab === "autonomo" && <AutonomoTab />}
      </div>
    </div>
  );
}

// ── Live tab ─────────────────────────────────────────────────────────────────

type Metrics = {
  today_total: number;
  today_human: number;
  today_bot: number;
  bot_containment: number;
  last_7_days: { date: string; total: number }[];
  agents: {
    name: string;
    email: string;
    role: string;
    status: string;
    handled: number;
    avg_response: string;
  }[];
  frt_summary?: { agent: string; avg_seconds: number; count: number }[];
  inactive_alerts?: { session_id: string; minutes: number }[];
};

function LiveTab() {
  const metricsQ = useQuery<Metrics>({
    queryKey: ["dashboard", "metrics"],
    queryFn: () => api.get("/inbox/metrics"),
    refetchInterval: 15_000,
  });

  const m = metricsQ.data;
  const maxDay = Math.max(1, ...(m?.last_7_days ?? []).map((d) => d.total));

  return (
    <div className="space-y-4">
      {metricsQ.isLoading && <Skeleton />}
      {metricsQ.error && (
        <div className="text-xs text-danger">{(metricsQ.error as Error).message}</div>
      )}

      {m && (
        <>
          <div className="grid grid-cols-4 gap-3">
            <KPI label="Conversaciones hoy"    value={m.today_total.toString()}                icon={Activity} />
            <KPI label="Con bot"               value={m.today_bot.toString()}                  icon={Bot} color="text-info" />
            <KPI label="Con humano"            value={m.today_human.toString()}                icon={Users} color="text-warn" />
            <KPI label="Contención del bot"    value={`${m.bot_containment}%`}                 icon={TrendingUp} color="text-success" />
          </div>

          {m.last_7_days?.length > 0 && (
            <Card title="Últimos 7 días">
              <div className="flex items-end gap-1 h-24">
                {m.last_7_days.map((d) => (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
                    <div
                      className="bg-accent/60 w-full rounded-t"
                      style={{ height: `${(d.total / maxDay) * 100}%`, minHeight: "2px" }}
                      title={`${d.total} convs`}
                    />
                    <div className="text-[9px] text-fg-dim">
                      {new Date(d.date).toLocaleDateString("es-AR", { weekday: "short" })}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {m.agents?.length > 0 && (
            <Card title={`Equipo (${m.agents.length})`}>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-fg-dim border-b border-border">
                    <th className="text-left font-normal py-1.5">Agente</th>
                    <th className="text-left font-normal">Email</th>
                    <th className="text-left font-normal">Rol</th>
                    <th className="text-left font-normal">Estado</th>
                    <th className="text-right font-normal">Resp. promedio</th>
                  </tr>
                </thead>
                <tbody>
                  {m.agents.map((a) => (
                    <tr key={a.email} className="border-b border-border/60">
                      <td className="py-1.5">{a.name}</td>
                      <td className="text-fg-dim">{a.email}</td>
                      <td>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-border">{a.role}</span>
                      </td>
                      <td>
                        <StatusPill status={a.status} />
                      </td>
                      <td className="text-right text-fg-dim">{a.avg_response}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}

          {(m.frt_summary?.length ?? 0) > 0 && (
            <Card title="First Response Time (por agente)">
              <div className="grid grid-cols-2 gap-3">
                {m.frt_summary!.map((f) => (
                  <div
                    key={f.agent}
                    className="bg-bg border border-border rounded p-2 text-xs flex justify-between"
                  >
                    <span>{f.agent}</span>
                    <span className="text-fg-dim">
                      {f.avg_seconds}s · {f.count} muestras
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {(m.inactive_alerts?.length ?? 0) > 0 && (
            <Card title="⚠️ Conversaciones humanas sin responder" variant="warn">
              <div className="space-y-1">
                {m.inactive_alerts!.map((alert) => (
                  <div
                    key={alert.session_id}
                    className="text-xs flex justify-between border-b border-border/50 py-1"
                  >
                    <span className="font-mono truncate">{alert.session_id}</span>
                    <span className="text-warn">{alert.minutes} min sin actividad</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

// ── Histórico tab ────────────────────────────────────────────────────────────

type Overview = {
  total: number;
  closed: number;
  won: number;
  lost: number;
  open_now: number;
  messages: number;
  conversion_rate: number;
};
type LBRow = { agent: string; closed: number; won: number; lost: number; resolved: number; conversion_rate: number };
type CatRow = { category: string; total: number };
type TLRow = { day: string; closed: number; won: number };

function HistoricoTab() {
  const [days, setDays] = useState(7);

  const overviewQ = useQuery<Overview>({
    queryKey: ["reports", "overview", days],
    queryFn: () => api.get(`/admin/reports/overview?days=${days}`),
  });
  const leaderboardQ = useQuery<{ rows: LBRow[] }>({
    queryKey: ["reports", "leaderboard", days],
    queryFn: () => api.get(`/admin/reports/leaderboard?days=${days}`),
  });
  const categoriesQ = useQuery<{ rows: CatRow[] }>({
    queryKey: ["reports", "categories", days],
    queryFn: () => api.get(`/admin/reports/categories?days=${days}`),
  });
  const timelineQ = useQuery<{ rows: TLRow[] }>({
    queryKey: ["reports", "timeline", days * 2],
    queryFn: () => api.get(`/admin/reports/timeline?days=${days * 2}`),
  });

  const maxTL = Math.max(1, ...(timelineQ.data?.rows ?? []).map((r) => r.closed));
  const maxCat = Math.max(1, ...(categoriesQ.data?.rows ?? []).map((r) => r.total));

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1">
        <span className="text-xs text-fg-muted mr-2">Rango:</span>
        {[7, 14, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={cn(
              "text-xs px-2.5 py-1 rounded border transition-colors",
              days === d
                ? "bg-accent/15 border-accent text-accent"
                : "bg-bg border-border text-fg-muted hover:text-fg",
            )}
          >
            {d}d
          </button>
        ))}
      </div>

      {overviewQ.isLoading ? (
        <Skeleton />
      ) : overviewQ.data ? (
        <div className="grid grid-cols-4 gap-3">
          <KPI label="Total"         value={overviewQ.data.total.toString()}      icon={Activity} />
          <KPI label="Cerradas"      value={overviewQ.data.closed.toString()}     icon={CheckCircle2} color="text-info" />
          <KPI label="Ventas"        value={overviewQ.data.won.toString()}        icon={TrendingUp} color="text-success" />
          <KPI label="Conversión"    value={`${overviewQ.data.conversion_rate}%`} icon={BarChart3} color="text-accent" />
          <KPI label="Descartados"   value={overviewQ.data.lost.toString()}       icon={XCircle} color="text-danger" />
          <KPI label="Abiertas ahora" value={overviewQ.data.open_now.toString()}  icon={Clock} color="text-warn" />
          <KPI label="Mensajes"       value={overviewQ.data.messages.toString()}  icon={Activity} />
        </div>
      ) : null}

      {(timelineQ.data?.rows.length ?? 0) > 0 && (
        <Card title="Timeline (cierres por día)">
          <div className="flex items-end gap-1 h-28">
            {timelineQ.data!.rows.map((r) => (
              <div key={r.day} className="flex-1 flex flex-col items-center gap-0.5">
                <div className="w-full flex flex-col justify-end h-full">
                  <div
                    className="bg-success/70 w-full"
                    style={{ height: `${(r.won / maxTL) * 100}%` }}
                    title={`${r.won} ventas`}
                  />
                  <div
                    className="bg-accent/50 w-full rounded-t"
                    style={{ height: `${((r.closed - r.won) / maxTL) * 100}%`, minHeight: "1px" }}
                    title={`${r.closed - r.won} cerradas (no venta)`}
                  />
                </div>
                <div className="text-[8px] text-fg-dim">
                  {new Date(r.day).toLocaleDateString("es-AR", { day: "numeric", month: "numeric" })}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-3 text-[10px] text-fg-dim mt-2">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-success/70 inline-block" /> Ventas
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-accent/50 inline-block" /> Cerradas (sin venta)
            </span>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3">
        {(leaderboardQ.data?.rows.length ?? 0) > 0 && (
          <Card title="Leaderboard de agentes">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-fg-dim border-b border-border">
                  <th className="text-left font-normal py-1">#</th>
                  <th className="text-left font-normal">Agente</th>
                  <th className="text-right font-normal">Cerradas</th>
                  <th className="text-right font-normal">Ventas</th>
                  <th className="text-right font-normal">Conv %</th>
                </tr>
              </thead>
              <tbody>
                {leaderboardQ.data!.rows.map((r, i) => (
                  <tr key={r.agent} className="border-b border-border/60">
                    <td className="py-1 text-fg-dim">{i + 1}</td>
                    <td>{r.agent}</td>
                    <td className="text-right">{r.closed}</td>
                    <td className="text-right text-success">{r.won}</td>
                    <td className="text-right font-semibold">{r.conversion_rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        {(categoriesQ.data?.rows.length ?? 0) > 0 && (
          <Card title="Categorías de cierre">
            <div className="space-y-1.5">
              {categoriesQ.data!.rows.map((r) => (
                <div key={r.category} className="text-xs">
                  <div className="flex justify-between mb-0.5">
                    <span>{r.category}</span>
                    <span className="text-fg-dim">{r.total}</span>
                  </div>
                  <div className="h-2 bg-bg rounded overflow-hidden">
                    <div
                      className="h-full bg-accent"
                      style={{ width: `${(r.total / maxCat) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

// ── Autónomo tab ─────────────────────────────────────────────────────────────

type AutoStatus = {
  scheduler_running: boolean;
  jobs: { id: string; name: string; next_run: string; trigger: string }[];
  last_run_stats: { last_run?: string; sent?: number; candidates?: number } | null;
  config: { enabled: boolean };
};
type AutoRecent = { recent: { phone: string; day: string; action: string; ttl_seconds: number }[] };

function AutonomoTab() {
  const qc = useQueryClient();

  const statusQ = useQuery<AutoStatus>({
    queryKey: ["autonomous", "status"],
    queryFn: () => api.get("/admin/autonomous/status"),
    refetchInterval: 20_000,
  });
  const recentQ = useQuery<AutoRecent>({
    queryKey: ["autonomous", "recent"],
    queryFn: () => api.get("/admin/autonomous/recent"),
    refetchInterval: 30_000,
  });

  const runNow = useMutation({
    mutationFn: () => api.post<{ ok: boolean; message: string }>("/admin/autonomous/run-now", {}),
    onSuccess: (r) => {
      alert(r.message || "Ciclo disparado");
      qc.invalidateQueries({ queryKey: ["autonomous"] });
    },
    onError: (e: Error) => alert(e.message),
  });

  const retryNow = useMutation({
    mutationFn: () => api.post<{ ok: boolean; message: string }>("/admin/autonomous/retry-now", {}),
    onSuccess: (r) => {
      alert(r.message || "Retry disparado");
      qc.invalidateQueries({ queryKey: ["autonomous"] });
    },
    onError: (e: Error) => alert(e.message),
  });

  const toggle = useMutation({
    mutationFn: () => api.post<{ enabled: boolean }>("/admin/autonomous/toggle", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["autonomous"] }),
    onError: (e: Error) => alert(e.message),
  });

  const enabled = statusQ.data?.config.enabled ?? false;
  const schedulerOk = statusQ.data?.scheduler_running ?? false;

  const formatTTL = (s: number) => {
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.round(s / 60)}m`;
    if (s < 86400) return `${Math.round(s / 3600)}h`;
    return `${Math.round(s / 86400)}d`;
  };

  return (
    <div className="space-y-4">
      {statusQ.isLoading && <Skeleton />}

      <div className="grid grid-cols-4 gap-3">
        <KPI
          label="Scheduler"
          value={schedulerOk ? (enabled ? "🟢 Activo" : "⏸ Pausado") : "🔴 Detenido"}
          icon={Bot}
          color={schedulerOk ? (enabled ? "text-success" : "text-warn") : "text-danger"}
        />
        <KPI
          label="Último ciclo"
          value={statusQ.data?.last_run_stats?.last_run
            ? new Date(statusQ.data.last_run_stats.last_run).toLocaleString("es-AR", {
                hour: "2-digit", minute: "2-digit", day: "numeric", month: "numeric",
              })
            : "—"}
          icon={Clock}
        />
        <KPI label="Enviados (último)" value={String(statusQ.data?.last_run_stats?.sent ?? 0)} icon={CheckCircle2} color="text-success" />
        <KPI label="Candidatos (último)" value={String(statusQ.data?.last_run_stats?.candidates ?? 0)} icon={Users} />
      </div>

      <div className="flex gap-2 flex-wrap">
        <Button size="sm" onClick={() => runNow.mutate()} disabled={runNow.isPending}>
          {runNow.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          Correr retargeting ahora
        </Button>
        <Button variant="outline" size="sm" onClick={() => retryNow.mutate()} disabled={retryNow.isPending}>
          {retryNow.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          Reactivar descartados
        </Button>
        <Button
          variant={enabled ? "warn" : "default"}
          size="sm"
          onClick={() => toggle.mutate()}
          disabled={toggle.isPending}
        >
          {enabled ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          {enabled ? "Pausar sistema" : "Reactivar sistema"}
        </Button>
      </div>

      {(statusQ.data?.jobs.length ?? 0) > 0 && (
        <Card title="Jobs programados">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-fg-dim border-b border-border">
                <th className="text-left font-normal py-1">Job</th>
                <th className="text-left font-normal">Trigger</th>
                <th className="text-right font-normal">Próxima ejecución</th>
              </tr>
            </thead>
            <tbody>
              {statusQ.data!.jobs.map((j) => (
                <tr key={j.id} className="border-b border-border/60">
                  <td className="py-1">{j.name}</td>
                  <td className="text-fg-dim font-mono text-[10px]">{j.trigger}</td>
                  <td className="text-right text-fg-dim">
                    {j.next_run
                      ? new Date(j.next_run).toLocaleString("es-AR", {
                          hour: "2-digit", minute: "2-digit", day: "numeric", month: "numeric",
                        })
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {(recentQ.data?.recent.length ?? 0) > 0 && (
        <Card title={`Acciones recientes (${recentQ.data!.recent.length})`}>
          <div className="max-h-80 overflow-y-auto scroll-thin">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-panel">
                <tr className="text-fg-dim border-b border-border">
                  <th className="text-left font-normal py-1">Teléfono</th>
                  <th className="text-left font-normal">Día</th>
                  <th className="text-left font-normal">Acción</th>
                  <th className="text-right font-normal">TTL restante</th>
                </tr>
              </thead>
              <tbody>
                {recentQ.data!.recent.map((r, i) => (
                  <tr key={`${r.phone}-${i}`} className="border-b border-border/60">
                    <td className="py-1 font-mono text-[10px]">{r.phone}</td>
                    <td>{r.day}</td>
                    <td>
                      <span
                        className={cn(
                          "text-[9px] px-1.5 py-0.5 rounded",
                          r.action === "sent" || r.action === "enviado"
                            ? "bg-success/15 text-success"
                            : "bg-border text-fg-dim",
                        )}
                      >
                        {r.action}
                      </span>
                    </td>
                    <td className="text-right text-fg-dim">{formatTTL(r.ttl_seconds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

// ── Shared components ────────────────────────────────────────────────────────

function KPI({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
}) {
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2 flex items-center gap-3">
      <Icon className={cn("w-4 h-4 text-fg-muted", color)} />
      <div className="min-w-0">
        <div className="text-[10px] text-fg-dim uppercase truncate">{label}</div>
        <div className="text-sm font-semibold truncate">{value}</div>
      </div>
    </div>
  );
}

function Card({
  title,
  variant = "default",
  children,
}: {
  title: string;
  variant?: "default" | "warn";
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "border rounded-lg p-3",
        variant === "warn" ? "bg-warn/10 border-warn/30" : "bg-card border-border",
      )}
    >
      <div className="text-xs font-semibold mb-2">{title}</div>
      {children}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="flex items-center justify-center py-8 text-xs text-fg-dim">
      <Loader2 className="w-4 h-4 animate-spin mr-2" /> Cargando…
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const s = status.toLowerCase();
  const color =
    s === "available" || s === "online" ? "bg-success/15 text-success"
    : s === "busy" ? "bg-warn/15 text-warn"
    : s === "away" ? "bg-info/15 text-info"
    : "bg-border text-fg-dim";
  return <span className={cn("text-[9px] px-1.5 py-0.5 rounded", color)}>{status}</span>;
}
