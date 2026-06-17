import aiosqlite
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChatSettings:
    chat_id: int
    required_members: int
    topic_id: Optional[int]


@dataclass
class UserRecord:
    chat_id: int
    user_id: int
    added_members: int
    access_granted: bool
    last_warning: Optional[float]


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id          INTEGER PRIMARY KEY,
                required_members INTEGER NOT NULL DEFAULT 1,
                topic_id         INTEGER
            );
            CREATE TABLE IF NOT EXISTS users (
                chat_id        INTEGER NOT NULL,
                user_id        INTEGER NOT NULL,
                added_members  INTEGER NOT NULL DEFAULT 0,
                access_granted INTEGER NOT NULL DEFAULT 0,
                last_warning   REAL,
                PRIMARY KEY (chat_id, user_id)
            );
        """)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    # ── settings ──────────────────────────────────────────────

    async def get_settings(self, chat_id: int) -> Optional[ChatSettings]:
        async with self._conn.execute(
            "SELECT * FROM chat_settings WHERE chat_id=?", (chat_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return ChatSettings(row["chat_id"], row["required_members"], row["topic_id"])

    async def ensure_settings(self, chat_id: int, default_required: int) -> ChatSettings:
        s = await self.get_settings(chat_id)
        if s:
            return s
        await self._conn.execute(
            "INSERT OR IGNORE INTO chat_settings (chat_id, required_members) VALUES (?,?)",
            (chat_id, default_required),
        )
        await self._conn.commit()
        return ChatSettings(chat_id, default_required, None)

    async def set_required(self, chat_id: int, n: int) -> None:
        await self._conn.execute(
            "INSERT INTO chat_settings (chat_id, required_members) VALUES (?,?)"
            " ON CONFLICT(chat_id) DO UPDATE SET required_members=excluded.required_members",
            (chat_id, n),
        )
        await self._conn.commit()

    async def set_topic(self, chat_id: int, topic_id: Optional[int]) -> None:
        await self._conn.execute(
            "INSERT INTO chat_settings (chat_id, required_members, topic_id) VALUES (?,1,?)"
            " ON CONFLICT(chat_id) DO UPDATE SET topic_id=excluded.topic_id",
            (chat_id, topic_id),
        )
        await self._conn.commit()

    # ── users ─────────────────────────────────────────────────

    async def get_user(self, chat_id: int, user_id: int) -> Optional[UserRecord]:
        async with self._conn.execute(
            "SELECT * FROM users WHERE chat_id=? AND user_id=?", (chat_id, user_id)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return UserRecord(
                row["chat_id"], row["user_id"],
                row["added_members"], bool(row["access_granted"]), row["last_warning"],
            )

    async def create_user(self, chat_id: int, user_id: int) -> UserRecord:
        await self._conn.execute(
            "INSERT OR IGNORE INTO users (chat_id, user_id) VALUES (?,?)",
            (chat_id, user_id),
        )
        await self._conn.commit()
        return UserRecord(chat_id, user_id, 0, False, None)

    async def increment_added(self, chat_id: int, user_id: int) -> int:
        async with self._conn.execute(
            "UPDATE users SET added_members=added_members+1"
            " WHERE chat_id=? AND user_id=? RETURNING added_members",
            (chat_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            await self._conn.commit()
            return row["added_members"] if row else 0

    async def grant_access(self, chat_id: int, user_id: int) -> None:
        await self._conn.execute(
            "UPDATE users SET access_granted=1 WHERE chat_id=? AND user_id=?",
            (chat_id, user_id),
        )
        await self._conn.commit()

    async def set_last_warning(self, chat_id: int, user_id: int, ts: float) -> None:
        await self._conn.execute(
            "UPDATE users SET last_warning=? WHERE chat_id=? AND user_id=?",
            (ts, chat_id, user_id),
        )
        await self._conn.commit()

    async def delete_user(self, chat_id: int, user_id: int) -> None:
        await self._conn.execute(
            "DELETE FROM users WHERE chat_id=? AND user_id=?", (chat_id, user_id)
        )
        await self._conn.commit()
