"""
Все тексты бота. Редактируйте здесь без перезапуска — используйте /reloadtexts.

Плейсхолдеры: {username} {required} {added} {remaining} {count} {topic}
"""

WELCOME = (
    "👋 Salam, {username}!\n\n"
    "Gruppada ýazmak  üçin azyndan <b>{required}</b> adam goşmaly"
    "Häzirlikçe diñe okap bilersiñiz."
)

BLOCKED = (
    "{username}, gruppada ýazmak  üçin azyndan <b>{required}</b> adam goşmaly"
)

SUCCESS = (
    "✅ {username}, siz gruppa adam goşdyñyz"
    "Indi arkaýyn ýazyşyp bilersiñiz"
)

HELP = (
    "<b>Команды администратора:</b>\n\n"
    "/help — эта справка\n"
    "/config — текущие настройки\n"
    "/setrequired &lt;число&gt; — сколько участников нужно добавить\n"
    "/settopic — привязать текущую тему (форумы)\n"
    "/settopic &lt;id&gt; — привязать по ID темы\n"
    "/settopic off — отвязать тему\n"
    "/reloadtexts — применить изменения в texts.py"
)

CONFIG = (
    "<b>Настройки чата:</b>\n"
    "Требуется участников: <b>{required}</b>\n"
    "Тема: <b>{topic}</b>"
)

SET_REQUIRED_OK  = "✅ Теперь нужно добавить <b>{count}</b> участник(а/ов)."
SET_TOPIC_OK     = "✅ Тема установлена: <b>{topic_id}</b>"
SET_TOPIC_OFF    = "✅ Привязка к теме отключена."
RELOAD_OK        = "✅ Тексты перезагружены."
NOT_ADMIN        = "⛔ Только для администраторов."
ONLY_IN_GROUP    = "⛔ Только в группах."
SETREQUIRED_USAGE = "⚠️ Использование: /setrequired &lt;число&gt;  Пример: /setrequired 3"
