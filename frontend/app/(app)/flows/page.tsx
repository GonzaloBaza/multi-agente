"use client";

/**
 * /flows — gestión de flows del widget (lista + activate/delete + widget
 * config).
 *
 * El BUILDER visual (Drawflow) NO se migró — requiere replicar un canvas
 * con drag & drop + propiedades por nodo que es un producto entero en sí
 * mismo. Para editar la topología del flujo sigue viviendo la UI vieja en
 * `/admin/flows-ui`. Acá damos:
 *   - Lista + estado activo/inactivo con toggle
 *   - Borrar flows
 *   - Editar config del widget (título, color, saludo, posición) — esto no
 *     es el flow, es la apariencia del widget embebible, lo mantenemos acá
 *     porque es texto + color picker (no canvas).
 *
 * Auth: admin para escribir, supervisor puede leer.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Edit3, Loader2, Plus, Save, Trash2 } from "lucide-react";
import { RoleGate, useRole } from "@/lib/auth";
import { NoAccess } from "@/components/ui/coming-soon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Flow = { name: string; active: boolean };

type WidgetConfig = {
  title: string;
  color: string;
  greeting: string;
  avatar: string;
  quick_replies: string;
  position: "right" | "left";
};

export default function FlowsPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <FlowsInner />
    </RoleGate>
  );
}

function FlowsInner() {
  const qc = useQueryClient();
  const { isAdmin } = useRole();

  const flowsQ = useQuery<Flow[]>({
    queryKey: ["flows", "list"],
    queryFn: () => api.get("/admin/flows/list"),
  });

  const toggle = useMutation({
    mutationFn: ({ name, active }: { name: string; active: boolean }) =>
      api.post(`/admin/flows/${encodeURIComponent(name)}/${active ? "activate" : "deactivate"}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["flows"] }),
    onError: (e: Error) => alert(e.message),
  });

  const remove = useMutation({
    mutationFn: (name: string) => api.delete(`/admin/flows/${encodeURIComponent(name)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["flows"] }),
    onError: (e: Error) => alert(e.message),
  });

  // ── Widget config ───────────────────────────────────────────────────────────
  const cfgQ = useQuery<WidgetConfig>({
    queryKey: ["flows", "widget-config"],
    queryFn: () => api.get("/admin/flows/widget-config"),
  });
  const [cfgDraft, setCfgDraft] = useState<WidgetConfig | null>(null);
  const effectiveCfg = cfgDraft ?? cfgQ.data ?? null;
  const dirtyCfg =
    cfgDraft &&
    cfgQ.data &&
    JSON.stringify(cfgDraft) !== JSON.stringify(cfgQ.data);

  const saveCfg = useMutation({
    mutationFn: (c: WidgetConfig) => api.post("/admin/flows/widget-config", c),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["flows", "widget-config"] });
      setCfgDraft(null);
    },
    onError: (e: Error) => alert(e.message),
  });

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Flujos del widget</h1>
          <p className="text-xs text-fg-dim mt-0.5">
            Lista y activación de flows. La edición visual (Drawflow) sigue en la UI vieja.
          </p>
        </div>
        <a
          href="/admin/flows-ui"
          className="inline-flex items-center gap-1.5 text-xs text-accent hover:underline"
        >
          <Edit3 className="w-3.5 h-3.5" /> Abrir builder visual
          <ArrowRight className="w-3.5 h-3.5" />
        </a>
      </div>

      <div className="flex-1 overflow-y-auto scroll-thin p-6 space-y-6 max-w-3xl">
        {/* Lista de flows */}
        <section>
          <h2 className="text-sm font-semibold mb-2">Flows</h2>
          {flowsQ.isLoading && (
            <div className="text-xs text-fg-dim"><Loader2 className="inline w-3 h-3 animate-spin mr-1" />Cargando…</div>
          )}
          {flowsQ.error && (
            <div className="text-xs text-danger">{(flowsQ.error as Error).message}</div>
          )}
          {flowsQ.data?.length === 0 && (
            <div className="text-xs text-fg-dim bg-card border border-border rounded p-3">
              Todavía no hay flows. Creá el primero desde el builder viejo.
            </div>
          )}
          <div className="space-y-1.5">
            {flowsQ.data?.map((f) => (
              <div
                key={f.name}
                className="bg-card border border-border rounded-lg p-3 flex items-center gap-3"
              >
                <div className="flex-1">
                  <div className="text-sm font-medium flex items-center gap-2">
                    {f.name}
                    <span
                      className={cn(
                        "text-[9px] px-1.5 py-0.5 rounded",
                        f.active ? "bg-success/15 text-success" : "bg-border text-fg-dim",
                      )}
                    >
                      {f.active ? "🟢 ACTIVO" : "inactivo"}
                    </span>
                  </div>
                </div>
                {isAdmin && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggle.mutate({ name: f.name, active: !f.active })}
                      disabled={toggle.isPending}
                    >
                      {f.active ? "Desactivar" : "Activar"}
                    </Button>
                    <a
                      href={`/admin/flows-ui?flow=${encodeURIComponent(f.name)}`}
                      className="text-xs text-accent hover:underline inline-flex items-center gap-1"
                    >
                      <Edit3 className="w-3.5 h-3.5" /> Editar
                    </a>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => {
                        if (confirm(`Eliminar el flow "${f.name}"? No se puede deshacer.`)) {
                          remove.mutate(f.name);
                        }
                      }}
                      disabled={remove.isPending}
                      title="Eliminar"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-danger" />
                    </Button>
                  </>
                )}
              </div>
            ))}
          </div>
          {isAdmin && (
            <a
              href="/admin/flows-ui"
              className="mt-3 inline-flex items-center gap-1 text-xs text-accent hover:underline"
            >
              <Plus className="w-3.5 h-3.5" /> Nuevo flow (editor visual)
            </a>
          )}
        </section>

        {/* Widget config */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold">Apariencia del widget embebible</h2>
            {dirtyCfg && (
              <Button
                size="sm"
                onClick={() => effectiveCfg && saveCfg.mutate(effectiveCfg)}
                disabled={saveCfg.isPending}
              >
                {saveCfg.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                Guardar cambios
              </Button>
            )}
          </div>
          {cfgQ.isLoading && !effectiveCfg ? (
            <div className="text-xs text-fg-dim"><Loader2 className="inline w-3 h-3 animate-spin mr-1" />Cargando…</div>
          ) : effectiveCfg ? (
            <div className="bg-card border border-border rounded-lg p-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-fg-muted uppercase">Título</label>
                  <Input
                    value={effectiveCfg.title}
                    onChange={(e) => setCfgDraft({ ...effectiveCfg, title: e.target.value })}
                  />
                </div>
                <div>
                  <label className="text-[10px] text-fg-muted uppercase">Color primario</label>
                  <div className="flex gap-2">
                    <input
                      type="color"
                      value={effectiveCfg.color}
                      onChange={(e) => setCfgDraft({ ...effectiveCfg, color: e.target.value })}
                      className="h-8 w-12 bg-bg border border-border rounded cursor-pointer"
                    />
                    <Input
                      value={effectiveCfg.color}
                      onChange={(e) => setCfgDraft({ ...effectiveCfg, color: e.target.value })}
                      className="flex-1 font-mono"
                    />
                  </div>
                </div>
                <div className="col-span-2">
                  <label className="text-[10px] text-fg-muted uppercase">Saludo inicial</label>
                  <Input
                    value={effectiveCfg.greeting}
                    onChange={(e) => setCfgDraft({ ...effectiveCfg, greeting: e.target.value })}
                    placeholder="Hola! ¿En qué puedo ayudarte?"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-fg-muted uppercase">Avatar (emoji o URL)</label>
                  <Input
                    value={effectiveCfg.avatar}
                    onChange={(e) => setCfgDraft({ ...effectiveCfg, avatar: e.target.value })}
                    placeholder="🎓"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-fg-muted uppercase">Posición</label>
                  <select
                    value={effectiveCfg.position}
                    onChange={(e) =>
                      setCfgDraft({ ...effectiveCfg, position: e.target.value as "right" | "left" })
                    }
                    className="w-full h-8 px-2 bg-bg border border-border rounded text-sm"
                  >
                    <option value="right">Derecha</option>
                    <option value="left">Izquierda</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="text-[10px] text-fg-muted uppercase">
                    Quick replies (separadas por <span className="font-mono">|</span>)
                  </label>
                  <Input
                    value={effectiveCfg.quick_replies}
                    onChange={(e) => setCfgDraft({ ...effectiveCfg, quick_replies: e.target.value })}
                    placeholder="Cursos|Precios|Asesoramiento"
                  />
                </div>
              </div>

              {/* Preview */}
              <div className="pt-3 border-t border-border">
                <div className="text-[10px] text-fg-dim uppercase mb-1">Preview</div>
                <div className="bg-bg border border-border rounded-lg p-3 flex items-start gap-2">
                  <div
                    className="w-9 h-9 rounded-full flex items-center justify-center text-white text-lg shrink-0"
                    style={{ backgroundColor: effectiveCfg.color }}
                  >
                    {effectiveCfg.avatar || "💬"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold">{effectiveCfg.title || "—"}</div>
                    <div className="text-[11px] text-fg-muted mt-0.5">
                      {effectiveCfg.greeting || "—"}
                    </div>
                    {effectiveCfg.quick_replies && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {effectiveCfg.quick_replies.split("|").map((q, i) => (
                          <span
                            key={i}
                            className="text-[10px] px-2 py-0.5 rounded-full border"
                            style={{ borderColor: effectiveCfg.color, color: effectiveCfg.color }}
                          >
                            {q.trim()}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
