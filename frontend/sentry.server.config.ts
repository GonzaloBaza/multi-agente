/**
 * Config de Sentry en el servidor Next.js (SSR + route handlers).
 * DSN via env — NEXT_PUBLIC_* porque se comparte con el cliente.
 */
import * as Sentry from "@sentry/nextjs";

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (DSN) {
  Sentry.init({
    dsn: DSN,
    environment: process.env.NEXT_PUBLIC_APP_ENV || "production",
    tracesSampleRate: 0.05,
  });
}
