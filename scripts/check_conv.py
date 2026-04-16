import asyncio, json, os, sys

async def check():
    import asyncpg
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL",""))
    sid = sys.argv[1] if len(sys.argv) > 1 else ""
    if not sid:
        print("Uso: check_conv.py <session_id>")
        return
    row = await conn.fetchrow(
        "SELECT id, external_id, channel, user_profile FROM conversations WHERE external_id = $1",
        sid,
    )
    if not row:
        row = await conn.fetchrow(
            "SELECT id, external_id, channel, user_profile FROM conversations WHERE id::text = $1",
            sid,
        )
    if row:
        print(f"id: {row['id']}")
        print(f"external_id: {row['external_id']}")
        print(f"channel: {row['channel']}")
        up = json.loads(row["user_profile"]) if row["user_profile"] else {}
        print(f"user_profile: {json.dumps(up, indent=2, default=str)}")
    else:
        print("NOT FOUND")
    await conn.close()

asyncio.run(check())
