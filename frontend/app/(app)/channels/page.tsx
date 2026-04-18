"use client";

import { RoleGate } from "@/lib/auth";
import { ComingSoon, NoAccess } from "@/components/ui/coming-soon";

export default function ChannelsPage() {
  return (
    <RoleGate min="admin" denyFallback={<NoAccess requiredRole="admin" />}>
      <ComingSoon
        title="Canales"
        description="Configurá la conexión con WhatsApp Meta Cloud API, Botmaker, Twilio y el widget embebible. Por ahora las credenciales se editan desde el .env del servidor."
      />
    </RoleGate>
  );
}
