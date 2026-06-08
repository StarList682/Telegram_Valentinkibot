from contextlib import suppress
from urllib.parse import urlparse

import validators

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Text, StateFilter, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.templates import texts
from app.templates.keyboards import admin as nav
from app.database.models import Sponsor
from app.utils.subscription import get_op_settings

SPONSOR_STATES = (
    'sponsor.title',
    'sponsor.link',
    'sponsor.access',
    'sponsor.limit',
    'sponsor.limit.custom',
    'sponsor.flyer.limit.custom',
)


async def get_channels(session: AsyncSession) -> list[Sponsor]:
    channels = await session.scalars(
        select(Sponsor)
    )
    return channels.all()


def _normalize_channel_access_reference(value: str) -> str | None:
    raw_value = (value or '').strip()
    if not raw_value:
        return None

    if raw_value.lstrip('-').isdigit():
        return raw_value

    if '://' in raw_value:
        parsed = urlparse(raw_value)
        if parsed.netloc not in {
            't.me',
            'www.t.me',
            'telegram.me',
            'www.telegram.me',
        }:
            return None

        path = parsed.path.strip('/')
        if not path:
            return None

        username = path.split('/')[0]
        if not username or username in {'joinchat', 'c'} or username.startswith('+'):
            return None

        raw_value = username

    username = raw_value.removeprefix('@')
    if not username:
        return None

    return f'@{username}'


async def show_sponsors(
    message: types.Message, session: AsyncSession,
    edit: bool = False,
) -> None:
    settings = await get_op_settings(session)
    sponsors = await get_channels(session)
    text = texts.admin.SPONSORS % (
        'включен' if settings.flyer_enabled else 'выключен',
        'включены' if settings.own_channels_enabled else 'выключены',
        settings.flyer_limit,
    )
    if not sponsors:
        text += '\n\n<i>Спонсоры ещё не добавлены.</i>'
    reply_markup = nav.inline.sponsors(
        sponsors,
        settings,
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


async def update_sponsors(
    message: types.Message, session: AsyncSession,
) -> None:
    await show_sponsors(message, session, edit=True)


async def channels(
    message: types.Message, session: AsyncSession,
) -> None:
    await show_sponsors(message, session)


async def channels_callback(
    call: types.CallbackQuery,
    session: AsyncSession,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()
    await show_sponsors(call.message, session, edit=True)


async def sponsor_menu(
    call: types.CallbackQuery, session: AsyncSession,
) -> None:
    action, *args = call.data.split(":", 2)[1:]

    if action in {"info", "list"}:
        return await update_sponsors(call.message, session)

    elif action == "add":
        return await call.message.edit_text(
            texts.admin.PRE_CHANNEL_ADD,
            reply_markup=nav.inline.SPONSOR_CHOICE,
        )

    sponsor = await session.scalar(
        select(Sponsor).where(
            Sponsor.id == int(args[0]),
        )
    )

    if action == "del":
        return await call.message.edit_text(
            texts.admin.SPONSOR_DEL % sponsor.title,
            reply_markup=nav.inline.choice(
                args[0], 'sponsor',
            ),
        )

    elif action == "del2":
        await call.answer(
            "Спонсор %s удален." % sponsor.title,
            show_alert=True,
        )
        await session.delete(sponsor)

    if action == "active":
        if sponsor.visits >= sponsor.limit and sponsor.limit != 0:
            sponsor.visits = 0
        sponsor.is_active = not sponsor.is_active

    await session.commit()
    await update_sponsors(call.message, session)


async def choice_sponsor(
    call: types.CallbackQuery, state: FSMContext,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()

    await call.message.edit_text(
        texts.admin.SPONSOR_TITLE,
        reply_markup=nav.inline.CANCEL,
    )
    await state.set_state('sponsor.title')
    await state.update_data(
        is_bot=(call.data.split(":")[1] == 'bot'),
        access_id='0',
        check=True,
        limit=0,
    )


async def sponsor_title(
    message: types.Message,
    state: FSMContext,
) -> None:
    title = (message.text or '').strip()
    if not title:
        return await message.answer(
            texts.admin.SPONSOR_TITLE_ERROR,
            reply_markup=nav.inline.CANCEL,
        )

    await state.update_data(title=title)
    await state.set_state('sponsor.link')
    await message.answer(
        texts.admin.SPONSOR_LINK,
        reply_markup=nav.inline.CANCEL,
    )


async def sponsor_link(
    message: types.Message,
    state: FSMContext,
) -> None:
    link = (message.text or '').strip()
    if not validators.url(link):
        return await message.answer(
            texts.admin.SPONSOR_LINK_ERROR,
            reply_markup=nav.inline.CANCEL,
        )

    data = await state.get_data()

    if data['is_bot']:
        await state.update_data(link=link, check=True)
        await state.set_state('sponsor.access')
        return await message.answer(
            texts.admin.SPONSOR_ACCESS_BOT,
            reply_markup=nav.inline.CANCEL,
        )

    access_id = _normalize_channel_access_reference(link)
    if access_id is not None:
        await state.update_data(
            link=link,
            access_id=access_id,
            check=True,
        )
        await state.set_state('sponsor.limit')
        return await message.answer(
            texts.admin.SPONSOR_LIMIT,
            reply_markup=nav.inline.SPONSOR_LIMIT,
        )

    await state.update_data(link=link, check=True)
    await state.set_state('sponsor.access')
    await message.answer(
        texts.admin.SPONSOR_ACCESS_CHANNEL,
        reply_markup=nav.inline.CANCEL,
    )

async def sponsor_access(
    message: types.Message,
    state: FSMContext,
) -> None:
    access_id = (message.text or '').strip()
    data = await state.get_data()

    if not access_id:
        return await message.answer(
            (
                texts.admin.SPONSOR_ACCESS_BOT
                if data['is_bot']
                else texts.admin.SPONSOR_ACCESS_CHANNEL_ERROR
            ),
            reply_markup=nav.inline.CANCEL,
        )

    if not data['is_bot']:
        normalized_access_id = _normalize_channel_access_reference(access_id)
        if normalized_access_id is None:
            return await message.answer(
                texts.admin.SPONSOR_ACCESS_CHANNEL_ERROR,
                reply_markup=nav.inline.CANCEL,
            )
        access_id = normalized_access_id

    await state.update_data(access_id=access_id)
    await state.set_state('sponsor.limit')
    await message.answer(
        texts.admin.SPONSOR_LIMIT,
        reply_markup=nav.inline.SPONSOR_LIMIT,
    )


async def create_sponsor(
    session: AsyncSession,
    state: FSMContext,
) -> str:
    data = await state.get_data()
    title = data['title']
    session.add(
        Sponsor(
            access_id=data['access_id'],
            title=title,
            link=data['link'],
            is_bot=data['is_bot'],
            check=True,
            limit=data['limit'],
        )
    )
    await session.commit()
    await state.clear()
    return title


async def sponsor_limit(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    raw_limit = call.data.split(':')[-1]
    if raw_limit == 'custom':
        await state.set_state('sponsor.limit.custom')
        await call.message.edit_text(
            texts.admin.SPONSOR_LIMIT_CUSTOM,
            reply_markup=nav.inline.CANCEL,
        )
        return

    await state.update_data(limit=int(raw_limit))
    await create_sponsor(session, state)
    await show_sponsors(call.message, session, edit=True)


async def sponsor_limit_custom(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    try:
        limit = int((message.text or '').strip())
        if limit < 0:
            raise ValueError
    except ValueError:
        return await message.answer(
            texts.admin.SPONSOR_LIMIT_ERROR,
            reply_markup=nav.inline.CANCEL,
        )

    await state.update_data(limit=limit)
    title = await create_sponsor(session, state)
    await message.answer(texts.admin.SPONSOR_ADDED % title)
    await show_sponsors(message, session)


async def op_config(
    call: types.CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    with suppress(TelegramBadRequest):
        await call.answer()

    settings = await get_op_settings(session)
    parts = call.data.split(':')
    action = parts[1]

    if action == 'back':
        return await update_sponsors(call.message, session)

    if action == 'flyer':
        settings.flyer_enabled = not settings.flyer_enabled
        await session.commit()
        return await update_sponsors(call.message, session)

    if action == 'own':
        settings.own_channels_enabled = not settings.own_channels_enabled
        await session.commit()
        return await update_sponsors(call.message, session)

    if action == 'limit':
        return await call.message.edit_text(
            texts.admin.FLYER_LIMIT,
            reply_markup=nav.inline.FLYER_LIMIT,
        )

    if action != 'setlimit':
        return

    raw_limit = parts[-1]
    if raw_limit == 'custom':
        await state.set_state('sponsor.flyer.limit.custom')
        return await call.message.edit_text(
            texts.admin.FLYER_LIMIT_CUSTOM,
            reply_markup=nav.inline.CANCEL,
        )

    settings.flyer_limit = max(1, int(raw_limit))
    await session.commit()
    await update_sponsors(call.message, session)


async def op_limit_custom(
    message: types.Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    try:
        limit = int((message.text or '').strip())
        if limit < 1:
            raise ValueError
    except ValueError:
        return await message.answer(
            texts.admin.FLYER_LIMIT_ERROR,
            reply_markup=nav.inline.CANCEL,
        )

    settings = await get_op_settings(session)
    settings.flyer_limit = limit
    await session.commit()
    await state.clear()
    await show_sponsors(message, session)


async def cancel(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await update_sponsors(call.message, session)
    await state.clear()


def register(router: Router) -> None:
    router.message.register(channels, Text("Спонсоры"))
    router.message.register(channels, Command("sponsors"))
    router.callback_query.register(channels_callback, Text('admin:sponsors'))
    router.callback_query.register(op_config, Text(startswith='opcfg:'))
    router.callback_query.register(sponsor_menu, Text(startswith="sponsor"))
    router.callback_query.register(
        choice_sponsor, Text(startswith="addsponsor")
    )
    router.message.register(sponsor_title, StateFilter("sponsor.title"))
    router.message.register(sponsor_link, StateFilter("sponsor.link"))
    router.message.register(sponsor_access, StateFilter("sponsor.access"))
    router.callback_query.register(
        sponsor_limit,
        Text(startswith='sadd:limit:'),
        StateFilter("sponsor.limit"),
    )
    router.message.register(
        sponsor_limit_custom,
        StateFilter("sponsor.limit.custom"),
    )
    router.message.register(
        op_limit_custom,
        StateFilter('sponsor.flyer.limit.custom'),
    )

    for state_name in SPONSOR_STATES:
        router.callback_query.register(
            cancel,
            Text('cancel'),
            StateFilter(state_name),
        )
