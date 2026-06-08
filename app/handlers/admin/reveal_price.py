from contextlib import suppress

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter, Text
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.templates import texts
from app.templates.keyboards import admin as nav
from app.utils.pricing import get_price_settings, get_reveal_sender_price


REVEAL_PRICE_STATE = 'reveal_price.value'


async def show_reveal_price(
    message: types.Message,
    session: AsyncSession,
    *,
    edit: bool = False,
) -> None:
    text = texts.admin.REVEAL_PRICE % await get_reveal_sender_price(session)

    if edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(
                text,
                reply_markup=nav.inline.REVEAL_PRICE,
            )
            return

    await message.answer(
        text,
        reply_markup=nav.inline.REVEAL_PRICE,
    )


async def reveal_price(
    message: types.Message,
    session: AsyncSession,
) -> None:
    await show_reveal_price(message, session)


async def reveal_price_callback(
    call: types.CallbackQuery,
    session: AsyncSession,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()
    await show_reveal_price(call.message, session, edit=True)


async def reveal_price_action(
    call: types.CallbackQuery,
    state: FSMContext,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()

    _, action = call.data.split(':', 1)

    if action == 'back':
        await state.clear()
        with suppress(TelegramBadRequest):
            await call.message.edit_text(
                'Админ-панель',
                reply_markup=nav.inline.MENU,
            )
        return

    if action != 'edit':
        return

    await state.set_state(REVEAL_PRICE_STATE)
    await call.message.edit_text(
        texts.admin.REVEAL_PRICE_EDIT,
        reply_markup=nav.inline.CANCEL,
    )


async def save_reveal_price(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    try:
        value = int((message.text or '').strip())
        if value < 1:
            raise ValueError
    except ValueError:
        return await message.answer(
            texts.admin.REVEAL_PRICE_ERROR,
            reply_markup=nav.inline.CANCEL,
        )

    settings = await get_price_settings(session)
    settings.reveal_sender_price = value
    await session.commit()
    await state.clear()
    await show_reveal_price(message, session)


async def cancel(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.clear()
    await show_reveal_price(call.message, session, edit=True)


def register(router: Router) -> None:
    router.message.register(reveal_price, Command('revealprice'))
    router.callback_query.register(
        reveal_price_callback,
        Text('admin:revealprice'),
    )
    router.callback_query.register(
        reveal_price_action,
        Text(startswith='revealcfg:'),
    )
    router.message.register(
        save_reveal_price,
        StateFilter(REVEAL_PRICE_STATE),
    )
    router.callback_query.register(
        cancel,
        Text('cancel'),
        StateFilter(REVEAL_PRICE_STATE),
    )
