from aiogram.types import BotCommand


ADMIN_COMMANDS = [
    BotCommand(
        command='panel',
        description='Открыть админ-панель',
    ),
    BotCommand(
        command='stats',
        description='Статистика пользователей',
    ),
    BotCommand(
        command='mailing',
        description='Рассылка',
    ),
    BotCommand(
        command='greeting',
        description='Приветка после /start',
    ),
    BotCommand(
        command='startmenu',
        description='Стартовое меню',
    ),
    BotCommand(
        command='revealprice',
        description='Цена узнать кто отправил',
    ),
    BotCommand(
        command='sponsors',
        description='Спонсоры и ОП',
    ),
    BotCommand(
        command='dump',
        description='Выгрузка пользователей',
    ),
    BotCommand(
        command='referrals',
        description='UTC/UTM ссылки',
    ),
    BotCommand(
        command='utc',
        description='UTC/UTM ссылки',
    ),
    BotCommand(
        command='admins',
        description='Список админов',
    ),
]
