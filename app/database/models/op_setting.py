from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OpSetting(Base):
    __tablename__ = 'op_settings'

    id: Mapped[int] = mapped_column(primary_key=True)
    flyer_enabled: Mapped[bool] = mapped_column(default=False)
    own_channels_enabled: Mapped[bool] = mapped_column(default=True)
    flyer_limit: Mapped[int] = mapped_column(default=1)
    min_age: Mapped[int] = mapped_column(default=16)
    max_age: Mapped[int] = mapped_column(default=99)
