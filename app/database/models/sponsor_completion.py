from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, bigint


class SponsorCompletion(Base):
    __tablename__ = 'sponsor_completions'
    __table_args__ = (
        UniqueConstraint('user_id', 'sponsor_id', name='uq_user_sponsor'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[bigint]
    sponsor_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
