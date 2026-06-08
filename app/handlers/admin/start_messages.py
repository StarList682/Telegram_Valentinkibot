from contextlib import suppress

from aiogram import Bot, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter, Text
from aiogram.fsm.context import FSMContext
from aiogram.utils.deep_linking import create_start_link
from sqlalchemy.ext.asyncio import AsyncSession

import keyboards.handlers_kb as user_nav
from app.templates import texts
from app.templates.keyboards import admin as nav
from app.utils.message_templates import (
    TEMPLATE_GREETING,
    TEMPLATE_MENU,
    UnsupportedTemplateContentType,
    extract_template_payload,
    get_content_type_title,
    load_message_template,
    reset_message_template,
    save_message_template,
    send_template_message,
)

TEMPLATE_EDIT_STATE = 'template.edit'


def _template_name(template_key: str) -> str:
    return (
        'приветка'
        if template_key == TEMPLATE_GREETING
        else 'стартовое меню'
    )


def _template_info_text(
    template_key: str,
    *,
    is_custom: bool,
    content_type: str,
) -> str:
    status = 'свой шаблон' if is_custom else 'по умолчанию'
    content_type_title = get_content_type_title(content_type)

    if template_key == TEMPLATE_GREETING:
        return texts.admin.GREETING_INFO % (
            status,
            content_type_title,
        )

    return texts.admin.MENU_INFO % (
        status,
        content_type_title,
    )


async def _share_keyboard(bot: Bot, user_id: int) -> types.InlineKeyboardMarkup:
    link = await create_start_link(bot, str(user_id), encode=True)
    inline_share_text = '\nОтправь мне анонимную валентинку!💌'
    inline_link = 'https://t.me/share/url?url=%s&text=%s' % (
        link,
        inline_share_text,
    )
    return await user_nav.anon_share(inline_link)


async def _show_template_screen(
    message: types.Message,
    session: AsyncSession,
    template_key: str,
    *,
    edit: bool = False,
) -> None:
    payload, is_custom = await load_message_template(session, template_key)
    if payload is None:
        return

    text = _template_info_text(
        template_key,
        is_custom=is_custom,
        content_type=payload['content_type'],
    )
    reply_markup = nav.inline.template_actions(
        template_key,
        is_custom=is_custom,
    )

    if edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(
                text,
                reply_markup=reply_markup,
            )
            return

    await message.answer(
        text,
        reply_markup=reply_markup,
    )


async def greeting(
    message: types.Message,
    session: AsyncSession,
) -> None:
    await _show_template_screen(message, session, TEMPLATE_GREETING)


async def greeting_callback(
    call: types.CallbackQuery,
    session: AsyncSession,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()
    await _show_template_screen(
        call.message,
        session,
        TEMPLATE_GREETING,
        edit=True,
    )


async def start_menu(
    message: types.Message,
    session: AsyncSession,
) -> None:
    await _show_template_screen(message, session, TEMPLATE_MENU)


async def start_menu_callback(
    call: types.CallbackQuery,
    session: AsyncSession,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()
    await _show_template_screen(
        call.message,
        session,
        TEMPLATE_MENU,
        edit=True,
    )


async def template_action(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    _, action, template_key = call.data.split(':', 2)

    if action == 'edit':
        with suppress(TelegramBadRequest):
            await call.answer()
        await state.set_state(TEMPLATE_EDIT_STATE)
        await state.update_data(template_key=template_key)
        text = (
            texts.admin.GREETING_EDIT
            if template_key == TEMPLATE_GREETING
            else texts.admin.MENU_EDIT
        )
        return await call.message.edit_text(
            text,
            reply_markup=nav.inline.CANCEL,
        )

    if action == 'preview':
        with suppress(TelegramBadRequest):
            await call.answer()
        payload, _ = await load_message_template(session, template_key)
        if payload is None:
            return

        await call.message.answer('Предпросмотр ниже:')
        reply_markup = None
        link = None
        append_menu_link = False
        if template_key == TEMPLATE_MENU:
            link = await create_start_link(bot, str(call.from_user.id), encode=True)
            reply_markup = await _share_keyboard(bot, call.from_user.id)
            append_menu_link = True

        await send_template_message(
            bot=bot,
            chat_id=call.message.chat.id,
            payload=payload,
            user=call.from_user,
            link=link,
            reply_markup=reply_markup,
            append_menu_link=append_menu_link,
        )
        return

    if action != 'reset':
        return

    payload, is_custom = await load_message_template(session, template_key)
    if payload is None:
        return

    if not is_custom:
        return await call.answer(
            texts.admin.MESSAGE_TEMPLATE_ALREADY_DEFAULT,
            show_alert=True,
        )

    await reset_message_template(session, template_key)
    await call.answer(
        texts.admin.MESSAGE_TEMPLATE_RESET % _template_name(template_key),
        show_alert=True,
    )
    await _show_template_screen(
        call.message,
        session,
        template_key,
        edit=True,
    )


async def save_template_message_handler(
    message: types.Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    template_key = state_data.get('template_key')
    if template_key not in {TEMPLATE_GREETING, TEMPLATE_MENU}:
        await state.clear()
        return await message.answer('Не удалось определить шаблон для сохранения.')

    try:
        payload = extract_template_payload(message)
    except UnsupportedTemplateContentType:
        return await message.answer(
            texts.admin.MESSAGE_TEMPLATE_UNSUPPORTED,
            reply_markup=nav.inline.CANCEL,
        )

    await save_message_template(session, template_key, payload)
    await state.clear()
    await message.answer(
        texts.admin.MESSAGE_TEMPLATE_SAVED % _template_name(template_key),
    )
    await _show_template_screen(message, session, template_key)


async def cancel_template_edit(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer('Отменено.')

    state_data = await state.get_data()
    template_key = state_data.get('template_key')
    await state.clear()

    if template_key not in {TEMPLATE_GREETING, TEMPLATE_MENU}:
        return

    await _show_template_screen(
        call.message,
        session,
        template_key,
        edit=True,
    )


def register(router: Router) -> None:
    router.message.register(greeting, Command('greeting'))
    router.message.register(start_menu, Command('startmenu'))
    router.callback_query.register(greeting_callback, Text('admin:greeting'))
    router.callback_query.register(
        start_menu_callback,
        Text('admin:startmenu'),
    )
    router.callback_query.register(
        template_action,
        Text(startswith='template:'),
    )
    router.message.register(
        save_template_message_handler,
        StateFilter(TEMPLATE_EDIT_STATE),
    )
    router.callback_query.register(
        cancel_template_edit,
        Text('cancel'),
        StateFilter(TEMPLATE_EDIT_STATE),
    )
