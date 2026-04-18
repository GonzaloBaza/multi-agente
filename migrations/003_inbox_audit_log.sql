-- Audit log de acciones humanas en el inbox
create table if not exists public.inbox_audit_log (
    id              uuid primary key default gen_random_uuid(),
    actor_id        text not null,
    action          text not null,
    conversation_id uuid,
    detail          jsonb,
    created_at      timestamptz not null default now()
);

create index if not exists idx_inbox_audit_actor on public.inbox_audit_log (actor_id);
create index if not exists idx_inbox_audit_conv on public.inbox_audit_log (conversation_id);
create index if not exists idx_inbox_audit_created on public.inbox_audit_log (created_at desc);
