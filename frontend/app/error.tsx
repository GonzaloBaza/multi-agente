"use client";

/**
 * Error boundary a nivel `app/`. Next.js lo monta si cualquier route
 * dentro del App Router tira durante render o data fetching.
 *
 * Mostrar algo honesto y accionable — nunca pantalla blanca. También
 * reportar a Sentry para que lleguen los errores "no atrapados" del
 * browser que pasan por aquí.
 */
import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="h-screen flex items-center justify-center bg-bg text-fg p-6">
      <div className="max-w-md text-center space-y-4">
        <div className="text-4xl">💥</div>
        <h1 className="text-lg font-semibold">Algo se rompió</h1>
        <p className="text-sm text-fg-dim">
          La pantalla que intentabas abrir tiró un error inesperado. Ya se reportó al equipo
          técnico y vamos a revisarlo.
        </p>
        {error.digest && (
          <p className="text-[10px] text-fg-dim font-mono">
            ref: {error.digest}
          </p>
        )}
        <div className="flex gap-2 justify-center">
          <button
            onClick={() => reset()}
            className="px-3 py-1.5 rounded bg-accent text-white text-xs font-medium hover:bg-accent-2"
          >
            Reintentar
          </button>
          <a
            href="/inbox"
            className="px-3 py-1.5 rounded border border-border text-xs text-fg-muted hover:bg-hover"
          >
            Volver al inbox
          </a>
        </div>
      </div>
    </div>
  );
}
