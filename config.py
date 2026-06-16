import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    db_path: str
    default_required_members: int
    warning_cooldown_seconds: int

    @classmethod
    def load(cls) -> "Config":
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError("BOT_TOKEN environment variable is not set")

        return cls(
            bot_token=token,
            db_path=os.getenv("DB_PATH", "bot.db"),
            default_required_members=int(os.getenv("DEFAULT_REQUIRED_MEMBERS", "1")),
            warning_cooldown_seconds=int(os.getenv("WARNING_COOLDOWN_SECONDS", "10")),
        )
