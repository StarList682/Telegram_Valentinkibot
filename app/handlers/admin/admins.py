from contextlib import suppress

from aiogram import Bot, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter, Text
from aiogram.fsm.context import FSMContext
from sqlalchemy import or_
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.templates import texts
from app.templates.keyboards import admin as nav
from app.utils.config import Settings
from app.utils.set_commands import set_commands
from app.utils.text import escape


ADMIN_STATES = (
    'admins.grant',
)


def _can_manage_admins(user_id: int, config: Settings) -> bool:
    return user_id in config.bot.admins


def _render_user_link(user: User | None, user_id: int) -> str:
    full_name = ' '.join(
        part for part in (
            getattr(user, 'first_name', None),
            getattr(user, 'last_name', None),
        ) if part
    ).strip()

    label = full_name or (
        '@%s' % user.username
        if getattr(user, 'username', None)
        else 'ID %i' % user_id
    )
    rendered = '<a href="tg://user?id=%i">%s</a>' % (
        user_id,
        escape(label),
    )

    if getattr(user, 'username', None) and not label.startswith('@'):
        rendered += ' (@%s)' % escape(user.username)

    return '%s <code>%i</code>' % (rendered, user_id)


async def _load_admin_users(
    session: AsyncSession,
    config: Settings,
) -> tuple[list[tuple[int, User | None]], list[tuple[int, User | None]]]:
    root_ids = {int(admin_id) for admin_id in config.bot.admins}

    query = select(User)
    if root_ids:
        query = query.where(
            or_(
                User.is_admin == True,
                User.id.in_(root_ids),
            ),
        )
    else:
        query = query.where(User.is_admin == True)

    users = await session.scalars(query)
    user_map = {
        int(user.id): user
        for user in users.all()
    }

    root_admins = [
        (user_id, user_map.get(user_id))
        for user_id in sorted(root_ids)
    ]
    delegated_admins = [
        (user_id, user)
        for user_id, user in sorted(user_map.items())
        if user_id not in root_ids and user.is_admin
    ]

    return root_admins, delegated_admins


async def _render_admins(
    message: types.Message,
    session: AsyncSession,
    config: Settings,
    edit: bool = False,
) -> None:
    root_admins, delegated_admins = await _load_admin_users(session, config)
    root_text = '\n'.join(
        '👑 %s' % _render_user_link(user, user_id)
        for user_id, user in root_admins
    ) or '—'
    delegated_text = '\n'.join(
        '🛡 %s' % _render_user_link(user, user_id)
        for user_id, user in delegated_admins
    ) or '—'
    keyboard = nav.inline.admins(
        [user_id for user_id, _ in delegated_admins],
        can_manage=_can_manage_admins(message.chat.id, config),
    )
    text = texts.admin.ADMINS % (
        root_text,
        delegated_text,
    )

    if edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(
                text,
                reply_markup=keyboard,
            )
            return

    await message.answer(
        text,
        reply_markup=keyboard,
    )


async def admins(
    message: types.Message,
    session: AsyncSession,
    config: Settings,
) -> None:
    await _render_admins(message, session, config)


async def admins_callback(
    call: types.CallbackQuery,
    session: AsyncSession,
    config: Settings,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()
    await _render_admins(call.message, session, config, edit=True)


async def admins_action(
    call: types.CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    config: Settings,
    bot: Bot,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()

    action, *rest = call.data.split(':')[1:]
    can_manage = _can_manage_admins(call.from_user.id, config)

    if action == 'back':
        await state.clear()
        with suppress(TelegramBadRequest):
            await call.message.edit_text(
                'Админ-панель',
                reply_markup=nav.inline.MENU,
            )
        return

    if action == 'list':
        await state.clear()
        await _render_admins(call.message, session, config, edit=True)
        return

    if not can_manage:
        return await call.answer(texts.admin.ADMIN_NO_RIGHTS, True)

    if action == 'grant':
        await state.set_state('admins.grant')
        return await call.message.edit_text(
            texts.admin.ADMIN_GRANT,
            reply_markup=nav.inline.CANCEL,
        )

    if action != 'revoke' or not rest:
        return

    try:
        user_id = int(rest[0])
    except ValueError:
        return

    if user_id in config.bot.admins:
        return await call.answer(texts.admin.ADMIN_REVOKE_ROOT, True)

    user = await session.scalar(
        select(User)
        .where(User.id == user_id)
    )
    if not user or not user.is_admin:
        return await call.answer(texts.admin.ADMIN_NOT_FOUND, True)

    user.is_admin = False
    await session.commit()
    await set_commands(bot, config, session=session)
    await call.answer(texts.admin.ADMIN_REVOKED % user_id, True)
    await _render_admins(call.message, session, config, edit=True)


async def grant_admin(
    message: types.Message,
    session: AsyncSession,
    state: FSMContext,
    config: Settings,
    bot: Bot,
) -> None:
    if not _can_manage_admins(message.from_user.id, config):
        await state.clear()
        return await message.answer(texts.admin.ADMIN_NO_RIGHTS)

    try:
        user_id = int((message.text or '').strip())
    except ValueError:
        return await message.answer(
            texts.admin.ADMIN_GRANT_ERROR,
            reply_markup=nav.inline.CANCEL,
        )

    user = await session.scalar(
        select(User)
        .where(User.id == user_id)
    )
    if not user:
        return await message.answer(
            texts.admin.ADMIN_NOT_FOUND,
            reply_markup=nav.inline.CANCEL,
        )

    if user_id in config.bot.admins or user.is_admin:
        await state.clear()
        return await message.answer(texts.admin.ADMIN_ALREADY_GRANTED)

    user.is_admin = True
    await session.commit()
    await set_commands(bot, config, session=session)
    await state.clear()
    await message.answer(texts.admin.ADMIN_GRANTED % user_id)
    await _render_admins(message, session, config)


async def cancel(
    call: types.CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    config: Settings,
) -> None:
    await state.clear()
    await _render_admins(call.message, session, config, edit=True)


def register(router: Router) -> None:
    router.message.register(admins, Command('admins'))
    router.callback_query.register(admins_callback, Text('admin:admins'))
    router.callback_query.register(admins_action, Text(startswith='admins:'))
    router.message.register(grant_admin, StateFilter('admins.grant'))

    for state_name in ADMIN_STATES:
        router.callback_query.register(
            cancel,
            Text('cancel'),
            StateFilter(state_name),
        )
