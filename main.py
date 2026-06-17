import asyncio
import importlib
import logging
import os
import time
from typing import Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import ChatMemberUpdatedFilter, Command, JOIN_TRANSITION, LEAVE_TRANSITION
from aiogram.types import ChatMemberUpdated, ChatPermissions, Message

import texts
from database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

BOT_TOKEN        = os.environ["BOT_TOKEN"]
DB_PATH          = os.getenv("DB_PATH", "bot.db")
DEFAULT_REQUIRED = int(os.getenv("DEFAULT_REQUIRED_MEMBERS", "1"))
WARNING_COOLDOWN = int(os.getenv("WARNING_COOLDOWN_SECONDS", "10"))

# ── Helpers ───────────────────────────────────────────────────────────────────

def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{name}</a>'

def thread(topic_id: Optional[int]) -> dict:
    return {"message_thread_id": topic_id} if topic_id else {}

RESTRICTED = ChatPermissions(
    can_send_messages=False, can_send_audios=False, can_send_documents=False,
    can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
    can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
)
UNRESTRICTED = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True,
    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
)

async def restrict(bot: Bot, chat_id: int, user_id: int) -> None:
    try:
        await bot.restrict_chat_member(chat_id, user_id, RESTRICTED)
    except Exception as e:
        log.warning("restrict failed: %s", e)

async def unrestrict(bot: Bot, chat_id: int, user_id: int) -> None:
    try:
        await bot.restrict_chat_member(chat_id, user_id, UNRESTRICTED)
    except Exception as e:
        log.warning("unrestrict failed: %s", e)

async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False

# ── Router ────────────────────────────────────────────────────────────────────

router = Router()

# ── Admin commands (регистрируем ПЕРВЫМИ — до голых @router.message()) ────────

@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    if message.chat.type == "private":
        return await message.reply(texts.ONLY_IN_GROUP)
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        return await message.reply(texts.NOT_ADMIN)
    importlib.reload(texts)
    await message.reply(texts.HELP)


@router.message(Command("config"))
async def cmd_config(message: Message, bot: Bot, db: Database) -> None:
    if message.chat.type == "private":
        return await message.reply(texts.ONLY_IN_GROUP)
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        return await message.reply(texts.NOT_ADMIN)
    s = await db.ensure_settings(message.chat.id, DEFAULT_REQUIRED)
    importlib.reload(texts)
    await message.reply(texts.CONFIG.format(
        required=s.required_members,
        topic=str(s.topic_id) if s.topic_id else "не задана",
    ))


@router.message(Command("setrequired"))
async def cmd_setrequired(message: Message, bot: Bot, db: Database) -> None:
    if message.chat.type == "private":
        return await message.reply(texts.ONLY_IN_GROUP)
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        return await message.reply(texts.NOT_ADMIN)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit() or int(parts[1]) < 1:
        return await message.reply(texts.SETREQUIRED_USAGE)
    n = int(parts[1])
    await db.set_required(message.chat.id, n)
    importlib.reload(texts)
    await message.reply(texts.SET_REQUIRED_OK.format(count=n))


@router.message(Command("settopic"))
async def cmd_settopic(message: Message, bot: Bot, db: Database) -> None:
    if message.chat.type == "private":
        return await message.reply(texts.ONLY_IN_GROUP)
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        return await message.reply(texts.NOT_ADMIN)
    parts = message.text.split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""
    importlib.reload(texts)
    if arg.lower() == "off":
        await db.set_topic(message.chat.id, None)
        return await message.reply(texts.SET_TOPIC_OFF)
    topic_id = int(arg) if arg.isdigit() else message.message_thread_id
    await db.set_topic(message.chat.id, topic_id)
    await message.reply(texts.SET_TOPIC_OK.format(topic_id=topic_id or "текущая тема"))


@router.message(Command("reloadtexts"))
async def cmd_reloadtexts(message: Message, bot: Bot) -> None:
    if message.chat.type == "private":
        return await message.reply(texts.ONLY_IN_GROUP)
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        return await message.reply(texts.NOT_ADMIN)
    importlib.reload(texts)
    await message.reply(texts.RELOAD_OK)

# ── New member joins ──────────────────────────────────────────────────────────

@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_join(event: ChatMemberUpdated, bot: Bot, db: Database) -> None:
    user = event.new_chat_member.user
    if user.is_bot:
        return
    settings = await db.ensure_settings(event.chat.id, DEFAULT_REQUIRED)
    record = await db.get_user(event.chat.id, user.id)
    if record and record.access_granted:
        return
    if record is None:
        await db.create_user(event.chat.id, user.id)
    await restrict(bot, event.chat.id, user.id)
    importlib.reload(texts)
    await bot.send_message(
        event.chat.id,
        texts.WELCOME.format(username=mention(user.id, user.first_name),
                             required=settings.required_members),
        **thread(settings.topic_id),
    )

# ── Member leaves ─────────────────────────────────────────────────────────────

@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_leave(event: ChatMemberUpdated, db: Database) -> None:
    user = event.old_chat_member.user
    if not user.is_bot:
        await db.delete_user(event.chat.id, user.id)

# ── Единый хендлер всех сообщений ────────────────────────────────────────────

@router.message()
async def on_message(message: Message, bot: Bot, db: Database) -> None:
    # Только группы
    if message.chat.type not in ("group", "supergroup"):
        return
    if message.from_user is None or message.from_user.is_bot:
        return

    user = message.from_user

    # ── Ручное добавление участника (service message) ──
    if message.new_chat_members:
        settings = await db.ensure_settings(message.chat.id, DEFAULT_REQUIRED)
        for new_member in message.new_chat_members:
            if new_member.is_bot or new_member.id == user.id:
                continue  # self-join через ссылку — не считаем
            record = await db.get_user(message.chat.id, user.id)
            if record and record.access_granted:
                continue
            if record is None:
                record = await db.create_user(message.chat.id, user.id)
                await restrict(bot, message.chat.id, user.id)
            new_count = await db.increment_added(message.chat.id, user.id)
            log.info("User %d added member in chat %d, count=%d", user.id, message.chat.id, new_count)
            if new_count >= settings.required_members:
                await db.grant_access(message.chat.id, user.id)
                await unrestrict(bot, message.chat.id, user.id)
                importlib.reload(texts)
                await bot.send_message(
                    message.chat.id,
                    texts.SUCCESS.format(username=mention(user.id, user.first_name)),
                    **thread(settings.topic_id),
                )
        return

    # Игнорируем прочие сервисные сообщения
    if message.left_chat_member:
        return

    # ── Обычное сообщение — проверяем доступ ──
    record = await db.get_user(message.chat.id, user.id)
    if record and record.access_granted:
        return

    settings = await db.ensure_settings(message.chat.id, DEFAULT_REQUIRED)

    try:
        await message.delete()
    except Exception as e:
        log.warning("delete failed: %s", e)

    if record is None:
        record = await db.create_user(message.chat.id, user.id)
        await restrict(bot, message.chat.id, user.id)

    now = time.time()
    if record.last_warning is None or now - record.last_warning >= WARNING_COOLDOWN:
        await db.set_last_warning(message.chat.id, user.id, now)
        importlib.reload(texts)
        await bot.send_message(
            message.chat.id,
            texts.BLOCKED.format(
                username=mention(user.id, user.first_name),
                required=settings.required_members,
                added=record.added_members,
                remaining=max(0, settings.required_members - record.added_members),
            ),
            **thread(settings.topic_id),
        )

# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    db = Database(DB_PATH)
    await db.init()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp["db"] = db
    dp.include_router(router)
    log.info("Bot started")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "chat_member", "my_chat_member"],
        )
    finally:
        await db.close()
        await bot.session.close()
        log.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
