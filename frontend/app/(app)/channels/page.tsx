"use client";

/**
 * /channels — estado de cada canal e integración externa.
 *
 * Consume `/admin/channels-status` (nuevo endpoint, admin/supervisor).
 *
 * Qué NO hace esta página: dar los secretos en plano ni permitir editar
 * credenciales. Todos los secretos viven en `/opt/multiagente/.env` del
 * server y se rotan por SSH. Exponerlos en la UI los filtraría en el
 * bundle del browser. Lo que sí hace: decir "configurado / no configurado"
 * para cada integración, mostrar valores NO sensibles (phone_number_id,
 * bucket R2, modelo OpenAI...) y warn si falta algo crítico.
 *
 * Auth: admin solo (los datos incluyen IDs que no queremos expuestos a
 * supervisors).
 */

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { RoleGate } from "@/lib/auth";
import { NoAccess } from "@/components/ui/coming-soon";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type ChannelKey =
  | "whatsapp_meta"
  | "botmaker"
  | "twilio"
  | "widget"
  | "zoho"
  | "mercadopago"
  | "rebill"
  | "openai"
  | "pinecone"
  | "cloudflare_r2"
  | "sentry"
  | "slack";

type ChannelStatus = {
  [K in ChannelKey]: {
    configured: boolean;
    [extra: string]: unknown;
  };
};

const LABELS: Record<ChannelKey, { label: string; group: "canales" | "integraciones" }> = {
  whatsapp_meta: { label: "WhatsApp Cloud API (Meta)", group: "canales" },
  botmaker:      { label: "Botmaker",                  group: "canales" },
  twilio:        { label: "Twilio WhatsApp",           group: "canales" },
  widget:        { label: "Widget web embebible",      group: "canales" },
  zoho:          { label: "Zoho CRM",                  group: "integraciones" },
  mercadopago:   { label: "MercadoPago",               group: "integraciones" },
  rebill:        { label: "Rebill",                    group: "integraciones" },
  openai:        { label: "OpenAI (LLM + Whisper + TTS)", group: "integraciones" },
  pinecone:      { label: "Pinecone (RAG)",            group: "integraciones" },
  cloudflare_r2: { label: "Cloudflare R2 (media)",     group: "integraciones" },
  sentry:        { label: "Sentry (errores)",          group: "integraciones" },
  slack:         { label: "Slack (alertas)",           group: "integraciones" },
};

export default function ChannelsPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <ChannelsInner />
    </RoleGate>
  );
}

function ChannelsInner() {
  const q = useQuery<ChannelStatus>({
    queryKey: ["channels", "status"],
    queryFn: () => api.get("/admin/channels-status"),
    refetchInterval: 60_000,
  });

  const keys = Object.keys(LABELS) as ChannelKey[];
  const canales       = keys.filter((k) => LABELS[k].group === "canales");
  const integraciones = keys.filter((k) => LABELS[k].group === "integraciones");

  const configCount = q.data
    ? keys.filter((k) => q.data![k]?.configured).length
    : 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-border">
        <h1 className="text-lg font-semibold">Canales e integraciones</h1>
        <p className="text-xs text-fg-dim mt-0.5">
          Estado de conexión. Los secretos se editan por SSH en{" "}
          <span className="font-mono">/opt/multiagente/.env</span>. Cambios requieren{" "}
          <span className="font-mono">docker compose restart api</span>.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto scroll-thin p-6 space-y-6 max-w-3xl">
        {q.isLoading && (
          <div className="text-xs text-fg-dim"><Loader2 className="inline w-3.5 h-3.5 animate-spin mr-2" />Cargando estado…</div>
        )}
        {q.error && (
          <div className="text-xs text-danger">{(q.error as Error).message}</div>
        )}

        {q.data && (
          <>
            <div className="bg-card border border-border rounded-lg px-3 py-2 flex items-center gap-3 text-xs">
              <CheckCircle2 className="w-4 h-4 text-success" />
              <div>
                <span className="font-semibold">{configCount} de {keys.length}</span>{" "}
                <span className="text-fg-dim">integraciones configuradas.</span>
              </div>
            </div>

            <Section title="Canales de entrada" keys={canales} data={q.data} />
            <Section title="Integraciones externas" keys={integraciones} data={q.data} />

            <div className="text-[11px] text-fg-dim pt-4 border-t border-border">
              <strong>Cómo editar credenciales:</strong>{" "}
              <code className="bg-bg px-1 rounded">ssh root@68.183.156.122</code> →{" "}
              <code className="bg-bg px-1 rounded">nano /opt/multiagente/.env</code> →{" "}
              <code className="bg-bg px-1 rounded">docker compose restart api</code>. La UI no
              lo hace para no exponer secretos en el bundle JS.
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  keys,
  data,
}: {
  title: string;
  keys: ChannelKey[];
  data: ChannelStatus;
}) {
  return (
    <section>
      <h2 className="text-sm font-semibold mb-2">{title}</h2>
      <div className="space-y-1.5">
        {keys.map((k) => {
          const meta = data[k] || { configured: false };
          const cfg = !!meta.configured;
          // Campos extra no-sensibles para mostrar.
          const extras: [string, string][] = Object.entries(meta)
            .filter(([key, val]) => key !== "configured" && val)
            .map(([key, val]) => [key, String(val)]);
          return (
            <div
              key={k}
              className="bg-card border border-border rounded-lg p-3 flex items-start gap-3"
            >
              {cfg ? (
                <CheckCircle2 className="w-4 h-4 text-success shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-4 h-4 text-fg-dim shrink-0 mt-0.5" />
              )}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium flex items-center gap-2">
                  {LABELS[k].label}
                  <span
                    className={cn(
                      "text-[9px] px-1.5 py-0.5 rounded",
                      cfg ? "bg-success/15 text-success" : "bg-border text-fg-dim",
                    )}
                  >
                    {cfg ? "configurado" : "no configurado"}
                  </span>
                </div>
                {extras.length > 0 && (
                  <div className="flex gap-3 mt-1 flex-wrap">
                    {extras.map(([key, val]) => (
                      <span key={key} className="text-[10px] text-fg-dim">
                        <span className="font-mono">{key}</span>:{" "}
                        <span className="font-mono text-fg-muted">{val}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
