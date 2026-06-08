from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


CONFIRM = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Подтвердить',
                callback_data='mailing:confirm',
            ),
            InlineKeyboardButton(
                text='Отмена',
                callback_data='cancel',
            ),
        ],
    ],
)


MAILING_BUTTONS = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text='Без кнопок',
                callback_data='mailing:skip_buttons',
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
