from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Mapped, mapped_column
from .base import bigint, Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[bigint] = mapped_column(primary_key=True)

    username: Mapped[Optional[str]] = mapped_column(default=None)
    first_name: Mapped[Optional[str]] = mapped_column(default=None)
    last_name: Mapped[Optional[str]] = mapped_column(default=None)

    join_date: Mapped[datetime] = mapped_column(default=datetime.now)
    block_date: Mapped[Optional[datetime]]

    ref: Mapped[Optional[str]]
    subbed: Mapped[bool] = mapped_column(default=False)
    subbed_before: Mapped[bool] = mapped_column(default=False)

    invited: Mapped[int] = mapped_column(default=0)

    vip_time: Mapped[datetime] = mapped_column(
        default=datetime.fromtimestamp(0)
    )
    balance: Mapped[int] = mapped_column(default=0)
    chat_only: Mapped[bool] = mapped_column(default=False)

    is_admin: Mapped[bool] = mapped_column(default=False)
    is_banned: Mapped[bool] = mapped_column(default=False)

    age: Mapped[Optional[int]] = mapped_column(default=None)
    is_man: Mapped[Optional[bool]] = mapped_column(default=None)
    friends: Mapped[str] = mapped_column(default='[]')
    in_room: Mapped[int] = mapped_column(default=0)
    dialogue_id: Mapped[Optional[int]] = mapped_column(default=None)

    @property
    def is_vip(self) -> bool:
        return (
            self.vip_time is not None
            and self.vip_time > datetime.now()
        )

    def add_vip(self, days: int) -> None:
        self.vip_time = max(
            self.vip_time, datetime.now()
        ) + timedelta(days=days)
