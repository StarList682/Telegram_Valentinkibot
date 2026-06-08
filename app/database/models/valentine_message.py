from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, bigint


class ValentineMessage(Base):
    __tablename__ = 'valentine_messages'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    sender_id: Mapped[bigint]
    receiver_id: Mapped[bigint]
    receiver_chat_id: Mapped[bigint]
    receiver_message_id: Mapped[Optional[bigint]]

    sender_name: Mapped[Optional[str]]
    sender_username: Mapped[Optional[str]]

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    revealed_at: Mapped[Optional[datetime]]
    reveal_charge_id: Mapped[Optional[str]]
    reveal_stars_paid: Mapped[Optional[int]]
