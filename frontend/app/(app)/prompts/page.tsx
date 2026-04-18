"use client";

import { RoleGate } from "@/lib/auth";
import { ComingSoon, NoAccess } from "@/components/ui/coming-soon";

export default function PromptsPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <ComingSoon
        title="Editor de prompts"
        description="Editá los system prompts de cada agente del bot (ventas, cobranzas, post-venta, router). Los cambios se reflejan sin reiniciar el container. La UI nueva viene en breve."
        legacyHref="/admin/prompts-ui"
        legacyLabel="Abrir editor de prompts viejo"
      />
    </RoleGate>
  );
}
