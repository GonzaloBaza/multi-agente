-- 010 — Nota interna del equipo por conversación.
--
-- Una sola nota editable por conversación (no un hilo): es el "contexto actual
-- del caso" que cualquiera del equipo lee de un vistazo al abrir el chat.
-- La escribe y la pisa cualquier agente; se guarda quién y cuándo para poder
-- rastrear el cambio en el audit log.
--
-- No confundir con `conversations.context->'closing_note'`, que es la
-- disposición de cierre con categoría y alimenta los reportes.
--
-- Idempotente: se puede correr más de una vez sin romper.

alter table public.conversation_meta
    add column if not exists notes              text,
    add column if not exists notes_updated_at   timestamptz,
    add column if not exists notes_updated_by   text,
    add column if not exists notes_updated_by_name text;

-- Índice parcial: el inbox filtra/destaca por "tiene nota", y las
-- conversaciones con nota son una minoría. Un índice sobre el subconjunto
-- pesa poco y evita el seq scan.
create index if not exists idx_conversation_meta_con_notas
    on public.conversation_meta (conversation_id)
    where notes is not null and notes <> '';

comment on column public.conversation_meta.notes is
    'Nota interna del equipo humano. Visible solo en la consola, NUNCA se le envía al alumno.';
