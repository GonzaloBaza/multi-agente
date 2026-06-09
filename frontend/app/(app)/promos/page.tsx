"use client";

/**
 * /promos — admin de cupones/promociones por país × canal.
 *
 * Matriz N países × 2 canales (widget, whatsapp). Por celda, dropdown:
 *   - Sin promo           → NO_PROMO
 *   - BOT15/BOT20         → scaled_coupons (default WA)
 *   - Hot Sale (custom)   → abre modal con form (código, %, factor, fecha, nombre)
 *   - Reset al default    → borra override Redis (vuelve al config hardcoded)
 *
 * Backend: /api/v1/admin/promos/* (Redis con fallback a channel_configs.py).
 * Auth: admin-only.
 *
 * Los cambios se aplican EN VIVO — el endpoint sales lee fresh en cada request.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RotateCcw, Save, X } from "lucide-react";
import { RoleGate } from "@/lib/auth";
import { NoAccess } from "@/components/ui/coming-soon";
import { Button } from "@/components/ui/button";
import { Flag } from "@/components/ui/flag";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

// Shape de un row del GET /admin/promos
type PromoItem = {
  country: string;
  country_name: string;
  channel: "widget" | "whatsapp";
  config: PromoConfig;
  preset: "none" | "scaled_coupons" | "custom";
  source: "default" | "override";
};

type PromoConfig = {
  promo_type: "none" | "scaled_coupons" | "hot_sale_block";
  code?: string;
  pct?: number;
  factor?: number;
  until?: string;
  name?: string;
  country_name?: string;
  levels?: unknown[];
};

type PresetsResponse = {
  presets: { key: string; label: string; config: PromoConfig }[];
  countries: { iso: string; name: string }[];
  channels: string[];
};

export default function PromosPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <PromosPageInner />
    </RoleGate>
  );
}

function PromosPageInner() {
  const qc = useQueryClient();

  const { data: promosData, isLoading } = useQuery<{ items: PromoItem[]; count: number }>({
    queryKey: ["admin", "promos"],
    queryFn: () => api.get("/admin/promos"),
  });

  const { data: presetsData } = useQuery<PresetsResponse>({
    queryKey: ["admin", "promos", "presets"],
    queryFn: () => api.get("/admin/promos/presets"),
  });

  // Modal de Hot Sale custom: cuando el admin elige "custom" en una celda,
  // abrimos este modal para editar los campos. Si lo confirma, hacemos PUT.
  const [editingCell, setEditingCell] = useState<{ country: string; channel: string; current: PromoConfig } | null>(null);

  // ── Mutations ────────────────────────────────────────────────────────────

  const saveMutation = useMutation({
    mutationFn: async ({ country, channel, config }: { country: string; channel: string; config: PromoConfig }) => {
      return api.put(`/admin/promos/${country}/${channel}`, config);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "promos"] });
      setEditingCell(null);
    },
    onError: (e: any) => {
      alert(`Error guardando: ${e?.message || e}`);
    },
  });

  const resetMutation = useMutation({
    mutationFn: async ({ country, channel }: { country: string; channel: string }) => {
      return api.delete(`/admin/promos/${country}/${channel}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "promos"] });
    },
    onError: (e: any) => {
      alert(`Error reseteando: ${e?.message || e}`);
    },
  });

  // ── Handlers ─────────────────────────────────────────────────────────────

  function handlePresetChange(item: PromoItem, presetKey: string) {
    if (presetKey === "custom") {
      // Abrir modal con el config actual (o uno default si era none/scaled)
      const base: PromoConfig = item.config.promo_type === "hot_sale_block"
        ? item.config
        : { promo_type: "hot_sale_block", code: "PROMO", pct: 20, factor: 0.80, until: "", name: "Promo", country_name: item.country_name };
      setEditingCell({ country: item.country, channel: item.channel, current: base });
      return;
    }
    // Buscar el preset y guardarlo
    const preset = presetsData?.presets.find(p => p.key === presetKey);
    if (!preset) return;
    saveMutation.mutate({ country: item.country, channel: item.channel, config: preset.config });
  }

  function handleReset(item: PromoItem) {
    if (!confirm(`Resetear ${item.country} ${item.channel} al config del código?`)) return;
    resetMutation.mutate({ country: item.country, channel: item.channel });
  }

  // ── Render ───────────────────────────────────────────────────────────────

  if (isLoading || !promosData) {
    return (
      <div className="flex-1 flex items-center justify-center text-fg-dim">
        <Loader2 className="w-6 h-6 animate-spin mr-2" /> Cargando promos…
      </div>
    );
  }

  // Agrupar por país para renderizar 1 fila por país, 2 columnas (widget, whatsapp)
  const byCountry = new Map<string, { name: string; widget?: PromoItem; whatsapp?: PromoItem }>();
  for (const it of promosData.items) {
    if (!byCountry.has(it.country)) byCountry.set(it.country, { name: it.country_name });
    const e = byCountry.get(it.country)!;
    if (it.channel === "widget") e.widget = it;
    else if (it.channel === "whatsapp") e.whatsapp = it;
  }

  return (
    <div className="flex-1 overflow-y-auto scroll-thin p-6 max-w-6xl mx-auto w-full">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold mb-1">Cupones / Promos</h1>
        <p className="text-sm text-fg-dim">
          Activá o desactivá la promo de cada país × canal. Los cambios se aplican <strong>en vivo</strong> —
          la próxima conversación que arranque ya ve el nuevo cupón. Sin redeploy.
        </p>
      </div>

      <div className="bg-panel border border-border rounded-md overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-card border-b border-border">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-fg-muted w-44">País</th>
              <th className="text-left px-3 py-2 font-medium text-fg-muted">Widget web</th>
              <th className="text-left px-3 py-2 font-medium text-fg-muted">WhatsApp</th>
            </tr>
          </thead>
          <tbody>
            {Array.from(byCountry.entries()).map(([iso, row]) => (
              <tr key={iso} className="border-b border-border last:border-b-0 hover:bg-hover/30">
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <Flag iso={iso} size={16} />
                    <span className="font-medium">{row.name}</span>
                    <span className="text-fg-dim text-[10px]">{iso}</span>
                  </div>
                </td>
                <CellEditor item={row.widget} onChange={handlePresetChange} onReset={handleReset} saving={saveMutation.isPending} presets={presetsData?.presets} />
                <CellEditor item={row.whatsapp} onChange={handlePresetChange} onReset={handleReset} saving={saveMutation.isPending} presets={presetsData?.presets} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Leyenda */}
      <div className="mt-4 text-[11px] text-fg-dim space-y-1">
        <div><span className="inline-block w-2 h-2 rounded-full bg-warn mr-1.5" /> Override Redis (editado desde acá)</div>
        <div><span className="inline-block w-2 h-2 rounded-full bg-fg-dim mr-1.5" /> Default del código</div>
      </div>

      {/* Modal Hot Sale custom */}
      {editingCell && (
        <HotSaleModal
          country={editingCell.country}
          channel={editingCell.channel}
          initial={editingCell.current}
          saving={saveMutation.isPending}
          onCancel={() => setEditingCell(null)}
          onSave={(cfg) => saveMutation.mutate({ country: editingCell.country, channel: editingCell.channel, config: cfg })}
        />
      )}
    </div>
  );
}

// ─── Celda con dropdown ────────────────────────────────────────────────────

function CellEditor({
  item, onChange, onReset, saving, presets,
}: {
  item?: PromoItem;
  onChange: (item: PromoItem, presetKey: string) => void;
  onReset: (item: PromoItem) => void;
  saving: boolean;
  presets?: PresetsResponse["presets"];
}) {
  if (!item || !presets) return <td className="px-3 py-2.5 text-fg-dim text-[11px]">—</td>;

  const summary = describeConfig(item.config);
  const dotClass = item.source === "override" ? "bg-warn" : "bg-fg-dim";

  return (
    <td className="px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span className={cn("w-2 h-2 rounded-full shrink-0", dotClass)} title={item.source === "override" ? "Override Redis" : "Default del código"} />
        <select
          value={item.preset}
          onChange={(e) => onChange(item, e.target.value)}
          disabled={saving}
          className="bg-bg border border-border rounded px-2 py-1 text-[11px] focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50"
        >
          {presets.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
        </select>
        {item.source === "override" && (
          <button
            onClick={() => onReset(item)}
            disabled={saving}
            title="Resetear al config del código"
            className="text-fg-dim hover:text-fg p-1 disabled:opacity-50"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        )}
      </div>
      <div className="text-[10px] text-fg-dim mt-1 truncate" title={summary}>{summary}</div>
    </td>
  );
}

// ─── Modal Hot Sale custom ─────────────────────────────────────────────────

function HotSaleModal({
  country, channel, initial, saving, onCancel, onSave,
}: {
  country: string;
  channel: string;
  initial: PromoConfig;
  saving: boolean;
  onCancel: () => void;
  onSave: (config: PromoConfig) => void;
}) {
  const [code, setCode]       = useState(initial.code || "PROMO");
  const [pct, setPct]         = useState(initial.pct ?? 20);
  const [factor, setFactor]   = useState(initial.factor ?? 0.80);
  const [until, setUntil]     = useState(initial.until || "");
  const [name, setName]       = useState(initial.name || "Promo");
  const [countryName, setCountryName] = useState(initial.country_name || "");

  function handleSave() {
    const cfg: PromoConfig = {
      promo_type: "hot_sale_block",
      code: code.trim().toUpperCase(),
      pct: Number(pct),
      factor: Number(factor),
      until: until.trim(),
      name: name.trim(),
      country_name: countryName.trim() || undefined,
    };
    if (!cfg.code || !cfg.until || !cfg.name) {
      alert("Completá código, fecha hasta y nombre.");
      return;
    }
    onSave(cfg);
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onCancel}>
      <div className="bg-panel border border-border rounded-md p-5 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold">Hot Sale custom — {country} {channel}</h2>
          <button onClick={onCancel} className="text-fg-dim hover:text-fg">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-3 text-xs">
          <Field label="Código del cupón" hint="Ej: HOY30, BLACK, NAVIDAD">
            <input value={code} onChange={(e) => setCode(e.target.value)} className="bg-bg border border-border rounded px-2 py-1 w-full text-xs" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="% descuento" hint="Entero, ej 30">
              <input type="number" min={1} max={99} value={pct} onChange={(e) => setPct(Number(e.target.value))} className="bg-bg border border-border rounded px-2 py-1 w-full text-xs" />
            </Field>
            <Field label="Factor cuota" hint="1 - pct/100. Ej 30% → 0.70">
              <input type="number" step={0.01} min={0.01} max={1} value={factor} onChange={(e) => setFactor(Number(e.target.value))} className="bg-bg border border-border rounded px-2 py-1 w-full text-xs" />
            </Field>
          </div>
          <Field label="Hasta cuándo (texto libre)" hint="Ej: 7 de junio, 31 de diciembre 2026">
            <input value={until} onChange={(e) => setUntil(e.target.value)} className="bg-bg border border-border rounded px-2 py-1 w-full text-xs" />
          </Field>
          <Field label="Nombre de la campaña" hint="Ej: Hot Sale, CyberDay, Black Friday">
            <input value={name} onChange={(e) => setName(e.target.value)} className="bg-bg border border-border rounded px-2 py-1 w-full text-xs" />
          </Field>
          <Field label="País mostrado (opcional)" hint="Para que diga 'CyberDay en Chile' en vez de 'Argentina'">
            <input value={countryName} onChange={(e) => setCountryName(e.target.value)} className="bg-bg border border-border rounded px-2 py-1 w-full text-xs" />
          </Field>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <Button variant="ghost" onClick={onCancel} disabled={saving}>Cancelar</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Save className="w-3.5 h-3.5 mr-1" />}
            Guardar
          </Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] text-fg-muted uppercase tracking-wider mb-1">{label}</div>
      {children}
      {hint && <div className="text-[10px] text-fg-dim mt-0.5">{hint}</div>}
    </div>
  );
}

// ─── Helper: descripción humana del config ─────────────────────────────────

function describeConfig(cfg: PromoConfig): string {
  if (!cfg || cfg.promo_type === "none") return "Sin promo";
  if (cfg.promo_type === "scaled_coupons") return "BOT15/BOT20 escalado (por objeción)";
  if (cfg.promo_type === "hot_sale_block") {
    const parts: string[] = [];
    if (cfg.name) parts.push(cfg.name);
    if (cfg.code) parts.push(`${cfg.code}`);
    if (cfg.pct) parts.push(`${cfg.pct}%`);
    if (cfg.until) parts.push(`hasta ${cfg.until}`);
    return parts.join(" · ") || "Hot Sale";
  }
  return cfg.promo_type;
}
