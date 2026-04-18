"use client";

import { RoleGate } from "@/lib/auth";
import { ComingSoon, NoAccess } from "@/components/ui/coming-soon";

export default function AgentsPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <ComingSoon
        title="Agentes IA"
        description="Configurá los agentes del bot (ventas, cobranzas, post-venta, closer): tools, temperatura, modelos. La UI nueva está en desarrollo — por ahora los cambios se hacen desde el código o el editor de prompts."
        legacyHref="/admin/prompts-ui"
        legacyLabel="Ir al editor de prompts viejo"
      />
    </RoleGate>
  );
}
