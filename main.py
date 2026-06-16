import asyncio
import html
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatPermissions, Message, User

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"
TEXTS_PATH = BASE_DIR / "texts.json"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("join_gate_bot")

router = Router()

DEFAULT_TEXTS = {
    "welcome_new": (
        "Привет, {user_mention}!\n\n"
        "Чтобы писать в этом чате, нужно вручную добавить {required} участника(ов).\n"
        "Сейчас у тебя: {current}/{required}."
    ),
    "blocked": (
        "⛔ {user_mention}, сначала добавь {remaining} участника(ов), чтобы получить доступ.\n"
        "Сейчас у тебя: {current}/{required}."
    ),
    "success": (
        "✅ {user_mention}, доступ открыт. Спасибо. Ты выполнил условие."
    ),
    "left_reset": (
        "Пользователь {user_mention} вышел из чата. Доступ сброшен."
    ),
    "admin_set_required": (
        "✅ Теперь нужно добавить {required} участника(ов)."
    ),
    "admin_set_topic": (
        "✅ Топик для сообщений бота установлен."
    ),
    "admin_clear_topic": (
        "✅ Привязка к топику снята."
    ),
    "admin_reload_texts": (
        "✅ Тексты перезагружены."
    ),
    "admin_show_config": (
        "Настройки чата:\n"
        "• нужно добавить: {required}\n"
        "• топик сообщений: {topic}\n"
    ),
    "help_admin": (
        "Команды:\n"
        "/setrequired N — сколько участников нужно добавить\n"
        "/settopic — привязать сообщения бота к текущему топику\n"
        "/settopic off — убрать привязку к топику\n"
        "/settopic 123 — указать thread id вручную\n"
        "/settext KEY ТЕКСТ — изменить текст\n"
        "/gettexts — список доступных текстов\n"
        "/reloadtexts — перечитать texts.json\n"
        "/config — показать текущие настройки"
    ),
    "not_authorized": "Эта команда доступна только администраторам чата.",
    "invalid_required": "Введите число больше 0.",
    "invalid_text_key": "Неизвестный ключ текста.",
    "text_updated": "✅ Текст обновлён.",
    "texts_saved": "✅ Тексты сохранены.",
    "no_topic_here": "Этот топик не найден. Откройте нужный топик и повторите команду /settopic без аргументов.",
}

DEFAULT_CHAT_SETTINGS = {
    "required_invites": 1,
    "notice_thread_id": None,
}

JOINED_STATUSES = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
LEFT_STATUSES = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}

def load_texts() -> dict[str, str]:
    if not TEXTS_PATH.exists():
        TEXTS_PATH.write_text(json.dumps(DEFAULT_TEXTS, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(DEFAULT_TEXTS)
    try:
        data = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("texts.json must contain a JSON object")
        merged = dict(DEFAULT_TEXTS)
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str):
                merged[k] = v
        return merged
    except Exception:
        log.exception("Failed to load texts.json, falling back to defaults")
        return dict(DEFAULT_TEXTS)

TEXTS = load_texts()

def save_texts() -> None:
    TEXTS_PATH.write_text(json.dumps(TEXTS, ensure_ascii=False, indent=2), encoding="utf-8")

def mention_user(user: User) -> str:
    full_name = html.escape(" ".join(part for part in [user.first_name, user.last_name] if part).strip() or "user")
    if user.username:
        return f"@{html.escape(user.username)}"
    return f'<a href="tg://user?id={user.id}">{full_name}</a>'

def render(template_key: str, **kwargs: Any) -> str:
    template = TEXTS.get(template_key, DEFAULT_TEXTS.get(template_key, template_key))
    return template.format(**kwargs)

def is_group_like(chat_type: str) -> bool:
    return chat_type in {ChatType.GROUP, ChatType.SUPERGROUP}

def independent_permissions(value: bool) -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=value,
        can_send_audios=value,
        can_send_documents=value,
        can_send_photos=value,
        can_send_videos=value,
        can_send_video_notes=value,
        can_send_voice_notes=value,
        can_send_polls=value,
        can_send_other_messages=value,
        can_add_web_page_previews=value,
        can_change_info=value,
        can_invite_users=value,
        can_pin_messages=value,
        can_manage_topics=value,
    )

MUTED_PERMISSIONS = independent_permissions(False)
FULL_PERMISSIONS = independent_permissions(True)

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                required_invites INTEGER NOT NULL DEFAULT 1,
                notice_thread_id INTEGER
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_progress (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                added_count INTEGER NOT NULL DEFAULT 0,
                access_granted INTEGER NOT NULL DEFAULT 0,
                last_warning_ts INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
            """
        )
        await db.commit()

async def ensure_chat_settings(chat_id: int) -> dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO chat_settings(chat_id, required_invites, notice_thread_id) VALUES (?, ?, ?)",
                (chat_id, DEFAULT_CHAT_SETTINGS["required_invites"], DEFAULT_CHAT_SETTINGS["notice_thread_id"]),
            )
            await db.commit()
            return dict(DEFAULT_CHAT_SETTINGS)
        return {"required_invites": row["required_invites"], "notice_thread_id": row["notice_thread_id"]}

async def set_required_invites(chat_id: int, count: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO chat_settings(chat_id, required_invites, notice_thread_id)
            VALUES (?, ?, COALESCE((SELECT notice_thread_id FROM chat_settings WHERE chat_id = ?), NULL))
            ON CONFLICT(chat_id) DO UPDATE SET required_invites = excluded.required_invites
            """,
            (chat_id, count, chat_id),
        )
        await db.commit()

async def set_notice_thread(chat_id: int, thread_id: Optional[int]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO chat_settings(chat_id, required_invites, notice_thread_id)
            VALUES (?, COALESCE((SELECT required_invites FROM chat_settings WHERE chat_id = ?), 1), ?)
            ON CONFLICT(chat_id) DO UPDATE SET notice_thread_id = excluded.notice_thread_id
            """,
            (chat_id, chat_id, thread_id),
        )
        await db.commit()

async def get_chat_settings(chat_id: int) -> dict[str, Any]:
    return await ensure_chat_settings(chat_id)

async def get_progress(chat_id: int, user_id: int) -> dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM user_progress WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO user_progress(chat_id, user_id, added_count, access_granted, last_warning_ts) VALUES (?, ?, 0, 0, 0)",
                (chat_id, user_id),
            )
            await db.commit()
            return {"added_count": 0, "access_granted": 0, "last_warning_ts": 0}
        return dict(row)

async def upsert_progress(chat_id: int, user_id: int, added_count: int, access_granted: int, last_warning_ts: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_progress(chat_id, user_id, added_count, access_granted, last_warning_ts)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                added_count = excluded.added_count,
                access_granted = excluded.access_granted,
                last_warning_ts = excluded.last_warning_ts
            """,
            (chat_id, user_id, added_count, access_granted, last_warning_ts),
        )
        await db.commit()

async def delete_progress(chat_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_progress WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()

async def is_authorized(bot: Bot, chat_id: int, user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    except Exception:
        return False

def thread_id_for_outgoing(message: Message, settings: dict[str, Any]) -> Optional[int]:
    if settings.get("notice_thread_id") is not None:
        return int(settings["notice_thread_id"])
    return message.message_thread_id

async def send_text(bot: Bot, chat_id: int, text: str, thread_id: Optional[int] = None) -> None:
    kwargs = {"chat_id": chat_id, "text": text, "parse_mode": ParseMode.HTML}
    if thread_id is not None:
        kwargs["message_thread_id"] = thread_id
    await bot.send_message(**kwargs)

async def mute_user(bot: Bot, chat_id: int, user_id: int) -> None:
    try:
        await bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=MUTED_PERMISSIONS)
    except TelegramBadRequest:
        pass

async def unmute_user(bot: Bot, chat_id: int, user_id: int) -> None:
    try:
        await bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=FULL_PERMISSIONS)
    except TelegramBadRequest:
        pass

async def reset_user(bot: Bot, chat_id: int, user: User) -> None:
    await delete_progress(chat_id, user.id)
    try:
        await mute_user(bot, chat_id, user.id)
    except Exception:
        pass

async def maybe_grant_access(bot: Bot, chat_id: int, user: User, settings: dict[str, Any]) -> None:
    progress = await get_progress(chat_id, user.id)
    required = max(1, int(settings["required_invites"]))
    if progress["access_granted"]:
        return
    if progress["added_count"] >= required:
        await upsert_progress(chat_id, user.id, progress["added_count"], 1, progress["last_warning_ts"])
        await unmute_user(bot, chat_id, user.id)
        text = render("success", user_mention=mention_user(user), required=required, current=progress["added_count"], remaining=0)
        await send_text(bot, chat_id, text, thread_id=settings.get("notice_thread_id"))
    else:
        await mute_user(bot, chat_id, user.id)

async def warn_user(bot: Bot, chat_id: int, user: User, current: int, required: int, settings: dict[str, Any], message_thread_id: Optional[int]) -> None:
    progress = await get_progress(chat_id, user.id)
    now = int(asyncio.get_running_loop().time())
    if now - int(progress["last_warning_ts"]) < 8:
        return
    remaining = max(0, required - current)
    await upsert_progress(chat_id, user.id, current, 0, now)
    text = render(
        "blocked",
        user_mention=mention_user(user),
        required=required,
        current=current,
        remaining=remaining,
    )
    thread_id = settings.get("notice_thread_id") if settings.get("notice_thread_id") is not None else message_thread_id
    await send_text(bot, chat_id, text, thread_id=thread_id)

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "Бот для групп. Добавь меня в чат как администратора и выдай право ограничивать участников."
        )

@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    if not is_group_like(message.chat.type):
        return
    if not message.from_user:
        return
    if not await is_authorized(bot, message.chat.id, message.from_user.id):
        return
    await message.answer(render("help_admin"), parse_mode=ParseMode.HTML)

@router.message(Command("config"))
async def cmd_config(message: Message, bot: Bot) -> None:
    if not is_group_like(message.chat.type):
        return
    if not message.from_user or not await is_authorized(bot, message.chat.id, message.from_user.id):
        await message.reply(render("not_authorized"), parse_mode=ParseMode.HTML)
        return
    settings = await get_chat_settings(message.chat.id)
    topic_text = str(settings["notice_thread_id"]) if settings["notice_thread_id"] is not None else "не задан"
    await message.reply(render("admin_show_config", required=settings["required_invites"], topic=topic_text), parse_mode=ParseMode.HTML)

@router.message(Command("setrequired"))
async def cmd_set_required(message: Message, bot: Bot, command: CommandObject) -> None:
    if not is_group_like(message.chat.type):
        return
    if not message.from_user or not await is_authorized(bot, message.chat.id, message.from_user.id):
        await message.reply(render("not_authorized"), parse_mode=ParseMode.HTML)
        return
    if not command.args:
        await message.reply(render("invalid_required"), parse_mode=ParseMode.HTML)
        return
    try:
        count = int(command.args.strip())
        if count < 1:
            raise ValueError
    except ValueError:
        await message.reply(render("invalid_required"), parse_mode=ParseMode.HTML)
        return
    await set_required_invites(message.chat.id, count)
    await message.reply(render("admin_set_required", required=count), parse_mode=ParseMode.HTML)

@router.message(Command("settopic"))
async def cmd_set_topic(message: Message, bot: Bot, command: CommandObject) -> None:
    if not is_group_like(message.chat.type):
        return
    if not message.from_user or not await is_authorized(bot, message.chat.id, message.from_user.id):
        await message.reply(render("not_authorized"), parse_mode=ParseMode.HTML)
        return
    arg = (command.args or "").strip().lower()
    if not arg:
        if message.message_thread_id is None:
            await message.reply(render("no_topic_here"), parse_mode=ParseMode.HTML)
            return
        await set_notice_thread(message.chat.id, message.message_thread_id)
        await message.reply(render("admin_set_topic"), parse_mode=ParseMode.HTML)
        return
    if arg in {"off", "none", "clear", "remove"}:
        await set_notice_thread(message.chat.id, None)
        await message.reply(render("admin_clear_topic"), parse_mode=ParseMode.HTML)
        return
    try:
        thread_id = int(arg)
    except ValueError:
        await message.reply("Укажи /settopic без аргументов, /settopic off или число thread id.", parse_mode=ParseMode.HTML)
        return
    await set_notice_thread(message.chat.id, thread_id)
    await message.reply(render("admin_set_topic"), parse_mode=ParseMode.HTML)

@router.message(Command("gettexts"))
async def cmd_get_texts(message: Message, bot: Bot) -> None:
    if not is_group_like(message.chat.type):
        return
    if not message.from_user or not await is_authorized(bot, message.chat.id, message.from_user.id):
        await message.reply(render("not_authorized"), parse_mode=ParseMode.HTML)
        return
    keys = "\n".join(sorted(TEXTS.keys()))
    await message.reply(f"Доступные ключи:\n<code>{html.escape(keys)}</code>", parse_mode=ParseMode.HTML)

@router.message(Command("reloadtexts"))
async def cmd_reload_texts(message: Message, bot: Bot) -> None:
    global TEXTS
    if not is_group_like(message.chat.type):
        return
    if not message.from_user or not await is_authorized(bot, message.chat.id, message.from_user.id):
        await message.reply(render("not_authorized"), parse_mode=ParseMode.HTML)
        return
    TEXTS = load_texts()
    await message.reply(render("admin_reload_texts"), parse_mode=ParseMode.HTML)

@router.message(Command("settext"))
async def cmd_set_text(message: Message, bot: Bot, command: CommandObject) -> None:
    global TEXTS
    if not is_group_like(message.chat.type):
        return
    if not message.from_user or not await is_authorized(bot, message.chat.id, message.from_user.id):
        await message.reply(render("not_authorized"), parse_mode=ParseMode.HTML)
        return
    args = (command.args or "").strip()
    if not args:
        await message.reply("Использование: /settext KEY новый текст", parse_mode=ParseMode.HTML)
        return
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Использование: /settext KEY новый текст", parse_mode=ParseMode.HTML)
        return
    key, value = parts[0], parts[1]
    if key not in TEXTS:
        await message.reply(render("invalid_text_key"), parse_mode=ParseMode.HTML)
        return
    TEXTS[key] = value
    save_texts()
    await message.reply(render("text_updated"), parse_mode=ParseMode.HTML)

@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot) -> None:
    if not is_group_like(message.chat.type):
        return
    if not message.from_user:
        return
    settings = await get_chat_settings(message.chat.id)
    inviter = message.from_user

    for new_user in message.new_chat_members or []:
        if new_user.is_bot:
            continue
        await upsert_progress(message.chat.id, new_user.id, 0, 0, 0)
        await mute_user(bot, message.chat.id, new_user.id)
        welcome = render(
            "welcome_new",
            user_mention=mention_user(new_user),
            required=settings["required_invites"],
            current=0,
            remaining=settings["required_invites"],
        )
        await send_text(bot, message.chat.id, welcome, thread_id=thread_id_for_outgoing(message, settings))

        # Manual add only: ignore self-joins.
        if inviter.id == new_user.id:
            continue

        progress = await get_progress(message.chat.id, inviter.id)
        new_count = int(progress["added_count"]) + 1
        await upsert_progress(message.chat.id, inviter.id, new_count, int(progress["access_granted"]), int(progress["last_warning_ts"]))
        await maybe_grant_access(bot, message.chat.id, inviter, settings)

@router.message(F.left_chat_member)
async def on_left_chat_member(message: Message, bot: Bot) -> None:
    if not is_group_like(message.chat.type):
        return
    left_user = message.left_chat_member
    if left_user is None or left_user.is_bot:
        return
    await reset_user(bot, message.chat.id, left_user)

@router.message(F.text)
async def on_any_text(message: Message, bot: Bot) -> None:
    if not is_group_like(message.chat.type):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    if await is_authorized(bot, message.chat.id, message.from_user.id):
        return

    settings = await get_chat_settings(message.chat.id)
    progress = await get_progress(message.chat.id, message.from_user.id)
    if int(progress["access_granted"]) == 1:
        return

    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    except TelegramForbiddenError:
        pass

    await mute_user(bot, message.chat.id, message.from_user.id)
    current = int(progress["added_count"])
    required = max(1, int(settings["required_invites"]))
    await warn_user(
        bot,
        message.chat.id,
        message.from_user,
        current=current,
        required=required,
        settings=settings,
        message_thread_id=message.message_thread_id,
    )

async def on_startup() -> None:
    await init_db()
    log.info("Database initialized")

async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    bot = Bot(token=token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(router)

    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
