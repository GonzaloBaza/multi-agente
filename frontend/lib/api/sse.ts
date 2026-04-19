"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";

/**
 * Suscribe al SSE del inbox y refetcha conversaciones + mensajes cuando
 * llega un evento nuevo (sin esperar polling de 15s).
 *
 * Auth: EventSource moderno soporta `withCredentials: true` → manda la
 * cookie httpOnly del mismo origen. El backend la lee como cualquier
 * request autenticado. Antes pasábamos el token en `?token=` porque lo
 * guardábamos en localStorage y no había cookie; eso cerró al migrar.
 */
export function useInboxSSE(_currentConversationId: string | null) {
  const qc = useQueryClient();
  const { user } = useAuth();

  useEffect(() => {
    if (!user) return; // sin sesión el guard ya redirigió a /login

    const es = new EventSource("/api/v1/inbox/stream", { withCredentials: true });
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;

    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data);
        qc.invalidateQueries({ queryKey: ["inbox", "conversations"] });
        if (evt.type === "new_message" && evt.session_id) {
          qc.invalidateQueries({ queryKey: ["inbox", "messages"] });
        }
      } catch {
        /* ignore malformed SSE frames */
      }
    };

    es.onerror = () => {
      es.close();
      // Re-crea la conexión en 3s — EventSource ya reintenta solo, pero
      // esto cubre el caso donde el backend cortó la sesión.
      retryTimeout = setTimeout(() => {
        // Forzamos re-mount del hook mediante un dispatch trivial
        qc.invalidateQueries({ queryKey: ["inbox"] });
      }, 3000);
    };

    return () => {
      es.close();
      if (retryTimeout) clearTimeout(retryTimeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);
}
