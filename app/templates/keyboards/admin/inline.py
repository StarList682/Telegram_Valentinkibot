from math import ceil
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.database.models import (
    Advert,
    MainMenuButton,
    OpSetting,
    RequestChannel,
    Sponsor,
)


MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Статистика',
                callback_data='admin:stats',
            ),
            InlineKeyboardButton(
                text='Рассылка',
                callback_data='admin:mailing',
            ),
            InlineKeyboardButton(
                text='Спонсоры',
                callback_data='admin:sponsors',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Выгрузка',
                callback_data='admin:dump',
            ),
            InlineKeyboardButton(
                text='UTC ссылки',
                callback_data='admin:refs',
            ),
            InlineKeyboardButton(
                text='Админы',
                callback_data='admin:admins',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Приветка',
                callback_data='admin:greeting',
            ),
            InlineKeyboardButton(
                text='Меню старта',
                callback_data='admin:startmenu',
            ),
            InlineKeyboardButton(
                text='Кто отправил',
                callback_data='admin:revealprice',
            ),
        ],
    ],
)


def back_panel_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text='Назад',
            callback_data='admin:panel',
        ),
    ]


def choice(item_id: int | str, prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Да',
                    callback_data='%s:del2:%s' % (prefix, item_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Нет',
                    callback_data='%s:info:%s' % (prefix, item_id),
                ),
            ],
        ],
    )


def channels(channels: list[RequestChannel]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='🟢' if channel.active else '⭕',
                    callback_data='request:active:%i' % channel.id,
                ),
                InlineKeyboardButton(
                    text=channel.title,
                    callback_data='none',
                ),
                InlineKeyboardButton(
                    text=str(channel.visits),
                    callback_data='none',
                ),
                InlineKeyboardButton(
                    text='🗑',
                    callback_data='request:del:%i' % channel.id,
                ),
            ] for channel in channels
        ] + [back_panel_row()]
    )


def ref(ref: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Назад',
                    callback_data='ref:list:1',
                ),
                InlineKeyboardButton(
                    text='Удалить',
                    callback_data='ref:del:%s' % ref,
                ),
            ]
        ]
    )


def ref_list(refs: list[str], page: int = 1) -> dict:
    pages = ceil(len(refs)/9) or 1
    refs = refs[(page - 1) * 9:page * 9]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            *(
                [
                    InlineKeyboardButton(
                        text=ref,
                        callback_data='ref:info:%s' % ref,
                    ),
                ] for ref in refs
            ),
            [
                InlineKeyboardButton(
                    text='Добавить UTC ссылку',
                    callback_data='ref:add:',
                ),
            ],
            [
                InlineKeyboardButton(
                    text='<-',
                    callback_data='ref:list:%i' % (page - 1),
                ),
                InlineKeyboardButton(
                    text='%i/%i' % (page, pages),
                    callback_data='none',
                ),
                InlineKeyboardButton(
                    text='->',
                    callback_data='ref:list:%i' % (page + 1),
                ),
            ],
            back_panel_row(),
        ],
    )


def sponsors(
    sponsors: list[Sponsor],
    settings: OpSetting,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *(
                [
                    InlineKeyboardButton(
                        text='🟢' if sponsor.is_active else '⭕',
                        callback_data='sponsor:active:%i' % sponsor.id,
                    ),
                    InlineKeyboardButton(
                        text=(
                            '🤖 ' if sponsor.is_bot else '💬 '
                        ) + sponsor.title,
                        callback_data='sponsor:info:%i' % sponsor.id,
                    ),
                    InlineKeyboardButton(
                        text='%i/%s' % (sponsor.visits, sponsor.limit or '∞'),
                        callback_data='sponsor:info:%i' % sponsor.id,
                    ),
                    InlineKeyboardButton(
                        text='🗑',
                        callback_data='sponsor:del:%i' % sponsor.id,
                    ),
                ] for sponsor in sponsors
            ),
            [
                InlineKeyboardButton(
                    text='Flyer %s' % (
                        '🟢' if settings.flyer_enabled else '⭕'
                    ),
                    callback_data='opcfg:flyer',
                ),
                InlineKeyboardButton(
                    text='Свои каналы %s' % (
                        '🟢' if settings.own_channels_enabled else '⭕'
                    ),
                    callback_data='opcfg:own',
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Flyer в ОП: %i' % settings.flyer_limit,
                    callback_data='opcfg:limit',
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Добавить',
                    callback_data='sponsor:add',
                ),
            ],
            back_panel_row(),
        ],
    )


FLYER_LIMIT = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='1',
                callback_data='opcfg:setlimit:1',
            ),
            InlineKeyboardButton(
                text='2',
                callback_data='opcfg:setlimit:2',
            ),
            InlineKeyboardButton(
                text='3',
                callback_data='opcfg:setlimit:3',
            ),
        ],
        [
            InlineKeyboardButton(
                text='5',
                callback_data='opcfg:setlimit:5',
            ),
            InlineKeyboardButton(
                text='10',
                callback_data='opcfg:setlimit:10',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Свой лимит',
                callback_data='opcfg:setlimit:custom',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Назад',
                callback_data='opcfg:back',
            ),
        ],
    ],
)


PRICING = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='VIP 1 день',
                callback_data='pricecfg:edit:vip_day_price',
            ),
        ],
        [
            InlineKeyboardButton(
                text='VIP 7 дней',
                callback_data='pricecfg:edit:vip_week_price',
            ),
        ],
        [
            InlineKeyboardButton(
                text='VIP 31 день',
                callback_data='pricecfg:edit:vip_month_price',
            ),
        ],
        [
            InlineKeyboardButton(
                text='VIP 365 дней',
                callback_data='pricecfg:edit:vip_year_price',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Скидка',
                callback_data='pricecfg:discount',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Назад',
                callback_data='pricecfg:back',
            ),
        ],
    ],
)


AGE_LIMITS = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Изменить диапазон',
                callback_data='agecfg:edit',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Назад',
                callback_data='agecfg:back',
            ),
        ],
    ],
)


def admins(
    delegated_admin_ids: list[int],
    can_manage: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if can_manage:
        rows.append(
            [
                InlineKeyboardButton(
                    text='Выдать админку',
                    callback_data='admins:grant',
                ),
            ],
        )

        rows.extend(
            [
                InlineKeyboardButton(
                    text='Изъять у %i' % user_id,
                    callback_data='admins:revoke:%i' % user_id,
                ),
            ] for user_id in delegated_admin_ids
        )

    rows.append(
        [
            InlineKeyboardButton(
                text='Обновить',
                callback_data='admins:list',
            ),
            InlineKeyboardButton(
                text='Назад',
                callback_data='admins:back',
            ),
        ],
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def template_actions(
    template_key: str,
    *,
    is_custom: bool,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text='Изменить',
                callback_data='template:edit:%s' % template_key,
            ),
        ],
        [
            InlineKeyboardButton(
                text='Предпросмотр',
                callback_data='template:preview:%s' % template_key,
            ),
        ],
    ]

    if is_custom:
        rows.append(
            [
                InlineKeyboardButton(
                    text='Сбросить',
                    callback_data='template:reset:%s' % template_key,
                ),
            ],
        )

    rows.append(back_panel_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


REVEAL_PRICE = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Изменить цену',
                callback_data='revealcfg:edit',
            ),
        ],
        back_panel_row(),
    ],
)


TOOLS = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='VIP',
                callback_data='tools:vip',
            ),
            InlineKeyboardButton(
                text='Бан',
                callback_data='tools:ban',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Баланс',
                callback_data='tools:balance',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Назад',
                callback_data='tools:back',
            ),
        ],
    ],
)


def adverts(adverts: list[Advert]) -> dict:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *(
                [
                    InlineKeyboardButton(
                        text='🟢' if advert.is_active else '⭕',
                        callback_data='ad:status:%i' % advert.id,
                    ),
                    InlineKeyboardButton(
                        text=advert.title,
                        callback_data='ad:show:%i' % advert.id,
                    ),
                    InlineKeyboardButton(
                        text='%i/%s' % (advert.views, advert.target or '∞'),
                        callback_data='none',
                    ),
                    InlineKeyboardButton(
                        text='🗑',
                        callback_data='ad:del:%i' % advert.id,
                    ),
                ] for advert in adverts
            ),
            [
                InlineKeyboardButton(
                    text='Добавить',
                    callback_data='ad:add',
                ),
            ],
            back_panel_row(),
        ],
    )


def menu_links(
    buttons: list[MainMenuButton],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *(
                [
                    InlineKeyboardButton(
                        text='🟢' if button.is_active else '⭕',
                        callback_data='mlink:toggle:%i' % button.id,
                    ),
                    InlineKeyboardButton(
                        text=button.title[:40],
                        callback_data='mlink:info:%i' % button.id,
                    ),
                    InlineKeyboardButton(
                        text='🗑',
                        callback_data='mlink:del:%i' % button.id,
                    ),
                ] for button in buttons
            ),
            [
                InlineKeyboardButton(
                    text='Добавить',
                    callback_data='mlink:add',
                ),
            ],
            back_panel_row(),
        ],
    )


def menu_link_info(button: MainMenuButton) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        'Выключить'
                        if button.is_active else
                        'Включить'
                    ),
                    callback_data='mlink:toggle:%i' % button.id,
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Удалить',
                    callback_data='mlink:del:%i' % button.id,
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Назад',
                    callback_data='mlink:list',
                ),
            ],
        ],
    )


def menu_link_delete(button_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Да',
                    callback_data='mlink:del2:%i' % button_id,
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Нет',
                    callback_data='mlink:info:%i' % button_id,
                ),
            ],
        ],
    )


DUMP = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Выгрузить всех',
                callback_data='dump:all',
            ),
        ],
        back_panel_row(),
    ],
)

CANCEL = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Отмена',
                callback_data='cancel',
            ),
        ],
    ],
)

SPONSOR_CHOICE = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='🤖 Бот',
                callback_data='addsponsor:bot',
            ),
            InlineKeyboardButton(
                text='💬 Канал',
                callback_data='addsponsor:channel',
            ),
        ],
    ],
)

SPONSOR_CHECK = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Проверять ✅',
                callback_data='sadd:check:1',
            ),
            InlineKeyboardButton(
                text='Не проверять ❌',
                callback_data='sadd:check:0',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Отмена',
                callback_data='cancel',
            ),
        ],
    ],
)

SPONSOR_LIMIT = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Без лимита',
                callback_data='sadd:limit:0',
            ),
            InlineKeyboardButton(
                text='10',
                callback_data='sadd:limit:10',
            ),
        ],
        [
            InlineKeyboardButton(
                text='50',
                callback_data='sadd:limit:50',
            ),
            InlineKeyboardButton(
                text='100',
                callback_data='sadd:limit:100',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Свой лимит',
                callback_data='sadd:limit:custom',
            ),
        ],
        [
            InlineKeyboardButton(
                text='Отмена',
                callback_data='cancel',
            ),
        ],
    ],
)

STOPMAIL = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Остановить рассылку',
                callback_data='stopmail',
            ),
        ],
    ],
)
