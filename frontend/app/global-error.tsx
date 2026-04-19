"use client";

/**
 * Fallback último — se monta si hasta el layout root (`app/layout.tsx`)
 * tira. Rarísimo, pero Next.js lo recomienda tener para no mostrar un
 * mensaje default del framework.
 *
 * Ojo: acá NO podemos usar los estilos globales (Tailwind) porque el
 * layout root no se renderizó. Inline styles.
 */
import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";

export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="es">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#0e0e10", color: "#fafafa" }}>
        <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
          <div style={{ textAlign: "center", maxWidth: 420 }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🛑</div>
            <h1 style={{ fontSize: 20, fontWeight: 600, margin: "0 0 8px" }}>
              Error fatal
            </h1>
            <p style={{ fontSize: 14, color: "#a0a0a0", lineHeight: 1.6 }}>
              Algo se rompió tan adentro que ni la app pudo recuperarse. Ya está reportado.
              Recargá la página o volvé al inbox.
            </p>
            {error.digest && (
              <p style={{ fontSize: 10, color: "#a0a0a0", fontFamily: "monospace", marginTop: 12 }}>
                ref: {error.digest}
              </p>
            )}
            <a
              href="/inbox"
              style={{
                display: "inline-block",
                marginTop: 20,
                padding: "8px 16px",
                background: "#7c3aed",
                color: "#fff",
                borderRadius: 6,
                textDecoration: "none",
                fontSize: 13,
              }}
            >
              Recargar
            </a>
          </div>
        </div>
      </body>
    </html>
  );
}
