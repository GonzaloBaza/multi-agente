"use client";

import { RoleGate } from "@/lib/auth";
import { ComingSoon, NoAccess } from "@/components/ui/coming-soon";

export default function TemplatesPage() {
  return (
    <RoleGate min="supervisor" denyFallback={<NoAccess requiredRole="supervisor o admin" />}>
      <ComingSoon
        title="Plantillas HSM"
        description="Editor de plantillas aprobadas por Meta para abrir ventanas de 24h en WhatsApp. Mientras tanto podés seguir usando la UI vieja."
        legacyHref="/admin/templates-ui"
        legacyLabel="Abrir editor de templates HSM"
      />
    </RoleGate>
  );
}
