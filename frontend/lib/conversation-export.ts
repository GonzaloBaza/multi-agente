/**
 * Exportar una conversación a un .txt legible.
 *
 * Todo client-side: los mensajes ya están cargados en el browser (props del
 * ConversationDetail), así que no hace falta endpoint nuevo en el backend.
 *
 * `buildTranscript` es una función pura (fácil de testear); `downloadTranscript`
 * la envuelve y dispara la descarga vía un <a download> temporal.
 */

import type { ContactDetail, ConversationListItem, Message } from "@/lib/mock-data";

/** Etiqueta humana del autor de cada mensaje según su role. */
function roleLabel(m: Message): string {
  switch (m.role) {
    case "user":
      return "Cliente";
    case "bot":
    case "assistant":
      return "Bot IA";
    case "human":
      return m.agent ? `Agente (${m.agent})` : "Agente";
    case "system":
      return "Sistema";
    default:
      return m.role;
  }
}

function channelLabel(channel: string): string {
  return channel === "whatsapp" ? "WhatsApp" : "Web Widget";
}

/** "Conversación con Juan Pérez" → "conversacion-juan-perez-2026-06-09.txt" */
export function transcriptFilename(contact: ContactDetail, now: Date = new Date()): string {
  const slug = (contact.name || "contacto")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // saca acentos
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "contacto";
  const ymd = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate(),
  ).padStart(2, "0")}`;
  return `conversacion-${slug}-${ymd}.txt`;
}

export function buildTranscript(opts: {
  contact: ContactDetail;
  conversation: ConversationListItem;
  messages: Message[];
  assignedAgentName?: string | null;
  now?: Date;
}): string {
  const { contact, conversation, messages, assignedAgentName, now = new Date() } = opts;

  const exported = now.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  // ── Encabezado ───────────────────────────────────────────────────────
  const headerLines = [
    `Conversación — ${contact.name}`,
    `Teléfono: ${contact.phone || "—"} · Canal: ${channelLabel(contact.channel)} · País: ${
      contact.countryName || contact.country || "—"
    }`,
  ];
  if (assignedAgentName) {
    headerLines.push(`Asignada a: ${assignedAgentName} · Exportado: ${exported}`);
  } else {
    headerLines.push(`Exportado: ${exported}`);
  }
  const sep = "─".repeat(60);

  // ── Mensajes ─────────────────────────────────────────────────────────
  const body =
    messages.length === 0
      ? "(Sin mensajes en esta conversación)"
      : messages
          .map((m) => {
            const time = m.at ? `[${m.at}] ` : "";
            let line = `${time}${roleLabel(m)}: ${m.content ?? ""}`.trimEnd();
            for (const att of m.attachments ?? []) {
              const name = att.filename ? `${att.filename} — ` : "";
              line += `\n        ↳ Adjunto: ${name}${att.url}`;
            }
            return line;
          })
          .join("\n");

  return `${headerLines.join("\n")}\n${sep}\n${body}\n`;
}

/** Arma el .txt y dispara la descarga en el browser. */
export function downloadTranscript(opts: {
  contact: ContactDetail;
  conversation: ConversationListItem;
  messages: Message[];
  assignedAgentName?: string | null;
}): void {
  const text = buildTranscript(opts);
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = transcriptFilename(opts.contact);
  document.body.appendChild(a);
  a.click();
  a.remove();
  // liberar el object URL en el próximo tick (Safari necesita que el click ya haya pasado)
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
