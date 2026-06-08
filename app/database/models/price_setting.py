from sqlalchemy.orm import Mapped, mapped_column

from prices import VIP_OPTIONS
from app.utils.reveal_sender import DEFAULT_REVEAL_SENDER_PRICE

from .base import Base


class PriceSetting(Base):
    __tablename__ = 'price_settings'

    id: Mapped[int] = mapped_column(primary_key=True)
    vip_day_price: Mapped[int] = mapped_column(
        default=VIP_OPTIONS['day']['price']
    )
    vip_week_price: Mapped[int] = mapped_column(
        default=VIP_OPTIONS['week']['price']
    )
    vip_month_price: Mapped[int] = mapped_column(
        default=VIP_OPTIONS['month']['price']
    )
    vip_year_price: Mapped[int] = mapped_column(
        default=VIP_OPTIONS['year']['price']
    )
    reveal_sender_price: Mapped[int] = mapped_column(
        default=DEFAULT_REVEAL_SENDER_PRICE
    )
    discount_percent: Mapped[int] = mapped_column(default=0)
