from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from .base import bigint, Base


class FlyerCompletion(Base):
    __tablename__ = 'flyer_completions'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[bigint]
    signature: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
