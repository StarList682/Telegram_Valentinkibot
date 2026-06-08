import asyncio

from typing import Optional
from contextlib import suppress

from aiogram import Bot, exceptions
from aiogram.types import BotCommandScopeChat

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.utils.config import Settings
from app.database.models import User
from app.templates.keyboards.admin.commands import ADMIN_COMMANDS
from app.templates.keyboards.user.commands import USER_COMMANDS


async def set_commands(
    bot: Bot,
    config: Settings,
    sessionmaker: Optional[async_sessionmaker] = None,
    session: Optional[AsyncSession] = None,
) -> None:
    await bot.set_my_commands(USER_COMMANDS)

    if sessionmaker:
        session = sessionmaker()

    admin_ids = await session.scalars(
        select(User.id)
        .where(User.is_admin == True)
    )

    if sessionmaker:
        await asyncio.shield(session.close())

    admin_commands = USER_COMMANDS + ADMIN_COMMANDS

    for chat_id in admin_ids.all():
        with suppress(exceptions.TelegramBadRequest):
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=chat_id),
            )

    for chat_id in config.bot.admins:
        with suppress(exceptions.TelegramBadRequest):
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=chat_id),
            )
