from typing import Optional

from config import Config
from database import ChatSettings, Database


async def get_or_create_settings(
    db: Database,
    config: Config,
    chat_id: int,
) -> ChatSettings:
    """Return existing settings or create a row with defaults."""
    settings = await db.get_chat_settings(chat_id)
    if settings is None:
        await db.upsert_chat_settings(
            chat_id=chat_id,
            required_members=config.default_required_members,
            topic_id=None,
        )
        settings = ChatSettings(
            chat_id=chat_id,
            required_members=config.default_required_members,
            topic_id=None,
        )
    return settings
