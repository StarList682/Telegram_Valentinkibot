from contextlib import suppress
from datetime import date, timedelta

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, Text
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.templates import texts
from app.templates.keyboards import admin as nav


def _back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[nav.inline.back_panel_row()],
    )


async def _render_stats(
    message: types.Message,
    session: AsyncSession,
    edit: bool = False,
) -> None:
    today = date.today()
    week_ago = today - timedelta(days=6)
    month_ago = today - timedelta(days=30)

    total_users = await session.scalar(
        select(func.count(User.id))
        .where(User.chat_only == False, User.id > 0)
    ) or 0
    admins_total = await session.scalar(
        select(func.count(User.id))
        .where(User.is_admin == True, User.id > 0)
    ) or 0
    named_users = await session.scalar(
        select(func.count(User.id))
        .where(
            User.chat_only == False,
            User.id > 0,
            User.first_name != None,
            User.first_name != '',
        )
    ) or 0
    joined_today = await session.scalar(
        select(func.count(User.id))
        .where(
            User.chat_only == False,
            User.id > 0,
            func.date(User.join_date) >= today,
        )
    ) or 0
    joined_week = await session.scalar(
        select(func.count(User.id))
        .where(
            User.chat_only == False,
            User.id > 0,
            func.date(User.join_date) >= week_ago,
        )
    ) or 0
    joined_month = await session.scalar(
        select(func.count(User.id))
        .where(
            User.chat_only == False,
            User.id > 0,
            func.date(User.join_date) >= month_ago,
        )
    ) or 0

    text = texts.admin.STATS.format(
        total_users=total_users,
        admins_total=admins_total,
        named_users=named_users,
        joined_today=joined_today,
        joined_week=joined_week,
        joined_month=joined_month,
    )

    if edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(
                text,
                reply_markup=_back_markup(),
            )
            return

    await message.answer(
        text,
        reply_markup=_back_markup(),
    )


async def user_stats(
    message: types.Message,
    session: AsyncSession,
) -> None:
    await _render_stats(message, session)


async def user_stats_callback(
    call: types.CallbackQuery,
    session: AsyncSession,
) -> None:
    await call.answer()
    await _render_stats(call.message, session, edit=True)


def register(router: Router) -> None:
    router.message.register(user_stats, Text("Статистика"))
    router.message.register(user_stats, Command("stats"))
    router.callback_query.register(user_stats_callback, Text('admin:stats'))
