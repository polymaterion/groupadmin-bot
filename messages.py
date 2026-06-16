import importlib
import logging
import time
from typing import Optional

from aiogram import Bot, Router
from aiogram.types import Message

import texts as texts_module
from config import Config
from database import Database
from services.permissions import restrict_user
from services.settings import get_or_create_settings

logger = logging.getLogger(__name__)
router = Router()


def _mention(user_id: int, first_name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{first_name}</a>'


def _topic_kwargs(topic_id: Optional[int]) -> dict:
    if topic_id is not None:
        return {"message_thread_id": topic_id}
    return {}


@router.message()
async def on_message(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    """
    Intercept messages from users who haven't been granted access yet.

    Cases handled:
    1. Known restricted user – delete message; warn if cooldown expired.
    2. Unknown user (was in group before bot joined) – restrict, delete, warn.
    3. Users with access_granted=True are ignored entirely.
    """
    # Only act in groups
    if message.chat.type not in ("group", "supergroup"):
        return

    user = message.from_user
    if user is None or user.is_bot:
        return

    # Service messages (new_chat_members etc.) are handled by members.py
    if message.new_chat_members or message.left_chat_member:
        return

    record = await db.get_user(message.chat.id, user.id)

    # User is fully unlocked
    if record and record.access_granted:
        return

    settings = await get_or_create_settings(db, config, message.chat.id)

    # Delete the message first (best-effort)
    try:
        await message.delete()
    except Exception as exc:
        logger.warning("Could not delete message %d: %s", message.message_id, exc)

    # New-to-bot user: create record and restrict
    if record is None:
        record = await db.create_user(message.chat.id, user.id)
        try:
            await restrict_user(bot, message.chat.id, user.id)
        except Exception as exc:
            logger.warning("Could not restrict user %d: %s", user.id, exc)

    # Spam protection: send warning at most once per cooldown window
    now = time.time()
    if (
        record.last_warning is None
        or now - record.last_warning >= config.warning_cooldown_seconds
    ):
        await db.update_last_warning(message.chat.id, user.id, now)
        importlib.reload(texts_module)
        mention = _mention(user.id, user.first_name)
        text = texts_module.BLOCKED.format(
            username=mention,
            required=settings.required_members,
            added=record.added_members,
            remaining=max(0, settings.required_members - record.added_members),
        )
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=text,
                **_topic_kwargs(settings.topic_id),
            )
        except Exception as exc:
            logger.warning("Could not send warning to chat %d: %s", message.chat.id, exc)
