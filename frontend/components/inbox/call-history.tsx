"use client";

/**
 * Historial de llamadas del contacto — lee desde Zoho Voice via
 * GET /api/v1/voice/logs?phone=...
 *
 * Se renderiza dentro del `ContactPanel` del inbox, debajo de Cobranzas.
 * Las llamadas NO las iniciamos desde acá; eso lo hace la extensión
 * ZDialer en el browser del agente (ver doc en `api/voice.py`). Este
 * componente solo MUESTRA el historial para dar contexto al agente antes
 * de marcar.
 *
 * Si el contacto no tiene teléfono → no se renderiza (return null).
 * Si Zoho tira error o timeout → mensaje discreto, no crash.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Phone, PhoneIncoming, PhoneOutgoing, PhoneMissed, Clock, Loader2, RefreshCw,
  ChevronDown, ChevronUp,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type CallLog = {
  logid: string;
  direction: "outgoing" | "incoming" | "missed" | "bridged" | "forward" | null;
  start: string | null;  // ISO
  end: string | null;
  duration: string | null; // "MM:SS"
  from_number: string | null;
  to_number: string | null;
  customer_number: string | null;
  did_number: string | null;
  agent_name: string | null;
  hangup_cause: string | null;
  hangup_detail: string | null;
  disconnected_by: string | null;
  recording_status: string | null;
};

type LogsResponse = { logs: CallLog[]; count: number };

function DirectionIcon({ direction }: { direction: CallLog["direction"] }) {
  const common = "w-3 h-3 shrink-0";
  if (direction === "outgoing") return <PhoneOutgoing className={cn(common, "text-info")} />;
  if (direction === "incoming") return <PhoneIncoming className={cn(common, "text-success")} />;
  if (direction === "missed") return <PhoneMissed className={cn(common, "text-danger")} />;
  return <Phone className={cn(common, "text-fg-dim")} />;
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diffSec = Math.round((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return "hace segs";
  if (diffSec < 3600) return `hace ${Math.round(diffSec / 60)}m`;
  if (diffSec < 86400) return `hace ${Math.round(diffSec / 3600)}h`;
  if (diffSec < 86400 * 7) return `hace ${Math.round(diffSec / 86400)}d`;
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
}

export function CallHistory({ phone }: { phone: string | null | undefined }) {
  const enabled = !!phone;
  const [open, setOpen] = useState(true);

  const { data, isLoading, error, refetch, isFetching } = useQuery<LogsResponse>({
    queryKey: ["voice", "logs", phone],
    queryFn: () => api.get(`/voice/logs?phone=${encodeURIComponent(phone!)}&limit=10`),
    enabled: enabled && open, // no fetchea si está cerrado — ahorra call a Zoho
    staleTime: 60_000, // 1 min — no spameamos Zoho
    retry: 1,
  });

  if (!enabled) return null;

  const logs = data?.logs ?? [];

  return (
    <div className="border border-border rounded-md overflow-hidden">
      {/* Header colapsable — mismo patrón que Contacto/Cobranzas. */}
      <div className="bg-card px-3 py-2 flex items-center justify-between border-b border-border gap-2">
        <button
          onClick={() => setOpen((s) => !s)}
          className="text-[10px] uppercase tracking-wider font-semibold text-fg-muted hover:text-fg flex-1 text-left flex items-center gap-1.5"
        >
          <Phone className="w-3 h-3" />
          Llamadas
          {logs.length > 0 && (
            <span className="text-fg-dim normal-case">({logs.length})</span>
          )}
        </button>
        <div className="flex items-center gap-2">
          {open && (
            <button
              onClick={() => refetch()}
              className="text-fg-dim hover:text-fg p-0.5"
              disabled={isFetching}
              title="Refrescar"
            >
              <RefreshCw className={cn("w-3 h-3", isFetching && "animate-spin")} />
            </button>
          )}
          <button
            onClick={() => setOpen((s) => !s)}
            className="text-fg-dim hover:text-fg p-0.5"
            aria-label={open ? "Colapsar" : "Expandir"}
          >
            {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="p-3">
          {isLoading && (
            <div className="flex items-center gap-2 text-[11px] text-fg-dim">
              <Loader2 className="w-3 h-3 animate-spin" /> Consultando Zoho Voice…
            </div>
          )}
          {error && (
            <div className="text-[11px] text-fg-dim">
              No pudimos traer el historial de llamadas.
            </div>
          )}
          {!isLoading && !error && logs.length === 0 && (
            <div className="text-[11px] text-fg-dim">Sin llamadas registradas.</div>
          )}
          <ul className="space-y-2">
            {logs.map((log) => (
              <li key={log.logid} className="flex items-start gap-2">
                <DirectionIcon direction={log.direction} />
                <div className="flex-1 min-w-0 text-[11px]">
                  <div className="flex items-baseline gap-2">
                    <span className="font-medium truncate">
                      {log.agent_name || "—"}
                    </span>
                    <span className="text-fg-dim text-[10px] shrink-0">
                      {formatRelative(log.start)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-fg-dim text-[10px] mt-0.5">
                    <Clock className="w-2.5 h-2.5" />
                    <span className="tabular-nums">{log.duration || "0:00"}</span>
                    {log.hangup_cause && (
                      <>
                        <span>·</span>
                        <span className="truncate">{log.hangup_cause}</span>
                      </>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {/* Hint sobre ZDialer — solo cuando no hay llamadas y no está cargando */}
          {logs.length === 0 && !isLoading && !error && (
            <div className="mt-2 pt-2 border-t border-border text-[10px] text-fg-dim leading-snug">
              Para llamar: instalá la{" "}
              <a
                href="https://chromewebstore.google.com/detail/zdialer-zoho-voice-extens/gnpglhdhioifppkjdpmlmolgeanpaofi"
                target="_blank"
                rel="noreferrer"
                className="text-accent hover:underline"
              >
                extensión ZDialer
              </a>
              . Al clickear el teléfono se dispara la llamada.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
