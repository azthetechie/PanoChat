"""MongoDB client singleton + startup index creation."""
import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def init_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        _db = _client[os.environ["DB_NAME"]]
    return _db


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        return init_db()
    return _db


async def close_db() -> None:
    global _client
    if _client:
        _client.close()


async def ensure_indexes() -> None:
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.channels.create_index("id", unique=True)
    await db.channels.create_index("name")
    await db.messages.create_index("id", unique=True)
    await db.messages.create_index([("channel_id", 1), ("created_at", -1)])
    await db.login_attempts.create_index("identifier", unique=True)
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.channel_reads.create_index([("user_id", 1), ("channel_id", 1)], unique=True)
    # Partial unique index on DM channel names (prevents race-duplicates)
    await db.channels.create_index(
        "name",
        unique=True,
        partialFilterExpression={"type": "dm"},
        name="uniq_dm_name",
    )
    # Threading: fast fetch of replies for a parent
    await db.messages.create_index([("parent_id", 1), ("created_at", 1)])
