"use client";

import { RoleGate } from "@/lib/auth";
import { ComingSoon, NoAccess } from "@/components/ui/coming-soon";

export default function TestAgentPage() {
  return (
    <RoleGate min="supervisor" denyFallback={<NoAccess requiredRole="supervisor o admin" />}>
      <ComingSoon
        title="Test Agent (sandbox)"
        description="Sandbox para probar los agentes IA sin impactar conversaciones reales. Útil para debuggear router + tools + prompts. Migración pendiente."
        legacyHref="/admin/test-agent-ui"
        legacyLabel="Abrir sandbox viejo"
      />
    </RoleGate>
  );
}
