from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import PriceSetting
from prices import VIP_OPTIONS
from app.utils.reveal_sender import DEFAULT_REVEAL_SENDER_PRICE


VIP_ITEM_META = {
    'day': {
        'field': 'vip_day_price',
        'title': 'VIP на 1 день',
        'label': '🔥 На день',
        'days': VIP_OPTIONS['day']['days'],
        'default_price': VIP_OPTIONS['day']['price'],
    },
    'week': {
        'field': 'vip_week_price',
        'title': 'VIP на 7 дней',
        'label': 'На неделю',
        'days': VIP_OPTIONS['week']['days'],
        'default_price': VIP_OPTIONS['week']['price'],
    },
    'month': {
        'field': 'vip_month_price',
        'title': 'VIP на 31 день',
        'label': 'На месяц',
        'days': VIP_OPTIONS['month']['days'],
        'default_price': VIP_OPTIONS['month']['price'],
    },
    'year': {
        'field': 'vip_year_price',
        'title': 'VIP на 365 дней',
        'label': 'На год',
        'days': VIP_OPTIONS['year']['days'],
        'default_price': VIP_OPTIONS['year']['price'],
    },
}

EDITABLE_PRICE_FIELDS = {
    meta['field']: meta['title']
    for meta in VIP_ITEM_META.values()
}


async def get_price_settings(session: AsyncSession) -> PriceSetting:
    settings = await session.get(PriceSetting, 1)
    if settings is None:
        settings = PriceSetting(id=1)
        session.add(settings)
        await session.commit()
    return settings


def clamp_discount_percent(value: int) -> int:
    return max(0, min(100, int(value)))


def apply_discount(price: int, discount_percent: int) -> int:
    discount = clamp_discount_percent(discount_percent)
    return max(0, round(price * (100 - discount) / 100))


def format_vip_option_name(
    label: str,
    price: int,
    discount_percent: int,
) -> str:
    suffix = '' if discount_percent <= 0 else ' (-%i%%)' % discount_percent
    return '%s - %i руб.%s' % (label, price, suffix)


def format_price_summary(base_price: int, final_price: int) -> str:
    if base_price == final_price:
        return '<code>%i ₽</code>' % final_price

    return '<code>%i ₽ -> %i ₽</code>' % (base_price, final_price)


def build_vip_options(settings: PriceSetting) -> dict[str, dict[str, Any]]:
    discount = clamp_discount_percent(settings.discount_percent)
    items: dict[str, dict[str, Any]] = {}

    for key, meta in VIP_ITEM_META.items():
        base_price = int(getattr(settings, meta['field']))
        final_price = apply_discount(base_price, discount)
        items[key] = {
            'name': format_vip_option_name(
                meta['label'],
                final_price,
                discount,
            ),
            'label': meta['label'],
            'title': meta['title'],
            'price': final_price,
            'base_price': base_price,
            'days': meta['days'],
        }

    return items


async def get_pricing_snapshot(session: AsyncSession) -> dict[str, Any]:
    settings = await get_price_settings(session)
    return {
        'settings': settings,
        'discount_percent': clamp_discount_percent(settings.discount_percent),
        'vip_options': build_vip_options(settings),
    }


async def get_vip_options(
    session: AsyncSession,
) -> dict[str, dict[str, Any]]:
    settings = await get_price_settings(session)
    return build_vip_options(settings)


async def get_reveal_sender_price(
    session: AsyncSession,
) -> int:
    settings = await get_price_settings(session)
    value = int(getattr(settings, 'reveal_sender_price', DEFAULT_REVEAL_SENDER_PRICE))
    return max(1, value)
