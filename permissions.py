from aiogram import Bot
from aiogram.types import ChatPermissions


# Full silence: cannot send any messages
_RESTRICTED = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

# Default restored permissions (mirrors the group's own defaults)
_UNRESTRICTED = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)


async def restrict_user(bot: Bot, chat_id: int, user_id: int) -> None:
    """Forbid the user from sending any content in the chat."""
    await bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        permissions=_RESTRICTED,
    )


async def unrestrict_user(bot: Bot, chat_id: int, user_id: int) -> None:
    """Restore default send permissions for the user."""
    await bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        permissions=_UNRESTRICTED,
    )
