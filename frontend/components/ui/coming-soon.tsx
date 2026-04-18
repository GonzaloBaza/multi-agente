"use client";

import Link from "next/link";
import { ArrowRight, Lock } from "lucide-react";

/**
 * Placeholder visual consistente para páginas que todavía no migramos de
 * la UI vieja (widget/*.html). Muestra un mensaje claro, el rol requerido
 * y un link a la versión vieja que sigue funcionando mientras tanto.
 *
 * Pensado para usarse junto con <RoleGate> — si el user no tiene rol, la
 * página directamente no se renderiza. Este componente es para el caso
 * "tenés permiso pero la UI nueva todavía no está lista".
 */
export function ComingSoon({
  title,
  description,
  legacyHref,
  legacyLabel = "Abrir versión vieja",
}: {
  title: string;
  description: string;
  legacyHref?: string;
  legacyLabel?: string;
}) {
  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="max-w-md text-center space-y-4">
        <div className="text-4xl">🚧</div>
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="text-sm text-fg-dim leading-relaxed">{description}</p>
        {legacyHref && (
          <Link
            href={legacyHref}
            className="inline-flex items-center gap-1.5 text-xs text-accent hover:underline"
          >
            {legacyLabel}
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        )}
      </div>
    </div>
  );
}

/**
 * Pantalla estándar cuando el usuario entró a una ruta sin permisos (por
 * ejemplo, un agente navegó manualmente a /prompts). Se usa como
 * `denyFallback` de <RoleGate>.
 */
export function NoAccess({ requiredRole }: { requiredRole?: string }) {
  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="max-w-md text-center space-y-3">
        <Lock className="w-8 h-8 mx-auto text-fg-dim" />
        <h1 className="text-lg font-semibold">Sin permisos</h1>
        <p className="text-sm text-fg-dim">
          Esta sección requiere rol{" "}
          <span className="font-mono text-fg">{requiredRole || "admin"}</span>. Si necesitás
          acceso, hablá con un administrador del workspace.
        </p>
        <Link
          href="/inbox"
          className="inline-flex items-center gap-1.5 text-xs text-accent hover:underline"
        >
          Volver al inbox
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
