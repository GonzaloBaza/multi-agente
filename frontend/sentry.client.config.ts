/**
 * Config de Sentry en el browser. Se carga al bundle del cliente — no
 * pongas nada secreto acá.
 *
 * Habilita cuando `NEXT_PUBLIC_SENTRY_DSN` está en el env build time. En
 * desarrollo, dejalo vacío para no mandar ruido de errores locales.
 */
import * as Sentry from "@sentry/nextjs";

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (DSN) {
  Sentry.init({
    dsn: DSN,
    // Ambiente: producción vs preview/dev, para filtrar en el dashboard.
    environment: process.env.NEXT_PUBLIC_APP_ENV || "production",
    // Tracing muy bajo para no saturar la cuota free (10k transactions/mes).
    tracesSampleRate: 0.05,
    // Replay de sesiones: solo errores, para entender qué hizo el usuario
    // antes del crash. 10% de los session normales (para tener baseline).
    replaysOnErrorSampleRate: 1.0,
    replaysSessionSampleRate: 0.1,
    integrations: [
      Sentry.replayIntegration({
        maskAllText: false,           // no ocultar textos del DOM por default
        maskAllInputs: true,          // sí ocultar valores de inputs (PII)
        blockAllMedia: false,
      }),
    ],
    // Ignorar errores que no son nuestros (extensiones del browser, etc).
    ignoreErrors: [
      "ResizeObserver loop limit exceeded",
      "Non-Error promise rejection captured",
      /Extension context invalidated/,
    ],
    beforeSend(event, hint) {
      // No mandar errores que vienen de scripts de terceros (ads, analytics
      // embebidos). Solo capturamos stack trace de nuestro código.
      const frame = event.exception?.values?.[0]?.stacktrace?.frames?.[0];
      if (frame?.filename?.includes("chrome-extension://")) return null;
      return event;
    },
  });
}
