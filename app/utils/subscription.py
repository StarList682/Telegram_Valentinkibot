import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
)
from aiogram.utils.token import TokenValidationError
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.templates import texts
from app.database.models import (
    FlyerCompletion,
    OpAccess,
    OpSetting,
    Sponsor,
    SponsorCompletion,
    User,
)
from app.utils.text import escape


logger = logging.getLogger('subscription')
OP_ACCESS_DURATION = timedelta(hours=2)


@dataclass(slots=True)
class SubscriptionItem:
    title: str
    link: str
    source: str
    required: bool
    sponsor_id: Optional[int] = None
    signature: Optional[str] = None


async def get_op_settings(session: AsyncSession) -> OpSetting:
    settings = await session.get(OpSetting, 1)
    if settings is None:
        settings = OpSetting(id=1)
        session.add(settings)
        await session.commit()
    return settings


class SubscriptionService:
    def __init__(
        self,
        flyer_key: str = '',
        flyer_base_url: str = 'https://api.flyerservice.io',
        shared_user_id: Optional[int] = None,
    ) -> None:
        self.flyer_key = flyer_key.strip()
        self.flyer_base_url = flyer_base_url.rstrip('/')
        self.shared_user_id = shared_user_id
        self._session: Optional[aiohttp.ClientSession] = None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def resolve_items(
        self,
        session: AsyncSession,
        user: User,
        bot: Bot,
    ) -> tuple[list[SubscriptionItem], list[SubscriptionItem], list[int], list[str]]:
        settings = await get_op_settings(session)
        visible_items: list[SubscriptionItem] = []
        required_items: list[SubscriptionItem] = []
        visible_keys: set[tuple[str, str]] = set()
        required_keys: set[tuple[str, str]] = set()
        shown_sponsor_ids: list[int] = []
        shown_flyer_signatures: list[str] = []

        if settings.own_channels_enabled:
            sponsors = await session.scalars(
                select(Sponsor).where(Sponsor.is_active == True)
            )
            required_internal = await self._resolve_sponsors(
                sponsors.all(), user, bot
            )
            self._extend_unique_items(
                visible_items,
                required_internal,
                visible_keys,
            )
            self._extend_unique_items(
                required_items,
                required_internal,
                required_keys,
            )
            shown_sponsor_ids.extend(
                [
                    item.sponsor_id for item in required_internal
                    if item.sponsor_id is not None
                ]
            )

        flyer_items: list[SubscriptionItem] = []
        if settings.flyer_enabled and self.flyer_key and settings.flyer_limit > 0:
            flyer_items = await self._resolve_flyer_items(
                session=session,
                user_id=user.id,
                limit=settings.flyer_limit,
            )
            self._extend_unique_items(
                visible_items,
                flyer_items,
                visible_keys,
            )
            self._extend_unique_items(
                required_items,
                flyer_items,
                required_keys,
            )
            shown_flyer_signatures.extend(
                [
                    item.signature for item in flyer_items
                    if item.signature
                ]
            )

        return (
            visible_items,
            required_items,
            shown_sponsor_ids,
            shown_flyer_signatures,
        )

    async def has_active_op_access(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> bool:
        access = await session.get(OpAccess, user_id)
        return bool(access and access.expires_at > datetime.now())

    async def grant_op_access(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> datetime:
        now = datetime.now()
        expires_at = now + OP_ACCESS_DURATION
        access = await session.get(OpAccess, user_id)

        if access is None:
            session.add(
                OpAccess(
                    user_id=user_id,
                    granted_at=now,
                    expires_at=expires_at,
                )
            )
            return expires_at

        access.granted_at = now
        access.expires_at = expires_at
        return expires_at

    async def complete_sponsors(
        self,
        session: AsyncSession,
        user_id: int,
        sponsor_ids: list[int],
    ) -> list[int]:
        unique_ids = [
            sponsor_id
            for sponsor_id in dict.fromkeys(sponsor_ids)
            if sponsor_id
        ]
        if not unique_ids:
            return []

        existing = await session.scalars(
            select(SponsorCompletion.sponsor_id).where(
                SponsorCompletion.user_id == user_id,
                SponsorCompletion.sponsor_id.in_(unique_ids),
            )
        )
        existing_ids = set(existing.all())
        new_ids = [
            sponsor_id for sponsor_id in unique_ids
            if sponsor_id not in existing_ids
        ]

        for sponsor_id in new_ids:
            session.add(
                SponsorCompletion(
                    user_id=user_id,
                    sponsor_id=sponsor_id,
                    created_at=datetime.now(),
                )
            )

        return new_ids

    @staticmethod
    def _item_key(item: SubscriptionItem) -> tuple[str, str]:
        return (
            str(item.link or '').strip().rstrip('/'),
            str(item.title or '').strip(),
        )

    @classmethod
    def _extend_unique_items(
        cls,
        target: list[SubscriptionItem],
        items: list[SubscriptionItem],
        seen_keys: set[tuple[str, str]],
    ) -> None:
        for item in items:
            key = cls._item_key(item)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            target.append(item)

    async def complete_flyer_signatures(
        self,
        session: AsyncSession,
        user_id: int,
        signatures: list[str],
    ) -> set[str]:
        completed: set[str] = set()

        for signature in dict.fromkeys(signatures):
            result = await self._check_flyer_task(user_id, signature)
            if self._is_completed_flyer_status(str(result or '').strip().lower()):
                completed.add(signature)

        if not completed:
            return completed

        existing = await session.scalars(
            select(FlyerCompletion.signature).where(
                FlyerCompletion.user_id == user_id,
                FlyerCompletion.signature.in_(completed),
            )
        )
        existing_signatures = set(existing.all())

        for signature in completed - existing_signatures:
            session.add(
                FlyerCompletion(
                    user_id=user_id,
                    signature=signature,
                    created_at=datetime.now(),
                )
            )

        await session.commit()
        return completed

    async def _resolve_sponsors(
        self,
        sponsors: list[Sponsor],
        user: User,
        bot: Bot,
    ) -> list[SubscriptionItem]:
        response = await asyncio.gather(
            *(
                self._check_sponsor(sponsor, user, bot)
                for sponsor in sponsors
            ),
        )
        pending_sponsors = [
            sponsor for sponsor in response
            if sponsor is not None
        ]

        return [
            self._build_sponsor_item(sponsor, required=True)
            for sponsor in pending_sponsors
        ]

    @staticmethod
    def _build_sponsor_item(
        sponsor: Sponsor,
        required: bool,
    ) -> SubscriptionItem:
        return SubscriptionItem(
            title=sponsor.title,
            link=sponsor.link,
            source='sponsor',
            required=required,
            sponsor_id=sponsor.id,
        )

    async def _resolve_flyer_items(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int,
    ) -> list[SubscriptionItem]:
        completed = await session.scalars(
            select(FlyerCompletion.signature).where(
                FlyerCompletion.user_id == user_id,
            )
        )
        completed_signatures = set(completed.all())
        tasks = await self._request_flyer_tasks(
            user_id=user_id,
            limit=max(limit * 4, limit),
        )

        if not tasks:
            return []

        items: list[SubscriptionItem] = []
        for task in tasks:
            signature = str(task.get('signature') or '').strip()
            link = self._get_primary_link(task)
            task_type = str(task.get('task') or '').strip().lower()
            task_status = str(task.get('status') or '').strip().lower()

            if (
                not signature
                or not link
                or signature in completed_signatures
                or self._is_completed_flyer_status(task_status)
                or not task_type.startswith('subscribe')
            ):
                continue

            items.append(
                SubscriptionItem(
                    title=self._build_flyer_title(task, len(items) + 1),
                    link=link,
                    source='flyer',
                    required=True,
                    signature=signature,
                )
            )
            if len(items) >= limit:
                break

        return items

    async def _request_flyer_tasks(
        self,
        user_id: int,
        limit: int,
    ) -> list[dict]:
        if not self.flyer_key:
            return []

        session = await self._get_session()
        try:
            async with session.post(
                f'{self.flyer_base_url}/get_tasks',
                json={
                    'key': self.flyer_key,
                    'user_id': user_id,
                    'limit': limit,
                },
            ) as response:
                if response.status < 200 or response.status >= 300:
                    logger.warning(
                        'Flyer get_tasks failed: status=%s user_id=%s',
                        response.status,
                        user_id,
                    )
                    return []

                data = await response.json(content_type=None)
                if data.get('error'):
                    logger.warning(
                        'Flyer get_tasks error for user_id=%s: %s',
                        user_id,
                        data['error'],
                    )
                    return []
                if data.get('warning'):
                    logger.info(
                        'Flyer warning for user_id=%s: %s',
                        user_id,
                        data['warning'],
                    )
                    return []

                result = data.get('result')
                return result if isinstance(result, list) else []
        except Exception:
            logger.exception('Flyer get_tasks request failed')
            return []

    async def _check_flyer_task(
        self,
        user_id: int,
        signature: str,
    ) -> Optional[str]:
        if not self.flyer_key or not signature:
            return None

        session = await self._get_session()
        try:
            async with session.post(
                f'{self.flyer_base_url}/check_task',
                json={
                    'key': self.flyer_key,
                    'user_id': user_id,
                    'signature': signature,
                },
            ) as response:
                if response.status < 200 or response.status >= 300:
                    logger.warning(
                        'Flyer check_task failed: status=%s user_id=%s',
                        response.status,
                        user_id,
                    )
                    return None

                data = await response.json(content_type=None)
                if data.get('error'):
                    logger.warning(
                        'Flyer check_task error for user_id=%s signature=%s: %s',
                        user_id,
                        signature,
                        data['error'],
                    )
                    return None
                result = data.get('result')
                return str(result).strip().lower() if result else None
        except Exception:
            logger.exception('Flyer check_task request failed')
            return None

    @staticmethod
    def _is_completed_flyer_status(status: str) -> bool:
        return status in {
            'complete',
            'completed',
            'waiting',
            'done',
        }

    async def _check_sponsor(
        self,
        sponsor: Sponsor,
        user: User,
        bot: Bot,
    ) -> Optional[Sponsor]:
        if sponsor.is_bot:
            try:
                bot_ = Bot(sponsor.access_id, session=bot.session)
                await bot_.send_chat_action(user.id, 'typing')
            except TokenValidationError:
                with suppress(ValueError):
                    self._validate_botstat_token(sponsor.access_id)
                    session = await self._get_session()
                    async with session.get(
                        'https://api.botstat.io/checksub/%s/%i' % (
                            sponsor.access_id, user.id,
                        )
                    ) as response:
                        data = await response.json(content_type=None)
                        if not data.get('ok'):
                            return sponsor
            except (
                TelegramNotFound,
                TelegramBadRequest,
                TelegramForbiddenError,
            ):
                return sponsor
            except TelegramAPIError:
                logger.warning(
                    'Unable to verify bot sponsor id=%s',
                    sponsor.id,
                    exc_info=True,
                )
                return sponsor
            return None

        chat_reference = self._resolve_chat_reference(sponsor)
        if chat_reference is None:
            logger.warning(
                'Sponsor id=%s has no valid channel reference for OP check',
                sponsor.id,
            )
            return sponsor

        try:
            member = await bot.get_chat_member(
                chat_reference,
                user.id,
            )
        except TelegramAPIError:
            logger.warning(
                'Unable to verify channel sponsor id=%s via %s',
                sponsor.id,
                chat_reference,
                exc_info=True,
            )
            return sponsor

        if member.status in ('left', 'kicked', None):
            return sponsor

        return None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @staticmethod
    def _get_primary_link(task: dict) -> Optional[str]:
        links = task.get('links') or []
        if isinstance(links, list):
            for link in links:
                if link:
                    return str(link).strip()

        link = task.get('link')
        return str(link).strip() if link else None

    @staticmethod
    def _build_flyer_title(task: dict, index: int) -> str:
        name = str(task.get('name') or '').strip() or f'Flyer канал {index}'
        title = f'🔥 {name}'
        return title[:63] + '…' if len(title) > 64 else title

    @staticmethod
    def _resolve_chat_reference(sponsor: Sponsor) -> Optional[int | str]:
        access_id = str(sponsor.access_id or '').strip()
        if access_id and access_id != '0':
            if access_id.lstrip('-').isdigit():
                return int(access_id)
            normalized_access = access_id
            if '://' in access_id:
                with suppress(ValueError):
                    parsed = urlparse(access_id)
                    if parsed.netloc in {
                        't.me',
                        'www.t.me',
                        'telegram.me',
                        'www.telegram.me',
                    }:
                        normalized_access = ''
                        path = parsed.path.strip('/')
                        if path:
                            username = path.split('/')[0]
                            if (
                                username
                                and username not in {'joinchat', 'c'}
                                and not username.startswith('+')
                            ):
                                normalized_access = username

            normalized_access = normalized_access.removeprefix('@')
            if normalized_access:
                return f'@{normalized_access}'

        link = str(sponsor.link or '').strip()
        if not link:
            return None

        normalized_link = link if '://' in link else f'https://{link}'
        with suppress(ValueError):
            parsed = urlparse(normalized_link)
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
            if not username or username.startswith('+') or username == 'joinchat':
                return None

            username = username.removeprefix('@')
            return f'@{username}'

        return None

    @staticmethod
    @lru_cache
    def _validate_botstat_token(token: str) -> None:
        if len(token.split('-')) != 5:
            raise ValueError


def render_subscription_text(
    items: list[SubscriptionItem],
    failed_check: bool = False,
) -> str:
    lines = '\n'.join(
        '• %s' % escape(str(item.title or '').strip())
        for item in items
        if str(item.title or '').strip()
    ) or '• Список недостающих каналов недоступен'

    if failed_check:
        return texts.user.NOT_SUBBED_FAILED % lines

    return texts.user.NOT_SUBBED % lines
