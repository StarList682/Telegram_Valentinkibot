import sqlite3
from datetime import datetime
from typing import Any

from aiogram import Dispatcher, Router
from aiogram.filters import Filter
from database import resolve_users_db_path


def patch_source_admin_compatibility() -> None:
    import aiogram.filters as aiogram_filters
    import pydantic
    from pydantic_settings import BaseSettings as PydanticBaseSettings

    try:
        pydantic.BaseSettings
    except Exception:
        pydantic.BaseSettings = PydanticBaseSettings

    if hasattr(aiogram_filters, "Text"):
        return

    class Text(Filter):
        def __init__(
            self,
            text: str | list[str] | tuple[str, ...] | None = None,
            *,
            startswith: str | None = None,
        ) -> None:
            self.text = text
            self.startswith = startswith

        async def __call__(self, event: Any) -> bool:
            value = getattr(event, "text", None)
            if value is None:
                value = getattr(event, "data", None)
            if value is None:
                return False

            if self.startswith is not None:
                return str(value).startswith(self.startswith)

            if isinstance(self.text, (list, tuple, set)):
                return str(value) in {str(item) for item in self.text}

            return str(value) == str(self.text)

    aiogram_filters.Text = Text


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now()

    for candidate in (value, value.replace("T", " ")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue

    return datetime.now()


async def sync_legacy_users(sessionmaker, root_admin_ids: list[int]) -> None:
    from app.database.models import User

    users_db_path = resolve_users_db_path()
    if not users_db_path.is_file():
        return

    with sqlite3.connect(users_db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}

        select_columns = ["id", "name"]
        if "joined_at" in columns:
            select_columns.append("joined_at")
        if "is_admin" in columns:
            select_columns.append("is_admin")

        cursor.execute(
            "SELECT %s FROM users" % ", ".join(select_columns)
        )
        rows = cursor.fetchall()

    async with sessionmaker() as session:
        for row in rows:
            legacy_id = int(row[0])
            legacy_name = row[1]
            legacy_joined_at = row[2] if len(row) > 2 else None
            legacy_is_admin = bool(row[3]) if len(row) > 3 else False

            user = await session.get(User, legacy_id)
            if user is None:
                user = User(
                    id=legacy_id,
                    first_name=legacy_name,
                    join_date=_parse_datetime(legacy_joined_at),
                    is_admin=(legacy_id in root_admin_ids) or legacy_is_admin,
                )
                session.add(user)
                continue

            if legacy_name:
                user.first_name = legacy_name
            user.chat_only = False
            if legacy_joined_at and getattr(user, "join_date", None) is None:
                user.join_date = _parse_datetime(legacy_joined_at)
            if legacy_id in root_admin_ids or legacy_is_admin:
                user.is_admin = True

        await session.commit()


async def setup_source_admin(dp: Dispatcher) -> Any:
    patch_source_admin_compatibility()

    from app.database import create_sessionmaker
    from app.filters import IsAdmin
    from app.handlers.admin import setup as setup_admin_handlers
    from app.middlewares.callback import CallbackMiddleware
    from app.middlewares.session import SessionMiddleware
    from app.middlewares.subscribe import SubMiddleware
    from app.middlewares.user import UserMiddleware
    from app.utils import load_config

    config = load_config()
    sessionmaker = await create_sessionmaker(config.db)
    await sync_legacy_users(sessionmaker, config.bot.admins)

    dp.update.outer_middleware(SessionMiddleware(sessionmaker))
    dp.update.outer_middleware(UserMiddleware())
    dp.message.outer_middleware(SubMiddleware())
    dp.callback_query.outer_middleware(SubMiddleware())
    dp.inline_query.outer_middleware(SubMiddleware())
    dp.callback_query.outer_middleware(CallbackMiddleware())

    admin_router = Router()
    admin_router.message.filter(IsAdmin())
    admin_router.callback_query.filter(IsAdmin())
    dp.include_router(admin_router)
    setup_admin_handlers(admin_router)

    return config, sessionmaker
