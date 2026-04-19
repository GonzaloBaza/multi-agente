/**
 * Hook oficial de Next.js 15 para init de observability al startup del
 * runtime (server o edge). Se ejecuta una sola vez por proceso.
 *
 * Sentry lee sus respectivos sentry.{server,edge,client}.config.ts al
 * levantarse. Si `NEXT_PUBLIC_SENTRY_DSN` está vacío, los inits son no-op.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

// Capturar errores server-side no atrapados por componentes (route
// handlers async, middleware). Sentry expone `captureRequestError` con la
// firma exacta que Next.js 15 espera acá — re-exportamos directo.
import * as Sentry from "@sentry/nextjs";
export const onRequestError = Sentry.captureRequestError;
