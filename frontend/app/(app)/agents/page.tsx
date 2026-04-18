"use client";

/**
 * /agents — panel de agentes IA del sistema.
 *
 * No hay config dinámica (temperatura, tools) por agente — eso está
 * hardcoded en code. Lo que sí sirve acá es tener visibilidad de:
 *   - Qué agentes existen + qué hacen
 *   - Cuál es su prompt actual (link directo a /prompts)
 *   - Cómo está el router (link a /prompts → orquestador)
 *
 * Admin-only. Cuando se implementen los panels de config realtime (tools
 * en Redis, temperatura settable, etc.) esta página crece. Por ahora es un
 * indice informativo.
 */

import Link from "next/link";
import { ArrowRight, Bot, Headphones, MessageCircle, Wallet, Brain } from "lucide-react";
import { RoleGate } from "@/lib/auth";
import { NoAccess } from "@/components/ui/coming-soon";

type AgentInfo = {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  tools: string[];
  promptKey: string; // id usado en /prompts
};

const AGENTS: AgentInfo[] = [
  {
    key: "sales",
    label: "Ventas",
    icon: MessageCircle,
    description:
      "Clasifica interés, arma pitch con RAG sobre el catálogo de cursos por país, responde precios/cuotas/certificados y genera link de pago (MercadoPago / Rebill).",
    tools: ["RAG Pinecone", "Zoho Leads", "MercadoPago", "Rebill"],
    promptKey: "ventas",
  },
  {
    key: "closer",
    label: "Closer",
    icon: Brain,
    description:
      "Toma el handoff del agente de Ventas cuando el lead está caliente y empuja el cierre. Envía link de pago personalizado + cupón si corresponde.",
    tools: ["Rebill", "MercadoPago", "Zoho SalesOrders"],
    promptKey: "ventas",
  },
  {
    key: "collections",
    label: "Cobranzas",
    icon: Wallet,
    description:
      "Recupera deuda vencida. Consulta saldo en Zoho (módulo area_cobranzas), regenera links de pago expirados, ofrece planes de regularización, registra gestiones.",
    tools: ["Zoho Cobranzas", "Rebill", "MercadoPago"],
    promptKey: "cobranzas",
  },
  {
    key: "post_sales",
    label: "Post-venta",
    icon: Headphones,
    description:
      "Soporte para alumnos activos. Verifica inscripción en Zoho, gestiona acceso al LMS (Moodle/Blackboard/Tropos), procesa certificados, recibe tickets.",
    tools: ["Zoho Contacts", "LMS", "Tickets"],
    promptKey: "post_venta",
  },
  {
    key: "router",
    label: "Router (orquestador)",
    icon: Bot,
    description:
      "gpt-4o-mini clasifica el intent de cada mensaje y decide a qué agente rutear. Detecta keywords de handoff humano (HANDOFF_REQUIRED) y fuerza el escalamiento cuando corresponde.",
    tools: ["gpt-4o-mini"],
    promptKey: "orquestador",
  },
];

export default function AgentsPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <AgentsInner />
    </RoleGate>
  );
}

function AgentsInner() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-border">
        <h1 className="text-lg font-semibold">Agentes IA</h1>
        <p className="text-xs text-fg-dim mt-0.5">
          Arquitectura multi-agente con LangGraph. La config (modelo, temperatura, tools) vive en{" "}
          <span className="font-mono">agents/*/</span>. Los prompts se editan desde{" "}
          <Link href="/prompts" className="text-accent hover:underline">/prompts</Link>.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto scroll-thin p-6 space-y-3 max-w-3xl">
        {AGENTS.map((a) => {
          const Icon = a.icon;
          return (
            <div key={a.key} className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-accent/15 text-accent flex items-center justify-center shrink-0">
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="text-sm font-semibold">{a.label}</h2>
                    <span className="text-[10px] font-mono text-fg-dim">{a.key}</span>
                  </div>
                  <p className="text-xs text-fg-muted leading-relaxed">{a.description}</p>
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {a.tools.map((t) => (
                      <span
                        key={t}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-bg border border-border text-fg-muted"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-3 mt-3">
                    <Link
                      href={`/prompts`}
                      className="text-[11px] text-accent hover:underline inline-flex items-center gap-1"
                    >
                      Editar prompt ({a.promptKey})
                      <ArrowRight className="w-3 h-3" />
                    </Link>
                    <Link
                      href="/test-agent"
                      className="text-[11px] text-accent hover:underline inline-flex items-center gap-1"
                    >
                      Probar en sandbox
                      <ArrowRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          );
        })}

        <div className="text-[11px] text-fg-dim pt-4 border-t border-border">
          <strong>Nota:</strong> para cambiar el modelo, temperatura o tools hay que tocar el
          código (<span className="font-mono">agents/&lt;agente&gt;/agent.py</span>) y hacer un
          deploy. La UI de config dinámica todavía no existe.
        </div>
      </div>
    </div>
  );
}
