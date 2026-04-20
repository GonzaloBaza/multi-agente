"use client";

/**
 * /pipeline — Kanban de conversaciones agrupadas por cola IA.
 *
 * Columnas: Ventas / Cobranzas / Post-venta — las tres colas que maneja el
 * router de agentes IA. Cada card es una conversación con:
 *   - Info del cliente (nombre, avatar, país)
 *   - Lifecycle (new/hot/customer/cold) como badge colorado
 *   - Ultima actividad (relative)
 *   - Canal (whatsapp/widget)
 *   - Agente asignado (si hay humano)
 *   - Flags (needs_human, bot_paused)
 *   - Menú contextual para MOVER de cola → PATCH backend
 *
 * El drag-and-drop real (arrastrar cards entre columnas) requiere instalar
 * @dnd-kit — lo dejamos para una iteración futura. Por ahora el move se
 * hace desde el menú "..." de cada card.
 *
 * Uso: supervisor+ puede ver y mover. Agente solo ve SUS convs (filtrado
 * por backend según rol).
 *
 * Auto-refresh: 30s via TanStack Query refetchInterval. Para realtime real
 * se puede subscribir al SSE de /inbox/stream y reactuar a "queue_changed"
 * events, pero el polling es suficiente para un kanban operativo.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Loader2,
  RefreshCw,
  MoreVertical,
  ArrowRight,
  Bot,
  UserCog,
  Clock,
  Flame,
  Snowflake,
  Sparkles,
  Award,
  MessageSquare,
  Phone,
  Globe,
  Pause,
  AlertCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { Flag } from "@/components/ui/flag";
import { Button } from "@/components/ui/button";
import { RoleGate } from "@/lib/auth";
import { NoAccess } from "@/components/ui/coming-soon";
import {
  QUEUE_LABEL,
  type ConversationListItem,
  type LifecycleStage,
  type Queue,
} from "@/lib/mock-data";
import { cn } from "@/lib/utils";

const COLUMNS: { queue: Queue; label: string; color: string; borderColor: string }[] = [
  { queue: "sales", label: "Ventas", color: "text-accent", borderColor: "border-accent/30" },
  { queue: "billing", label: "Cobranzas", color: "text-warn", borderColor: "border-warn/30" },
  { queue: "post-sales", label: "Post-venta", color: "text-info", borderColor: "border-info/30" },
];

const LIFECYCLE_META: Record<
  LifecycleStage,
  { label: string; color: string; icon: React.ComponentType<{ className?: string }> }
> = {
  new: { label: "Nuevo", color: "text-info bg-info/15", icon: Sparkles },
  hot: { label: "Hot", color: "text-danger bg-danger/15", icon: Flame },
  customer: { label: "Cliente", color: "text-success bg-success/15", icon: Award },
  cold: { label: "Cold", color: "text-fg-dim bg-fg-dim/15", icon: Snowflake },
};

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const diffSec = Math.round((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return "ahora";
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h`;
  return `${Math.round(diffSec / 86400)}d`;
}

export default function PipelinePage() {
  return (
    <RoleGate min="supervisor" denyFallback={<NoAccess requiredRole="supervisor o admin" />}>
      <Inner />
    </RoleGate>
  );
}

function Inner() {
  const qc = useQueryClient();
  const [lifecycleFilter, setLifecycleFilter] = useState<LifecycleStage | "all">("all");
  const [statusFilter, setStatusFilter] = useState<"open" | "pending" | "all">("open");

  const convsQ = useQuery<ConversationListItem[]>({
    queryKey: ["pipeline", "conversations", statusFilter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "200" });
      if (statusFilter !== "all") params.set("status", statusFilter);
      return api.get(`/inbox/conversations?${params.toString()}`);
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const moveQueue = useMutation({
    mutationFn: ({ convId, queue }: { convId: string; queue: Queue }) =>
      api.post(`/inbox/conversations/${convId}/queue`, { queue }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline", "conversations"] });
    },
    onError: (e: Error) => alert(e.message),
  });

  const grouped = useMemo(() => {
    const byQueue: Record<Queue, ConversationListItem[]> = {
      sales: [],
      billing: [],
      "post-sales": [],
    };
    for (const c of convsQ.data ?? []) {
      if (lifecycleFilter !== "all" && c.lifecycle !== lifecycleFilter) continue;
      const q = c.queue || "sales";
      if (!byQueue[q]) continue;
      byQueue[q].push(c);
    }
    return byQueue;
  }, [convsQ.data, lifecycleFilter]);

  const totalFiltered =
    grouped.sales.length + grouped.billing.length + grouped["post-sales"].length;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-lg font-semibold">Pipeline</h1>
          <p className="text-xs text-fg-dim mt-0.5">
            Kanban de conversaciones agrupadas por cola IA. Mové entre colas
            desde el menú de cada card.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Filtro lifecycle */}
          <select
            value={lifecycleFilter}
            onChange={(e) => setLifecycleFilter(e.target.value as LifecycleStage | "all")}
            className="bg-bg border border-border rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-accent"
          >
            <option value="all">Todos los lifecycle</option>
            <option value="hot">🔥 Hot leads</option>
            <option value="new">✨ Nuevos</option>
            <option value="customer">🏆 Clientes</option>
            <option value="cold">❄ Cold</option>
          </select>
          {/* Filtro status */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as "open" | "pending" | "all")}
            className="bg-bg border border-border rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-accent"
          >
            <option value="open">Abiertas</option>
            <option value="pending">Pendientes</option>
            <option value="all">Todas</option>
          </select>
          <Button
            size="sm"
            variant="outline"
            onClick={() => convsQ.refetch()}
            disabled={convsQ.isFetching}
          >
            <RefreshCw className={cn("w-3.5 h-3.5", convsQ.isFetching && "animate-spin")} />
            Refrescar
          </Button>
        </div>
      </div>

      {/* Toolbar info */}
      <div className="px-6 py-2 border-b border-border text-[11px] text-fg-dim flex items-center gap-4">
        <span>
          <span className="font-medium text-fg">{totalFiltered}</span> conversaciones
          {lifecycleFilter !== "all" && (
            <span> · lifecycle: <span className="text-fg">{LIFECYCLE_META[lifecycleFilter].label}</span></span>
          )}
        </span>
        <span>· Auto-refresh 30s</span>
      </div>

      {convsQ.isLoading ? (
        <div className="flex-1 flex items-center justify-center text-fg-dim">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : (
        <div className="flex-1 overflow-x-auto scroll-thin">
          <div className="flex gap-4 p-4 min-h-full" style={{ minWidth: "1200px" }}>
            {COLUMNS.map((col) => (
              <Column
                key={col.queue}
                queue={col.queue}
                label={col.label}
                color={col.color}
                borderColor={col.borderColor}
                convs={grouped[col.queue]}
                onMove={(convId, q) => moveQueue.mutate({ convId, queue: q })}
                moving={moveQueue.isPending}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Column({
  queue,
  label,
  color,
  borderColor,
  convs,
  onMove,
  moving,
}: {
  queue: Queue;
  label: string;
  color: string;
  borderColor: string;
  convs: ConversationListItem[];
  onMove: (convId: string, queue: Queue) => void;
  moving: boolean;
}) {
  return (
    <div className={cn("flex-1 min-w-[320px] bg-card rounded-lg border flex flex-col overflow-hidden", borderColor)}>
      <div className={cn("px-3 py-2.5 border-b flex items-center justify-between", borderColor)}>
        <div className="flex items-center gap-2">
          <span className={cn("w-2 h-2 rounded-full", color.replace("text-", "bg-"))} />
          <span className="text-sm font-semibold">{label}</span>
          <span className="text-[10px] text-fg-dim tabular-nums">({convs.length})</span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto scroll-thin p-2 space-y-2">
        {convs.length === 0 && (
          <div className="text-[11px] text-fg-dim italic text-center py-8">
            Sin conversaciones
          </div>
        )}
        {convs.map((c) => (
          <Card key={c.id} conv={c} onMove={onMove} moving={moving} currentQueue={queue} />
        ))}
      </div>
    </div>
  );
}

function Card({
  conv,
  onMove,
  moving,
  currentQueue,
}: {
  conv: ConversationListItem;
  onMove: (convId: string, queue: Queue) => void;
  moving: boolean;
  currentQueue: Queue;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const lifecycleMeta = LIFECYCLE_META[conv.lifecycle];
  const LifecycleIcon = lifecycleMeta.icon;
  const targetQueues = COLUMNS.filter((c) => c.queue !== currentQueue);

  return (
    <div className="bg-bg border border-border rounded-md p-2.5 hover:border-accent/50 transition-colors relative group">
      {/* Header: avatar + nombre + menú */}
      <div className="flex items-start gap-2 mb-1.5">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-pink-500 to-fuchsia-600 text-white text-[9px] font-bold flex items-center justify-center shrink-0">
          {conv.contact.initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            <Flag iso={conv.contact.country} size={10} />
            <span className="text-xs font-medium truncate">{conv.contact.name}</span>
          </div>
          <div className="text-[10px] text-fg-dim tabular-nums">
            {formatRelative(conv.lastMessageAt)}
          </div>
        </div>
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="opacity-0 group-hover:opacity-100 text-fg-dim hover:text-fg p-0.5"
          title="Mover / acciones"
          aria-label="Menú de acciones"
        >
          <MoreVertical className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Badges: lifecycle + flags */}
      <div className="flex items-center gap-1 mb-1.5 flex-wrap">
        <span className={cn("text-[9px] px-1.5 py-0.5 rounded flex items-center gap-0.5", lifecycleMeta.color)}>
          <LifecycleIcon className="w-2.5 h-2.5" /> {lifecycleMeta.label}
        </span>
        {conv.needsHuman && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-warn/15 text-warn flex items-center gap-0.5">
            <UserCog className="w-2.5 h-2.5" /> Necesita humano
          </span>
        )}
        {conv.botPaused && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-fg-dim/15 text-fg-dim flex items-center gap-0.5">
            <Pause className="w-2.5 h-2.5" /> Bot pausado
          </span>
        )}
        {conv.channel === "whatsapp" ? (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-success/10 text-success flex items-center gap-0.5">
            <Phone className="w-2.5 h-2.5" /> WhatsApp
          </span>
        ) : (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-info/10 text-info flex items-center gap-0.5">
            <Globe className="w-2.5 h-2.5" /> Widget
          </span>
        )}
      </div>

      {/* Último mensaje (preview) */}
      <div className="text-[11px] text-fg-dim line-clamp-2 leading-snug mb-1.5">
        {conv.lastMessage}
      </div>

      {/* Acción: abrir en inbox */}
      <Link
        href={`/inbox?c=${conv.id}`}
        className="inline-flex items-center gap-1 text-[10px] text-accent hover:underline"
      >
        Abrir en inbox <ArrowRight className="w-2.5 h-2.5" />
      </Link>

      {/* Menú contextual */}
      {menuOpen && (
        <div
          className="absolute top-7 right-2 z-10 bg-panel border border-border rounded-md shadow-lg py-1 w-44"
          onMouseLeave={() => setMenuOpen(false)}
        >
          <div className="px-2 py-1 text-[9px] uppercase tracking-wider text-fg-muted">
            Mover a cola
          </div>
          {targetQueues.map((tq) => (
            <button
              key={tq.queue}
              onClick={() => {
                onMove(conv.id, tq.queue);
                setMenuOpen(false);
              }}
              disabled={moving}
              className="w-full text-left px-2 py-1.5 text-[11px] hover:bg-hover transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              <span className={cn("w-2 h-2 rounded-full", tq.color.replace("text-", "bg-"))} />
              {tq.label}
            </button>
          ))}
          <div className="border-t border-border mt-1 pt-1 px-2 py-1">
            <Link
              href={`/inbox?c=${conv.id}`}
              className="text-[11px] text-accent hover:underline flex items-center gap-1"
              onClick={() => setMenuOpen(false)}
            >
              <MessageSquare className="w-2.5 h-2.5" /> Abrir en inbox
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
