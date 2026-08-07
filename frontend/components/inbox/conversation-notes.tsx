"use client";

/**
 * Nota interna del equipo sobre una conversación.
 *
 * Una sola nota por conversación: se pisa, no se acumula. La idea es que sea
 * el "contexto actual del caso" — lo que cualquiera del equipo necesita saber
 * antes de responder. Por eso va arriba de todo en el panel y, cuando existe,
 * se destaca en ámbar para que no pase desapercibida.
 *
 * ⚠️ Es interna: nunca se le envía al alumno ni entra al contexto del bot.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, NotebookPen, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type NotesResponse = {
  notes: string;
  notes_updated_at: string | null;
  notes_updated_by_name: string;
};

function firmaDeEdicion(n: NotesResponse): string {
  if (!n.notes_updated_at) return "";
  const fecha = new Date(n.notes_updated_at).toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  return n.notes_updated_by_name ? `${n.notes_updated_by_name} · ${fecha}` : fecha;
}

export function ConversationNotes({ conversationId }: { conversationId: string | null }) {
  const qc = useQueryClient();
  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState("");

  const { data, isLoading } = useQuery<NotesResponse>({
    queryKey: ["conv-notes", conversationId],
    queryFn: () => api.get(`/inbox/conversations/${conversationId}/notes`),
    enabled: !!conversationId,
  });

  // Al cambiar de conversación se sale del modo edición: si no, el borrador de
  // una conversación quedaría abierto sobre otra.
  useEffect(() => {
    setEditando(false);
    setBorrador("");
  }, [conversationId]);

  const guardar = useMutation({
    mutationFn: (notes: string) =>
      api.put<NotesResponse>(`/inbox/conversations/${conversationId}/notes`, { notes }),
    onSuccess: (r) => {
      qc.setQueryData(["conv-notes", conversationId], r);
      // La lista destaca las conversaciones con nota.
      qc.invalidateQueries({ queryKey: ["conversations"] });
      setEditando(false);
    },
  });

  if (!conversationId) return null;

  const nota = data?.notes ?? "";
  const tieneNota = nota.trim().length > 0;

  // ── Edición ──────────────────────────────────────────────────────────────
  if (editando) {
    return (
      <div className="border border-warn/50 bg-warn/10 rounded-md p-3 space-y-2">
        <div className="flex items-center gap-2 text-warn">
          <NotebookPen className="w-3.5 h-3.5" />
          <span className="text-[11px] font-semibold uppercase tracking-wider">Nota interna</span>
        </div>
        <textarea
          autoFocus
          value={borrador}
          onChange={(e) => setBorrador(e.target.value)}
          rows={4}
          placeholder="Contexto del caso para el resto del equipo…"
          className="w-full bg-bg border border-border rounded p-2 text-[11px] leading-relaxed resize-y focus:outline-none focus:border-warn"
        />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => guardar.mutate(borrador)}
            disabled={guardar.isPending}
          >
            {guardar.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
            Guardar
          </Button>
          <Button size="sm" variant="outline" onClick={() => setEditando(false)}>
            Cancelar
          </Button>
        </div>
        <div className="text-[10px] text-fg-dim">
          Solo la ve el equipo. No se le envía al alumno.
        </div>
      </div>
    );
  }

  // ── Sin nota: entrada discreta ───────────────────────────────────────────
  if (!tieneNota) {
    return (
      <button
        onClick={() => {
          setBorrador("");
          setEditando(true);
        }}
        disabled={isLoading}
        className="w-full border border-dashed border-border hover:border-warn/50 hover:bg-warn/5 rounded-md px-3 py-2 flex items-center gap-2 text-fg-dim hover:text-warn transition-colors"
      >
        <NotebookPen className="w-3.5 h-3.5" />
        <span className="text-[11px]">Agregar nota interna</span>
      </button>
    );
  }

  // ── Con nota: destacada ──────────────────────────────────────────────────
  return (
    <div className="border border-warn/50 bg-warn/10 rounded-md p-3 space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-warn">
          <NotebookPen className="w-3.5 h-3.5" />
          <span className="text-[11px] font-semibold uppercase tracking-wider">Nota interna</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              setBorrador(nota);
              setEditando(true);
            }}
            title="Editar nota"
            className="text-fg-dim hover:text-warn p-1 rounded transition-colors"
          >
            <Pencil className="w-3 h-3" />
          </button>
          <button
            onClick={() => {
              if (confirm("¿Borrar la nota de esta conversación?")) guardar.mutate("");
            }}
            title="Borrar nota"
            className="text-fg-dim hover:text-danger p-1 rounded transition-colors"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
      <div className="text-[11px] leading-relaxed whitespace-pre-wrap break-words">{nota}</div>
      {data && firmaDeEdicion(data) && (
        <div className="text-[10px] text-fg-dim pt-0.5">{firmaDeEdicion(data)}</div>
      )}
    </div>
  );
}
