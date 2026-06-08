from aiogram import Router
from . import (
    dump,
    start,
    stats,
    referrals,
    subscribe,
    mail,
    admins,
    start_messages,
    reveal_price,
)


def setup(router: Router) -> None:
    start.register(router)
    dump.register(router)
    mail.register(router)
    stats.register(router)
    start_messages.register(router)
    reveal_price.register(router)
    referrals.register(router)
    subscribe.register(router)
    admins.register(router)
