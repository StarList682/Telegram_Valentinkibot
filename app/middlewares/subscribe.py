from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware, exceptions, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Chat, Update

from app.database.models import User
from app.templates.keyboards import user as nav
from app.utils.config import Settings
from app.utils.subscription import (
    SubscriptionService,
    render_subscription_text,
)


class SubMiddleware(BaseMiddleware):
    @staticmethod
    async def _show_subscription_screen(
        event: Update,
        user: User,
        data: Dict[str, Any],
    ) -> None:
        sponsors = data.get('sponsors', [])
        session = data['session']

        if isinstance(event, types.CallbackQuery):
            if getattr(event, 'data', None) == 'checksub':
                return

            await event.answer(
                'Чтобы пользоваться ботом, подпишитесь на все каналы.',
                True,
            )

            if event.message:
                updated = False
                with suppress(exceptions.TelegramAPIError):
                    await event.message.edit_text(
                        render_subscription_text(sponsors),
                        reply_markup=nav.inline.subscription(sponsors),
                    )
                    updated = True

                if not updated:
                    with suppress(exceptions.TelegramAPIError):
                        await event.message.answer(
                            render_subscription_text(sponsors),
                            reply_markup=nav.inline.subscription(sponsors),
                        )

        elif isinstance(event, types.Message):
            await event.answer(
                render_subscription_text(sponsors),
                reply_markup=nav.inline.subscription(sponsors),
            )

        if user.subbed:
            user.subbed = False
            await session.commit()

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        user: Optional[User] = data.get('user')
        config: Settings = data['config']
        state: FSMContext = data['state']
        chat: Optional[Chat] = data.get('event_chat')
        subscription_service: SubscriptionService = data['subscription_service']

        data['sponsors'] = []
        data['required_sponsors'] = []

        if (
            not chat
            or not user
            or getattr(user, 'id', 0) in config.bot.admins
            or user.is_admin
        ):
            return await handler(event, data)

        if (
            chat.type != 'private'
        ):
            return await handler(event, data)

        if await subscription_service.has_active_op_access(
            data['session'],
            user.id,
        ):
            data['sponsors'] = []
            data['required_sponsors'] = []
            await state.update_data(
                op_sponsor_ids=[],
                op_flyer_signatures=[],
            )
            return await handler(event, data)

        sponsors, required_sponsors, sponsor_ids, flyer_signatures = (
            await subscription_service.resolve_items(
                session=data['session'],
                user=user,
                bot=data['bot'],
            )
        )
        data['sponsors'] = sponsors
        data['required_sponsors'] = required_sponsors
        await state.update_data(
            op_sponsor_ids=sponsor_ids,
            op_flyer_signatures=flyer_signatures,
        )

        if required_sponsors:
            if isinstance(event, types.Message):
                raw_text = (getattr(event, 'text', None) or '').strip()
                if raw_text.startswith('/start'):
                    parts = raw_text.split(maxsplit=1)
                    await state.update_data(
                        pending_start_args=parts[1] if len(parts) > 1 else None,
                        pending_callback_data=None,
                    )
            elif (
                isinstance(event, types.CallbackQuery)
                and getattr(event, 'data', None) != 'checksub'
            ):
                await state.update_data(
                    pending_callback_data=getattr(event, 'data', None),
                )
            await self._show_subscription_screen(event, user, data)
            if not (
                isinstance(event, types.CallbackQuery)
                and getattr(event, 'data', None) == 'checksub'
            ):
                return None

        return await handler(event, data)
