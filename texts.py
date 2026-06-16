"""
All user-facing texts are stored here.
Edit this file to change any bot message without touching the logic.

Available placeholders:
  {username}  – @mention or first name of the user
  {required}  – number of members the user must add
  {added}     – how many members the user has added so far
  {remaining} – how many more members are needed
  {count}     – generic numeric placeholder (used in /setrequired feedback)
"""

# Sent when a brand-new user joins the group
WELCOME: str = (
    "👋 Привет, {username}!\n\n"
    "Чтобы писать в этой группе, тебе нужно вручную добавить "
    "<b>{required}</b> участник(а/ов).\n\n"
    "Пока лимит не выполнен — ты можешь читать чат, но не писать."
)

# Sent when an unknown existing user tries to post a message
BLOCKED: str = (
    "🚫 {username}, чтобы писать в этой группе, нужно вручную добавить "
    "<b>{required}</b> участник(а/ов).\n"
    "Уже добавлено: {added}/{required}."
)

# Sent when the user has added enough members and access is unlocked
SUCCESS: str = (
    "✅ {username}, ты добавил(а) нужное количество участников!\n"
    "Теперь ты можешь свободно писать в группе. Добро пожаловать! 🎉"
)

# Response to /help
HELP: str = (
    "<b>Команды администратора:</b>\n\n"
    "/help — это сообщение\n"
    "/config — текущие настройки чата\n"
    "/setrequired &lt;число&gt; — установить количество участников для разблокировки\n"
    "/settopic — назначить текущую тему для сообщений бота\n"
    "/settopic &lt;id&gt; — назначить конкретную тему\n"
    "/settopic off — отключить привязку к теме\n"
    "/reloadtexts — перезагрузить тексты из texts.py"
)

# Response to /config
CONFIG: str = (
    "<b>Настройки чата:</b>\n\n"
    "Требуется добавить участников: <b>{required}</b>\n"
    "Тема для сообщений: <b>{topic}</b>"
)

# Confirmation after /setrequired
SET_REQUIRED_OK: str = (
    "✅ Теперь для доступа нужно добавить <b>{count}</b> участник(а/ов)."
)

# Confirmation after /settopic
SET_TOPIC_OK: str = "✅ Тема для сообщений бота установлена: <b>{topic_id}</b>"
SET_TOPIC_OFF: str = "✅ Привязка к теме отключена."

# /reloadtexts
RELOAD_OK: str = "✅ Тексты успешно перезагружены."

# Error: non-admin tried to use an admin command
NOT_ADMIN: str = "⛔ Эта команда доступна только администраторам группы."

# Error: command sent in private chat
ONLY_IN_GROUP: str = "⛔ Эта команда работает только в группах."

# Error: wrong argument for /setrequired
SETREQUIRED_USAGE: str = (
    "⚠️ Использование: /setrequired &lt;число&gt;\n"
    "Пример: /setrequired 3"
)
