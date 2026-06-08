import csv
from contextlib import suppress
from io import StringIO

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, Text
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.templates.keyboards import admin as nav


async def dump_users(
    call: types.CallbackQuery,
    session: AsyncSession,
) -> None:
    users = (
        await session.scalars(
            select(User)
            .where(User.chat_only == False)
            .order_by(User.join_date.desc(), User.id.desc())
        )
    ).all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "username", "first_name", "last_name", "join_date", "is_admin"])

    for user in users:
        writer.writerow(
            [
                user.id,
                user.username or "",
                user.first_name or "",
                user.last_name or "",
                user.join_date.isoformat(sep=" ", timespec="seconds")
                if user.join_date else "",
                int(bool(user.is_admin)),
            ]
        )

    await call.message.answer_document(
        types.BufferedInputFile(
            buffer.getvalue().encode("utf-8"),
            "users_dump.csv",
        ),
        caption=f"Выгружено пользователей: {len(users)}",
    )
    with suppress(TelegramBadRequest):
        await call.message.delete()


async def show_dump_menu(
    message: types.Message,
    edit: bool = False,
) -> None:
    text = "Выгрузить всех пользователей бота?"
    if edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(
                text,
                reply_markup=nav.inline.DUMP,
            )
            return

    await message.answer(
        text,
        reply_markup=nav.inline.DUMP,
    )


async def pre_dump_users(message: types.Message) -> None:
    await show_dump_menu(message)


async def pre_dump_users_callback(call: types.CallbackQuery) -> None:
    await call.answer()
    await show_dump_menu(call.message, edit=True)


def register(router: Router) -> None:
    router.message.register(pre_dump_users, Command("dump"))
    router.message.register(pre_dump_users, Text("Выгрузка"))
    router.callback_query.register(pre_dump_users_callback, Text('admin:dump'))
    router.callback_query.register(dump_users, Text("dump:all"))
