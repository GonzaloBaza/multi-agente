"use client";

import { RoleGate } from "@/lib/auth";
import { ComingSoon, NoAccess } from "@/components/ui/coming-soon";

export default function DashboardPage() {
  return (
    <RoleGate min="supervisor" denyFallback={<NoAccess requiredRole="supervisor o admin" />}>
      <ComingSoon
        title="Dashboard"
        description="Panel consolidado: KPIs en vivo, histórico y monitor del sistema autónomo (retargeting). Por ahora, el panel viejo sigue siendo la fuente de verdad. Analytics (ya migrado) cubre los KPIs básicos."
        legacyHref="/admin/dashboard-ui"
        legacyLabel="Abrir dashboard viejo"
      />
    </RoleGate>
  );
}
