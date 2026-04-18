"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAgents } from "@/lib/api/inbox";

const PALETTES = [
  "from-pink-500 to-fuchsia-600",
  "from-blue-500 to-indigo-600",
  "from-emerald-500 to-teal-600",
  "from-amber-500 to-orange-600",
  "from-purple-500 to-pink-600",
  "from-cyan-500 to-blue-600",
];

export default function SettingsPage() {
  const qc = useQueryClient();
  const agentsQ = useAgents();
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState({ id: "", name: "", email: "", initials: "", color: PALETTES[0] });

  const create = useMutation({
    mutationFn: () => api.post("/inbox/agents", draft),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inbox", "agents"] });
      setShowForm(false);
      setDraft({ id: "", name: "", email: "", initials: "", color: PALETTES[0] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/inbox/agents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inbox", "agents"] }),
  });

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-border">
        <h1 className="text-lg font-semibold">Configuración</h1>
        <p className="text-xs text-fg-dim mt-0.5">Equipo, integraciones y preferencias</p>
      </div>

      <div className="flex-1 overflow-y-auto scroll-thin p-6 space-y-6 max-w-2xl">
        {/* Agentes */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold">Equipo (agentes humanos)</h2>
              <p className="text-[11px] text-fg-dim">Personas que pueden tomar conversaciones del inbox</p>
            </div>
            <Button size="sm" onClick={() => setShowForm(true)}>
              <Plus className="w-3.5 h-3.5" /> Nuevo agente
            </Button>
          </div>

          {showForm && (
            <div className="bg-card border border-border rounded-lg p-4 mb-3 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-fg-muted uppercase">ID (sin espacios)</label>
                  <Input value={draft.id} onChange={(e) => setDraft({ ...draft, id: e.target.value.replace(/\s/g, "-") })} placeholder="u-jrios" />
                </div>
                <div>
                  <label className="text-[10px] text-fg-muted uppercase">Nombre completo</label>
                  <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Julián Ríos" />
                </div>
                <div>
                  <label className="text-[10px] text-fg-muted uppercase">Email</label>
                  <Input type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} placeholder="jrios@msklatam.com" />
                </div>
                <div>
                  <label className="text-[10px] text-fg-muted uppercase">Iniciales</label>
                  <Input value={draft.initials} onChange={(e) => setDraft({ ...draft, initials: e.target.value.toUpperCase().slice(0, 2) })} placeholder="JR" maxLength={2} />
                </div>
              </div>
              <div>
                <label className="text-[10px] text-fg-muted uppercase mb-1.5 block">Color del avatar</label>
                <div className="flex gap-1.5">
                  {PALETTES.map((p) => (
                    <button
                      key={p}
                      onClick={() => setDraft({ ...draft, color: p })}
                      className={`w-7 h-7 rounded-full bg-gradient-to-br ${p} ${draft.color === p ? "ring-2 ring-fg" : ""}`}
                    />
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-border">
                <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>Cancelar</Button>
                <Button size="sm" onClick={() => create.mutate()} disabled={create.isPending || !draft.id || !draft.name}>
                  {create.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : "Crear"}
                </Button>
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            {agentsQ.data?.map((a) => (
              <div key={a.id} className="bg-card border border-border rounded-lg p-3 flex items-center gap-3">
                <div className={`w-9 h-9 rounded-full bg-gradient-to-br ${a.color || "from-pink-500 to-fuchsia-600"} text-white text-xs font-bold flex items-center justify-center`}>
                  {a.initials || a.name[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{a.name}</div>
                  <div className="text-[11px] text-fg-dim truncate">{(a as any).email || a.id}</div>
                </div>
                <Button
                  variant="ghost" size="icon-sm"
                  onClick={() => remove.mutate(a.id)}
                  disabled={remove.isPending}
                  title="Desactivar agente"
                >
                  <Trash2 className="w-3.5 h-3.5 text-danger" />
                </Button>
              </div>
            ))}
          </div>
        </section>

        {/* Info del workspace */}
        <section>
          <h2 className="text-sm font-semibold mb-3">Workspace</h2>
          <div className="bg-card border border-border rounded-lg p-4 text-xs space-y-2">
            <div className="flex justify-between"><span className="text-fg-dim">Backend</span><span className="font-mono">agentes.msklatam.com</span></div>
            <div className="flex justify-between"><span className="text-fg-dim">Storage</span><span className="font-mono">Cloudflare R2</span></div>
            <div className="flex justify-between"><span className="text-fg-dim">DB</span><span className="font-mono">Supabase Postgres</span></div>
            <div className="flex justify-between"><span className="text-fg-dim">LLM</span><span className="font-mono">OpenAI gpt-4o + gpt-4o-mini</span></div>
          </div>
        </section>
      </div>
    </div>
  );
}
