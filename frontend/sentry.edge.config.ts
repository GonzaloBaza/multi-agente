/**
 * Config de Sentry en el edge runtime de Next.js (middleware + edge routes).
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
