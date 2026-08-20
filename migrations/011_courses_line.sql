-- 011: línea(s) de producto en el catálogo de cursos
--
-- El CMS propio (catalog_course_detail) expone `line` (línea principal) y
-- `lines` (todas las líneas; los cursos duales vienen p.ej.
-- ["medicina","enfermeria"]). Hasta ahora el sync las descartaba.
-- Vocabulario actual: medicina / enfermeria / mindcare / master.
--
-- Ambas columnas son sync-managed: las escribe upsert_course en cada corrida
-- (a diferencia de pitch_hook / pitch_by_profile, que el sync no toca).
-- ensure_schema() incluye estos mismos alter de forma idempotente, así que
-- esta migración solo es necesaria si se quiere aplicar sin reiniciar la app.
--
-- Backfill: correr un sync de cursos después de desplegar
--   POST /api/v1/admin/courses/sync

alter table public.courses add column if not exists line text;
alter table public.courses add column if not exists lines jsonb not null default '[]'::jsonb;
create index if not exists courses_line_idx on public.courses (country, line);
