from contextlib import suppress

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, Text

from app.templates.keyboards import admin as nav


async def show_panel(
    message: types.Message,
    edit: bool = False,
) -> None:
    if edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(
                'Админ-панель',
                reply_markup=nav.inline.MENU,
            )
            return

    await message.answer('Админ-панель', reply_markup=nav.inline.MENU)


async def start(message: types.Message) -> None:
    await show_panel(message)


async def start_callback(call: types.CallbackQuery) -> None:
    await call.answer()
    await show_panel(call.message, edit=True)


def register(router: Router) -> None:
    router.message.register(start, Command('panel'))
    router.message.register(start, Text('Админ-панель ⚙️'))
    router.callback_query.register(start_callback, Text('admin:panel'))
