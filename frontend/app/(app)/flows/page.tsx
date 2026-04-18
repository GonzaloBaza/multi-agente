"use client";

import { RoleGate } from "@/lib/auth";
import { ComingSoon, NoAccess } from "@/components/ui/coming-soon";

export default function FlowsPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <ComingSoon
        title="Flujos visuales"
        description="Flow builder (Drawflow) para armar secuencias multi-paso del widget. Feature con poca tracción hoy — si lo necesitás, el editor viejo sigue funcional."
        legacyHref="/admin/flows-ui"
        legacyLabel="Abrir flow builder viejo"
      />
    </RoleGate>
  );
}
