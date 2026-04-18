"use client";

import { RoleGate } from "@/lib/auth";
import { ComingSoon, NoAccess } from "@/components/ui/coming-soon";

export default function RedisPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <ComingSoon
        title="Redis (admin)"
        description="Inspección y limpieza de claves de Redis (conversaciones activas, sesiones, locks, retargeting). Peligroso — solo admin. La UI nueva se implementa después, mientras tanto seguí usando la vieja."
        legacyHref="/admin/redis-ui"
        legacyLabel="Abrir Redis admin viejo"
      />
    </RoleGate>
  );
}
