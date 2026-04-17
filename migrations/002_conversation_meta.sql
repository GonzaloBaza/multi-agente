-- ============================================================================
-- Migration 002: conversation_meta + status / lifecycle override / queue
--
-- Agrega persistencia para acciones humanas sobre conversaciones:
-- asignar a agente, snooze, clasificar manual, marcar resuelta, tags, queue.
--
-- Aplicar:  psql $DATABASE_URL -f migrations/002_conversation_meta.sql
-- ============================================================================

-- 1) Agentes humanos del workspace
create table if not exists public.agents (
    id           text primary key,            -- e.g. "u-gbaza"
    name         text not null,
    email        text,
    initials     text,
    color        text,                        -- tailwind gradient classes
    active       boolean not null default true,
    created_at   timestamptz not null default now()
);

-- Seed agente owner si no existe (para tener al menos uno)
insert into public.agents (id, name, email, initials, color)
values ('u-gbaza', 'Gonzalo Baza', 'gonzalobaza@msklatam.com', 'G', 'from-pink-500 to-fuchsia-600')
on conflict (id) do nothing;

-- 2) Meta por conversación (1:1 con conversations)
--    Toda acción humana se persiste acá. La tabla conversations queda intacta.
create table if not exists public.conversation_meta (
    conversation_id    uuid primary key references public.conversations(id) on delete cascade,

    -- Asignación
    assigned_agent_id  text references public.agents(id),
    assigned_at        timestamptz,

    -- Estado humano
    status             text not null default 'open'
                       check (status in ('open', 'pending', 'resolved')),

    -- Snooze (cron despierta cuando snoozed_until < now())
    snoozed_until      timestamptz,
    snoozed_at         timestamptz,

    -- Override manual del lifecycle (el bot calcula uno automático aparte)
    lifecycle_override text check (lifecycle_override in ('new', 'hot', 'customer', 'cold')),
    lifecycle_overridden_at timestamptz,

    -- Cola de atención (sales/billing/post-sales/support)
    queue              text not null default 'sales'
                       check (queue in ('sales', 'billing', 'post-sales', 'support')),

    -- Bot pausado en esta conv (override del bot_disabled de Redis, ahora durable)
    bot_paused         boolean not null default false,
    bot_paused_at      timestamptz,

    -- Tags libres (texto[])
    tags               text[] not null default '{}',

    -- Necesita atención humana (escaló del bot)
    needs_human        boolean not null default false,

    -- Lifecycle calculado por el bot automáticamente (se actualiza en cada turno)
    lifecycle_auto     text check (lifecycle_auto in ('new', 'hot', 'customer', 'cold')),

    updated_at         timestamptz not null default now()
);

-- Índices para los filtros del inbox
create index if not exists idx_conv_meta_status        on public.conversation_meta (status);
create index if not exists idx_conv_meta_assigned      on public.conversation_meta (assigned_agent_id);
create index if not exists idx_conv_meta_queue         on public.conversation_meta (queue);
create index if not exists idx_conv_meta_snoozed_until on public.conversation_meta (snoozed_until)
    where snoozed_until is not null;
create index if not exists idx_conv_meta_needs_human   on public.conversation_meta (needs_human) where needs_human = true;
create index if not exists idx_conv_meta_tags          on public.conversation_meta using gin (tags);

-- Trigger para mantener updated_at
create or replace function set_conversation_meta_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists conversation_meta_updated_at on public.conversation_meta;
create trigger conversation_meta_updated_at
    before update on public.conversation_meta
    for each row
    execute function set_conversation_meta_updated_at();

-- 3) Lifecycle "efectivo" = override si existe, si no auto.
--    View para que el frontend lea sin lógica.
create or replace view public.conversation_lifecycle as
select
    cm.conversation_id,
    coalesce(cm.lifecycle_override, cm.lifecycle_auto, 'new') as lifecycle,
    cm.lifecycle_override is not null as is_manual_override
from public.conversation_meta cm;

-- 4) Función helper: get-or-create meta para una conversación
create or replace function public.ensure_conversation_meta(p_conversation_id uuid)
returns public.conversation_meta as $$
declare
    rec public.conversation_meta;
begin
    insert into public.conversation_meta (conversation_id)
    values (p_conversation_id)
    on conflict (conversation_id) do nothing;

    select * into rec from public.conversation_meta where conversation_id = p_conversation_id;
    return rec;
end;
$$ language plpgsql;

-- ============================================================================
-- Listo. Ya podés:
--   - INSERT en conversation_meta cuando una conversación nueva se crea
--   - UPDATE para asignar / snooze / clasificar / etc.
--   - Cron: SELECT * FROM conversation_meta WHERE snoozed_until < now()
--           → marcarlas como un-snoozed y notificar
-- ============================================================================
