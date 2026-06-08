from aiogram.filters import Filter
from app.database.models import User


class IsVip(Filter):
    def __init__(self, is_vip: bool = True) -> None:
        self.is_vip = is_vip

    async def __call__(self, _, user: User) -> bool:
        return self.is_vip == user.is_vip
