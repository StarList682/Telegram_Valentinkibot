from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, bigint


class OpAccess(Base):
    __tablename__ = 'op_access'

    user_id: Mapped[bigint] = mapped_column(primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(default=datetime.now)
    expires_at: Mapped[datetime]
