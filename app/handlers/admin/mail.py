import asyncio
from datetime import datetime

from aiogram import Router, Bot, types
from aiogram.filters import Text, Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters import ContentTypes
from app.utils.mailing import MailerSingleton
from app.utils.mailing_buttons import (
    build_mailing_reply_markup,
    parse_mailing_buttons,
)
from app.database.models import User
from app.templates import texts
from app.templates.keyboards import admin as nav
from app.utils.message_templates import (
    UnsupportedTemplateContentType,
    extract_template_payload,
    send_template_message,
)


async def _show_mailing_preview(
    message: types.Message,
    bot: Bot,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    reply_markup = await build_mailing_reply_markup(
        bot,
        data['template_payload'],
        data.get('button_specs'),
    )
    await state.update_data(
        reply_markup=(
            reply_markup.dict()
            if reply_markup else None
        ),
    )

    await bot.send_message(message.chat.id, texts.admin.MAILING_PREVIEW)
    await send_template_message(
        bot=bot,
        chat_id=message.chat.id,
        payload=data['template_payload'],
        user=message.from_user,
        reply_markup=reply_markup,
    )
    await bot.send_message(
        message.chat.id,
        texts.admin.MAILING_CONFIRM,
        reply_markup=nav.reply.CONFIRM,
    )
    await state.set_state("mailing.confirm")


async def pre_mailing(message: types.Message, state: FSMContext) -> None:
    await message.answer(
        texts.admin.MAILING_PRE,
        reply_markup=nav.inline.CANCEL,
    )
    await state.set_state("mailing.text")


async def pre_mailing_callback(
    call: types.CallbackQuery,
    state: FSMContext,
) -> None:
    await call.answer()
    await pre_mailing(call.message, state)


async def mailing_text(message: types.Message, state: FSMContext) -> None:
    try:
        template_payload = extract_template_payload(message)
    except UnsupportedTemplateContentType:
        supported_types = ', '.join(
            (
                'текст',
                'фото',
                'видео',
                'GIF',
                'документ',
                'аудио',
                'голосовое',
                'стикер',
                'видеокружок',
            ),
        )
        return await message.answer(
            'Этот тип сообщения не поддерживается для рассылки.\n'
            'Поддерживаются: %s.' % supported_types,
            reply_markup=nav.inline.CANCEL,
        )

    await state.update_data(
        template_payload=template_payload,
        button_specs=None,
        reply_markup=None,
    )

    await message.answer(
        texts.admin.MAILING_BUTTONS,
        reply_markup=nav.reply.MAILING_BUTTONS,
    )
    await state.set_state("mailing.buttons")


async def mailing_buttons(
    message: types.Message,
    bot: Bot,
    state: FSMContext,
) -> None:
    try:
        button_specs = parse_mailing_buttons(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        await message.answer(
            texts.admin.MAILING_BUTTONS,
            reply_markup=nav.reply.MAILING_BUTTONS,
        )
        return

    await state.update_data(button_specs=button_specs)
    await _show_mailing_preview(message, bot, state)


async def skip_mailing_buttons(
    message: types.Message,
    bot: Bot,
    state: FSMContext,
) -> None:
    await _show_mailing_preview(message, bot, state)


async def skip_mailing_buttons_callback(
    call: types.CallbackQuery,
    bot: Bot,
    state: FSMContext,
) -> None:
    await call.answer()
    await _show_mailing_preview(call.message, bot, state)


async def invalid_mailing_buttons(message: types.Message) -> None:
    await message.answer(
        'На этом шаге нужен только текст с описанием кнопок.',
        reply_markup=nav.reply.MAILING_BUTTONS,
    )


async def _run_mailing(
    message: types.Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    scope = (await session.scalars(
        select(User)
        .where(User.block_date == None)
        .where(User.chat_only == False)
        .where(User.vip_time < datetime.now())
    )).all()

    if not scope:
        await state.clear()
        return await message.answer(
            'Для рассылки нет пользователей.',
            reply_markup=nav.inline.MENU,
        )

    await message.answer(
        'Начинаю рассылку...', reply_markup=nav.inline.MENU,
    )

    mailer = MailerSingleton.get_instance()
    asyncio.create_task(mailer.start_mailing(
        data['template_payload'],
        data['reply_markup'],
        message.chat.id, bot, scope,
        cancel_keyboard=nav.inline.STOPMAIL,
    ))
    await state.clear()


async def mailing_confirm(
    message: types.Message,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if message.text == 'Подтвердить':
        await _run_mailing(message, bot, state, session)
        return

    await message.answer("Рассылка отменена.", reply_markup=nav.inline.MENU)
    await state.clear()


async def mailing_confirm_callback(
    call: types.CallbackQuery,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await call.answer()
    await _run_mailing(call.message, bot, state, session)


async def stop_mailing(call: types.CallbackQuery) -> None:
    MailerSingleton.get_instance().stop_mailing()

    await call.message.delete()
    await call.answer("Рассылка остановлена.")


async def cancel_mailing(
    call: types.CallbackQuery, state: FSMContext,
) -> None:
    await state.clear()

    await call.message.delete()
    await call.answer("Отменено.")
    await call.message.answer(
        "Рассылка отменена.",
        reply_markup=nav.inline.MENU,
    )


async def cancel_mailing_message(
    message: types.Message,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer("Рассылка отменена.", reply_markup=nav.inline.MENU)


def register(router: Router) -> None:
    router.message.register(pre_mailing, Command("mailing"))
    router.message.register(pre_mailing, Text("Рассылка"))
    router.callback_query.register(pre_mailing_callback, Text("admin:mailing"))
    router.message.register(
        cancel_mailing_message, Text("Отмена"), StateFilter("mailing.text"),
    )
    router.message.register(
        mailing_text, StateFilter("mailing.text"),
        ContentTypes(types.ContentType.ANY),
    )
    router.callback_query.register(
        cancel_mailing, Text("cancel"), StateFilter("mailing.text"),
    )
    router.callback_query.register(
        skip_mailing_buttons_callback,
        Text("mailing:skip_buttons"),
        StateFilter("mailing.buttons"),
    )
    router.message.register(
        skip_mailing_buttons,
        Text("Без кнопок"),
        StateFilter("mailing.buttons"),
    )
    router.message.register(
        cancel_mailing_message, Text("Отмена"), StateFilter("mailing.buttons"),
    )
    router.message.register(
        mailing_buttons,
        StateFilter("mailing.buttons"),
        ContentTypes(types.ContentType.TEXT),
    )
    router.message.register(
        invalid_mailing_buttons,
        StateFilter("mailing.buttons"),
        ContentTypes(types.ContentType.ANY),
    )
    router.callback_query.register(
        cancel_mailing, Text("cancel"), StateFilter("mailing.buttons"),
    )
    router.message.register(mailing_confirm, StateFilter("mailing.confirm"))
    router.callback_query.register(
        mailing_confirm_callback,
        Text("mailing:confirm"),
        StateFilter("mailing.confirm"),
    )
    router.callback_query.register(
        cancel_mailing, Text("cancel"), StateFilter("mailing.confirm"),
    )
    router.callback_query.register(stop_mailing, Text("stopmail"))
