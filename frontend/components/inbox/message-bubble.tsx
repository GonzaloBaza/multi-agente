"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Code2, Mic, FileText } from "lucide-react";
import type { Message } from "@/lib/mock-data";

interface Props {
  message: Message;
  contactInitials: string;
}

/**
 * Detecta si el contenido del mensaje es un placeholder de audio/adjunto
 * generado por nuestro composer (ej: "🎤 Mensaje de voz (82KB)").
 */
function detectAttachment(content: string): { type: "audio" | "file" | null; label: string } {
  const trimmed = content.trim();
  if (trimmed.startsWith("🎤")) return { type: "audio", label: trimmed };
  if (trimmed.startsWith("📎")) return { type: "file", label: trimmed };
  return { type: null, label: "" };
}

export function MessageBubble({ message, contactInitials }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex gap-3 justify-end">
        <div className="max-w-xl">
          <div className="text-[10px] text-fg-dim mb-1 text-right">Usuario · {message.at}</div>
          <div className="bg-accent/15 border border-accent/30 rounded-lg px-4 py-2.5 text-sm space-y-2">
            {message.content && <MessageContent content={message.content} />}
            {message.attachments?.map((a, i) => (
              <AttachmentPreview key={i} attachment={a} />
            ))}
          </div>
        </div>
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-pink-500 to-fuchsia-600 text-white text-xs font-bold flex items-center justify-center shrink-0">
          {contactInitials}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-accent/20 text-accent text-xs font-bold flex items-center justify-center shrink-0">
        🤖
      </div>
      <div className="max-w-xl space-y-2">
        <div className="text-[10px] text-fg-dim">
          {message.role === "assistant" && message.agent === "humano"
            ? <>Humano · <span className="text-accent">{(message as any).sender_name || "agente"}</span> · {message.at}</>
            : <>Bot · {message.agent || "Sales Agent"} · {message.at}</>}
        </div>
        {message.toolCall && (
          <div className="bg-info/10 border border-info/30 rounded-lg px-3 py-2 text-xs flex items-center gap-2">
            <Code2 className="w-3.5 h-3.5 text-info shrink-0" />
            <span className="font-mono text-info truncate">
              {message.toolCall.name}({message.toolCall.args})
            </span>
            <span className="ml-auto text-[10px] text-success shrink-0">
              {message.toolCall.status === "ok" ? "200 OK" : "ERR"}
              {message.toolCall.duration && ` · ${message.toolCall.duration}`}
            </span>
          </div>
        )}
        <div className="bg-card rounded-lg px-4 py-2.5 text-sm space-y-2">
          {message.content && <MessageContent content={message.content} />}
          {message.attachments?.map((a, i) => (
            <AttachmentPreview key={i} attachment={a} />
          ))}
        </div>
      </div>
    </div>
  );
}

function AttachmentPreview({ attachment }: { attachment: NonNullable<Message["attachments"]>[0] }) {
  const ct = attachment.content_type || "";
  if (ct.startsWith("audio/")) {
    return (
      <audio
        controls
        src={attachment.url}
        className="w-full max-w-sm h-9 rounded"
        preload="metadata"
      />
    );
  }
  if (ct.startsWith("image/")) {
    return (
      <a href={attachment.url} target="_blank" rel="noopener noreferrer" className="block">
        <img
          src={attachment.url}
          alt={attachment.filename || "imagen"}
          className="rounded max-w-full max-h-72 border border-border"
        />
      </a>
    );
  }
  // Otros tipos: link de descarga
  return (
    <a
      href={attachment.url}
      target="_blank" rel="noopener noreferrer"
      className="inline-flex items-center gap-2 text-accent hover:underline text-xs bg-hover px-2 py-1 rounded"
    >
      <FileText className="w-3.5 h-3.5" />
      {attachment.filename || "Descargar archivo"}
      {attachment.size && (
        <span className="text-fg-dim">({(attachment.size / 1024).toFixed(0)}KB)</span>
      )}
    </a>
  );
}

function MessageContent({ content }: { content: string }) {
  // Detección de adjuntos placeholder (audio/file)
  const att = detectAttachment(content);

  if (att.type === "audio") {
    return (
      <div className="flex items-center gap-2 text-fg">
        <Mic className="w-4 h-4 text-accent" />
        <span>{att.label}</span>
      </div>
    );
  }
  if (att.type === "file") {
    return (
      <div className="flex items-center gap-2 text-fg">
        <FileText className="w-4 h-4 text-fg-muted" />
        <span>{att.label}</span>
      </div>
    );
  }

  // Markdown estándar (negritas, italicas, links, listas)
  return (
    <div className="prose prose-invert prose-sm max-w-none [&>*]:my-1 [&_a]:text-accent [&_a]:underline [&_strong]:font-semibold [&_strong]:text-fg [&_code]:bg-hover [&_code]:px-1 [&_code]:rounded [&_code]:text-[12px]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
