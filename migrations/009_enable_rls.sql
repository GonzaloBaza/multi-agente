-- Activa Row-Level Security en todas las tablas de `public`.
--
-- POR QUÉ: Supabase expone automáticamente el schema `public` por su API REST
-- (PostgREST, https://<project>.supabase.co/rest/v1/). Sin RLS, cualquiera con
-- la anon key puede leer/editar/borrar esas tablas sin login. El Security
-- Advisor de Supabase lo marca como crítico (`rls_disabled_in_public`).
--
-- POR QUÉ ES SEGURO ACÁ: nuestro backend NO depende de RLS para acceder —
--   1. integrations/supabase_client.py usa la SECRET_KEY (service_role), que
--      bypassa RLS siempre.
--   2. memory/postgres_store.py conecta directo por DATABASE_URL como rol
--      `postgres` (dueño de las tablas), que también bypassa RLS.
-- El frontend nunca habla con Supabase directo (todo va por FastAPI /api/*),
-- así que no hay ningún path que use la anon key. Activar RLS sin políticas
-- = bloquea anon/authenticated en PostgREST, deja pasar a nuestro backend.
-- Prueba empírica: `profiles` y `customers` ya tenían RLS activado y todo
-- funcionaba — esta migración hace lo mismo en el resto.
--
-- ⚠️ Usamos ENABLE (NO FORCE). FORCE haría que hasta el dueño `postgres`
-- quede sujeto a RLS, lo que rompería el acceso directo por asyncpg.
-- ENABLE deja al dueño y al service_role pasar; solo frena a anon/authenticated.
--
-- Idempotente: ENABLE ROW LEVEL SECURITY es no-op si ya estaba activado.

ALTER TABLE public.conversations           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_meta       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_stage      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbox_audit_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbox_read_state        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.courses                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lifecycle_stages        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.snippets                ENABLE ROW LEVEL SECURITY;

-- Las que ya estaban activadas (no-op, las dejamos explícitas para que esta
-- migración sea la fuente de verdad: "todo public tiene RLS").
ALTER TABLE public.profiles                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customers               ENABLE ROW LEVEL SECURITY;
