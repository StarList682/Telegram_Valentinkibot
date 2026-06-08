from typing import Optional
from aiogram import types


def escape(text: str) -> str:
    return (
        text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def link(user: types.User, text: str | None = None) -> str:
    url = (
        'https://t.me/%s' % user.username
        if user.username else
        'tg://user?id=%i' % user.id
    )

    return '<a href="%s">%s</a>' % (
        url, text or escape(user.first_name),
    )


def get_ref(message: types.Message, check: bool = True) -> Optional[str]:
    if check and not message.text.startswith('/start'):
        return

    if args := message.text.split()[1:]:
        return args[0]
