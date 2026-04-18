"use client";

/**
 * /test-agent — sandbox para probar agentes IA sin impactar conversaciones
 * reales.
 *
 * Paridad con widget/test-agent.html: left panel de configuración (país,
 * canal, forzar agente) + chat interactivo a la derecha que muestra qué
 * agente respondió, si pidió handoff, si envió link Rebill, y la latencia.
 *
 * La config NO persiste entre sesiones — intencional: cada vez que abrís
 * la página arrancás en limpio. El historial NO se guarda en la DB real.
 *
 * Auth: supervisor+.
 */

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Send, Trash2 } from "lucide-react";
import { RoleGate } from "@/lib/auth";
import { NoAccess } from "@/components/ui/coming-soon";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Role = "user" | "assistant";
type Msg = {
  role: Role;
  content: string;
  meta?: {
    agent?: string;
    handoff?: boolean;
    handoff_reason?: string;
    link_rebill?: boolean;
    latency_ms?: number;
  };
};

type TestAgentBody = {
  message: string;
  history: { role: Role; content: string }[];
  country: string;
  channel: string;
  forced_agent: string | null;
};

type TestAgentResponse = {
  response: string;
  agent_used: string;
  handoff_requested: boolean;
  handoff_reason: string;
  link_rebill_enviado: boolean;
  latency_ms: number;
};

const COUNTRIES = ["AR", "MX", "CL", "CO", "EC", "UY", "PE"];
const CHANNELS = ["widget", "whatsapp"];
const AGENTS = [
  { value: null,          label: "Auto (router)" },
  { value: "sales",       label: "Ventas" },
  { value: "collections", label: "Cobranzas" },
  { value: "post_sales",  label: "Post-venta" },
  { value: "closer",      label: "Closer" },
];

export default function TestAgentPage() {
  return (
    <RoleGate min="supervisor" denyFallback={<NoAccess requiredRole="supervisor o admin" />}>
      <TestAgentInner />
    </RoleGate>
  );
}

function TestAgentInner() {
  const [country, setCountry] = useState("AR");
  const [channel, setChannel] = useState("widget");
  const [forcedAgent, setForcedAgent] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  const send = useMutation({
    mutationFn: (text: string) => {
      const history = msgs.map((m) => ({ role: m.role, content: m.content }));
      const body: TestAgentBody = {
        message: text,
        history,
        country,
        channel,
        forced_agent: forcedAgent,
      };
      return api.post<TestAgentResponse>("/admin/test-agent", body);
    },
    onSuccess: (r) => {
      setMsgs((prev) => [
        ...prev,
        {
          role: "assistant",
          content: r.response,
          meta: {
            agent: r.agent_used,
            handoff: r.handoff_requested,
            handoff_reason: r.handoff_reason,
            link_rebill: r.link_rebill_enviado,
            latency_ms: r.latency_ms,
          },
        },
      ]);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 0);
    },
    onError: (e: Error) => {
      setMsgs((prev) => [...prev, { role: "assistant", content: `⚠️ ${e.message}` }]);
    },
  });

  const handleSend = () => {
    const text = input.trim();
    if (!text || send.isPending) return;
    setMsgs((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    send.mutate(text);
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 0);
  };

  const avgLatency = (() => {
    const withLatency = msgs.filter((m) => m.meta?.latency_ms);
    if (withLatency.length === 0) return null;
    const sum = withLatency.reduce((acc, m) => acc + (m.meta?.latency_ms ?? 0), 0);
    return Math.round(sum / withLatency.length);
  })();

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Config panel */}
      <aside className="w-64 border-r border-border bg-panel p-4 space-y-4 overflow-y-auto scroll-thin">
        <div>
          <h1 className="text-sm font-semibold">Test Agent</h1>
          <p className="text-[11px] text-fg-dim mt-0.5">
            Sandbox. No persiste nada en la DB real.
          </p>
        </div>

        <div>
          <label className="text-[10px] text-fg-muted uppercase block mb-1">País</label>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="w-full h-8 px-2 bg-bg border border-border rounded text-sm"
          >
            {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label className="text-[10px] text-fg-muted uppercase block mb-1">Canal</label>
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            className="w-full h-8 px-2 bg-bg border border-border rounded text-sm"
          >
            {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label className="text-[10px] text-fg-muted uppercase block mb-1">Forzar agente</label>
          <div className="flex flex-col gap-1">
            {AGENTS.map((a) => (
              <button
                key={a.label}
                onClick={() => setForcedAgent(a.value)}
                className={cn(
                  "text-left text-xs px-2 py-1 rounded border transition-colors",
                  forcedAgent === a.value
                    ? "bg-accent/15 border-accent text-accent"
                    : "bg-bg border-border text-fg-muted hover:text-fg",
                )}
              >
                {a.label}
              </button>
            ))}
          </div>
          <div className="text-[10px] text-fg-dim mt-1">
            "Auto" deja que el router clasifique el intent.
          </div>
        </div>

        <div className="pt-3 border-t border-border space-y-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (msgs.length === 0 || confirm("Limpiar la conversación?"))
                setMsgs([]);
            }}
            className="w-full"
          >
            <Trash2 className="w-3.5 h-3.5" /> Limpiar conversación
          </Button>
        </div>
      </aside>

      {/* Chat */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
          <div className="text-sm font-semibold">Conversación de prueba</div>
          <div className="flex gap-2 text-[10px] text-fg-dim">
            <span>{msgs.length} mensajes</span>
            {avgLatency !== null && (
              <span>· latencia media {avgLatency}ms</span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto scroll-thin p-4 space-y-3">
          {msgs.length === 0 && (
            <div className="text-center text-xs text-fg-dim py-12">
              Escribí un mensaje abajo para empezar a probar el agente.
            </div>
          )}
          {msgs.map((m, i) => (
            <div
              key={i}
              className={cn(
                "flex gap-2",
                m.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[70%] rounded-lg px-3 py-2 text-sm",
                  m.role === "user"
                    ? "bg-accent text-white"
                    : "bg-card border border-border",
                )}
              >
                <div className="whitespace-pre-wrap break-words">{m.content}</div>
                {m.meta && (
                  <div className="flex gap-1 mt-1.5 flex-wrap">
                    {m.meta.agent && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-border/60 text-fg-dim">
                        agente: {m.meta.agent}
                      </span>
                    )}
                    {m.meta.handoff && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-warn/20 text-warn">
                        handoff: {m.meta.handoff_reason || "si"}
                      </span>
                    )}
                    {m.meta.link_rebill && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-success/20 text-success">
                        🔗 link Rebill enviado
                      </span>
                    )}
                    {m.meta.latency_ms !== undefined && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-border/60 text-fg-dim">
                        {m.meta.latency_ms}ms
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {send.isPending && (
            <div className="flex gap-2 justify-start">
              <div className="bg-card border border-border rounded-lg px-3 py-2 text-sm text-fg-dim flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Pensando…
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="border-t border-border p-3">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Escribí un mensaje… (Enter envía, Shift+Enter nueva línea)"
              rows={2}
              className="flex-1 resize-none p-2 bg-bg border border-border rounded text-sm outline-none focus:ring-1 focus:ring-accent"
              disabled={send.isPending}
            />
            <Button onClick={handleSend} disabled={!input.trim() || send.isPending}>
              {send.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Send className="w-3.5 h-3.5" />
              )}
              Enviar
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
