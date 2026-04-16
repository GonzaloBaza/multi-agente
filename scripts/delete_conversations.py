"""Borra todas las conversaciones de un email dado (Redis + Postgres)."""
import asyncio
import sys
import os

# Para correr dentro del container
sys.path.insert(0, "/app")

import redis.asyncio as aioredis
import asyncpg


async def main():
    email = sys.argv[1] if len(sys.argv) > 1 else ""
    if not email:
        print("Uso: python delete_conversations.py <email>")
        return

    pg_url = os.environ.get("DATABASE_URL", os.environ.get("SUPABASE_DB_URL", ""))
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")

    conn = await asyncpg.connect(pg_url)
    rows = await conn.fetch(
        "SELECT id, external_id, channel FROM public.conversations WHERE user_profile->>'email' = $1",
        email,
    )
    print(f"Encontradas {len(rows)} conversaciones para {email}")

    r = aioredis.from_url(redis_url)
    for row in rows:
        sid = row["external_id"]
        cid = str(row["id"])
        ch = row["channel"]
        deleted = 0
        for key in [
            f"conv:{cid}", f"idx:{ch}:{sid}",
            f"conv_queue:{sid}", f"conv_label:{sid}",
            f"conv_assigned:{sid}", f"conv_assigned_name:{sid}",
            f"bot_disabled:{sid}", f"agent_name:{sid}",
            f"conv_enrichment:{sid}", f"conv_notes:{sid}", f"wflow:{sid}",
        ]:
            n = await r.delete(key)
            if n:
                deleted += 1
        await conn.execute("DELETE FROM public.conversation_stage WHERE conversation_id = $1", row["id"])
        await conn.execute("DELETE FROM public.messages WHERE conversation_id = $1", row["id"])
        await conn.execute("DELETE FROM public.conversations WHERE id = $1", row["id"])
        print(f"  Borrada: {sid} (redis: {deleted} keys, pg: cascade)")

    await r.aclose()
    await conn.close()
    print("Listo")


if __name__ == "__main__":
    asyncio.run(main())
