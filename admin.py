import importlib
import logging
from typing import Optional

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

import texts as texts_module
from config import Config
from database import Database
from services.settings import get_or_create_settings

logger = logging.getLogger(__name__)
router = Router()


async def _is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Return True if user is a chat administrator or creator."""
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")


def _only_groups(message: Message) -> bool:
    """Return True if the message comes from a group or supergroup."""
    return message.chat.type in ("group", "supergroup")


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    if not _only_groups(message):
        await message.reply(texts_module.ONLY_IN_GROUP)
        return
    if not await _is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply(texts_module.NOT_ADMIN)
        return

    importlib.reload(texts_module)
    await message.reply(texts_module.HELP)


@router.message(Command("config"))
async def cmd_config(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not _only_groups(message):
        await message.reply(texts_module.ONLY_IN_GROUP)
        return
    if not await _is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply(texts_module.NOT_ADMIN)
        return

    settings = await get_or_create_settings(db, config, message.chat.id)
    topic_display = str(settings.topic_id) if settings.topic_id else "не задана"

    importlib.reload(texts_module)
    text = texts_module.CONFIG.format(
        required=settings.required_members,
        topic=topic_display,
    )
    await message.reply(text)


@router.message(Command("setrequired"))
async def cmd_setrequired(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not _only_groups(message):
        await message.reply(texts_module.ONLY_IN_GROUP)
        return
    if not await _is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply(texts_module.NOT_ADMIN)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit() or int(args[1].strip()) < 1:
        importlib.reload(texts_module)
        await message.reply(texts_module.SETREQUIRED_USAGE)
        return

    count = int(args[1].strip())
    await db.set_required_members(message.chat.id, count)

    importlib.reload(texts_module)
    await message.reply(texts_module.SET_REQUIRED_OK.format(count=count))
    logger.info("Chat %d: required_members set to %d.", message.chat.id, count)


@router.message(Command("settopic"))
async def cmd_settopic(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    if not _only_groups(message):
        await message.reply(texts_module.ONLY_IN_GROUP)
        return
    if not await _is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply(texts_module.NOT_ADMIN)
        return

    args = message.text.split(maxsplit=1)
    arg = args[1].strip() if len(args) > 1 else ""

    importlib.reload(texts_module)

    if arg.lower() == "off":
        await db.set_topic_id(message.chat.id, None)
        await message.reply(texts_module.SET_TOPIC_OFF)
        logger.info("Chat %d: topic_id cleared.", message.chat.id)
        return

    if arg.isdigit():
        topic_id = int(arg)
    elif message.message_thread_id:
        # Command sent inside a topic thread – use that thread's id
        topic_id = message.message_thread_id
    else:
        topic_id = None

    await db.set_topic_id(message.chat.id, topic_id)
    display = str(topic_id) if topic_id is not None else "текущая тема"
    await message.reply(texts_module.SET_TOPIC_OK.format(topic_id=display))
    logger.info("Chat %d: topic_id set to %s.", message.chat.id, topic_id)


@router.message(Command("reloadtexts"))
async def cmd_reloadtexts(message: Message, bot: Bot) -> None:
    if not _only_groups(message):
        await message.reply(texts_module.ONLY_IN_GROUP)
        return
    if not await _is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply(texts_module.NOT_ADMIN)
        return

    importlib.reload(texts_module)
    await message.reply(texts_module.RELOAD_OK)
    logger.info("texts.py reloaded by admin in chat %d.", message.chat.id)
