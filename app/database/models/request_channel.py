from sqlalchemy.orm import Mapped, mapped_column
from .base import bigint, Base


class RequestChannel(Base):
    __tablename__ = 'request_channels'

    id: Mapped[bigint] = mapped_column(primary_key=True)

    active: Mapped[bool] = mapped_column(default=False)
    title: Mapped[str]
    visits: Mapped[int] = mapped_column(default=0)
