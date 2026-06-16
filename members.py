import importlib
import logging
from typing import Optional

from aiogram import Bot, Router
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from aiogram.types import ChatMemberUpdated, Message

import texts as texts_module
from config import Config
from database import Database, UserRecord
from services.permissions import restrict_user, unrestrict_user
from services.settings import get_or_create_settings

logger = logging.getLogger(__name__)
router = Router()


def _mention(user_id: int, first_name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{first_name}</a>'


def _topic_kwargs(topic_id: Optional[int]) -> dict:
    """Return message_thread_id kwarg only when a topic is configured."""
    if topic_id is not None:
        return {"message_thread_id": topic_id}
    return {}


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(
    event: ChatMemberUpdated,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    """Handle a new member joining the group."""
    user = event.new_chat_member.user

    # Ignore bots joining
    if user.is_bot:
        return

    settings = await get_or_create_settings(db, config, event.chat.id)

    existing = await db.get_user(event.chat.id, user.id)
    if existing and existing.access_granted:
        # Already cleared in a previous session — skip
        return

    if existing is None:
        await db.create_user(event.chat.id, user.id)

    await restrict_user(bot, event.chat.id, user.id)

    mention = _mention(user.id, user.first_name)
    # Reload texts so runtime /reloadtexts takes effect
    importlib.reload(texts_module)
    text = texts_module.WELCOME.format(
        username=mention,
        required=settings.required_members,
    )
    await bot.send_message(
        chat_id=event.chat.id,
        text=text,
        **_topic_kwargs(settings.topic_id),
    )


@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_user_leave(
    event: ChatMemberUpdated,
    db: Database,
) -> None:
    """Delete user progress when they leave the group."""
    user = event.old_chat_member.user
    if user.is_bot:
        return
    await db.delete_user(event.chat.id, user.id)
    logger.info("User %d left chat %d – progress reset.", user.id, event.chat.id)


@router.message()
async def on_new_chat_members_message(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    """
    Detect manually added members via the service message that Telegram generates.
    This event fires when `from` (the adder) is different from the added users.
    """
    if not message.new_chat_members:
        return

    adder = message.from_user
    if adder is None or adder.is_bot:
        return

    settings = await get_or_create_settings(db, config, message.chat.id)

    for new_member in message.new_chat_members:
        # Skip bots and self-joins (invite links / QR codes result in from==new_member)
        if new_member.is_bot or new_member.id == adder.id:
            continue

        adder_record = await db.get_user(message.chat.id, adder.id)

        # If the adder's access is already granted, nothing to do
        if adder_record and adder_record.access_granted:
            continue

        # If the adder is somehow not in the DB yet, create them and restrict
        if adder_record is None:
            adder_record = await db.create_user(message.chat.id, adder.id)
            await restrict_user(bot, message.chat.id, adder.id)

        new_count = await db.increment_added_members(message.chat.id, adder.id)

        if new_count >= settings.required_members:
            await db.grant_access(message.chat.id, adder.id)
            await unrestrict_user(bot, message.chat.id, adder.id)

            importlib.reload(texts_module)
            mention = _mention(adder.id, adder.first_name)
            text = texts_module.SUCCESS.format(username=mention)
            await bot.send_message(
                chat_id=message.chat.id,
                text=text,
                **_topic_kwargs(settings.topic_id),
            )
            logger.info(
                "User %d in chat %d unlocked after adding %d member(s).",
                adder.id,
                message.chat.id,
                new_count,
            )
