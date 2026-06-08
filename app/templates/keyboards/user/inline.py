from typing import TYPE_CHECKING, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

if TYPE_CHECKING:
    from app.utils.payments import BaseBill
else:
    BaseBill = Any


def split(items: list, size: int) -> list[list]:
    return [
        items[index:index + size]
        for index in range(0, len(items), size)
    ]


def _get_item_attr(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def subscription(sponsors: list[Any]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *(
                [
                    InlineKeyboardButton(
                        text=_get_item_attr(sponsor, 'title'),
                        url=_get_item_attr(sponsor, 'link'),
                    ),
                ] for sponsor in sponsors
            ),
            [
                InlineKeyboardButton(
                    text='Проверить подписку',
                    callback_data='checksub',
                ),
            ],
        ]
    )


def bill(
    bill: BaseBill, item_id: str, is_vip: bool = True
) -> InlineKeyboardMarkup:
    if is_vip:
        check_callback = 'check:vip:%s:%s:%s' % (
            bill.provider,
            bill.id,
            item_id,
        )
    else:
        check_callback = 'check:profile:%s:%s' % (
            bill.provider,
            bill.id,
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Оплатить 🔗',
                    url=bill.url,
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Проверить ✅',
                    callback_data=check_callback,
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Назад 🔙',
                    callback_data='back:vip' if is_vip else 'back:profile',
                ),
            ],
        ]
    )


def choose_bill(item_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Оплатить балансом 💰',
                    callback_data='buy:balance:%s' % item_id,
                )
            ],
            [
                InlineKeyboardButton(
                    text='Оплатить звездами ⭐',
                    callback_data='buy:stars:%s' % item_id,
                )
            ],
            [
                InlineKeyboardButton(
                    text='Оплатить криптой 🪙',
                    callback_data='buy:crypto:%s' % item_id,
                )
            ],
            [
                InlineKeyboardButton(
                    text='СПБ 💳',
                    callback_data='buy:platega:%s' % item_id,
                )
            ],
            [
                InlineKeyboardButton(
                    text='Назад 🔙',
                    callback_data='back:vip',
                ),
            ],
        ]
    )


def choose_top_up_method(amount: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Оплатить звездами ⭐',
                    callback_data='topup:stars:%i' % amount,
                )
            ],
            [
                InlineKeyboardButton(
                    text='Оплатить криптой 🪙',
                    callback_data='topup:crypto:%i' % amount,
                )
            ],
            [
                InlineKeyboardButton(
                    text='СПБ 💳',
                    callback_data='topup:platega:%i' % amount,
                )
            ],
            [
                InlineKeyboardButton(
                    text='Назад 🔙',
                    callback_data='back:profile',
                )
            ],
        ]
    )


def confirm_buy_balance(item_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Подтвердить✅',
                    callback_data='accept:buy:balance:%s' % item_id,
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Назад 🔙',
                    callback_data='back:vip',
                ),
            ],
        ]
    )


def buy(vip_options: dict[str, dict[str, Any]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *(
                [
                    InlineKeyboardButton(
                        text=item['name'],
                        callback_data='buy:%s' % key,
                    ),
                ] for key, item in vip_options.items()
            ),
            [
                InlineKeyboardButton(
                    text='Получить бесплатно 🤫',
                    callback_data='ref',
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Главное меню',
                    callback_data='menu:main',
                ),
            ],
        ],
    )


BACK_VIP = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Назад 🔙',
                callback_data='back:vip',
            ),
        ],
    ],
)
