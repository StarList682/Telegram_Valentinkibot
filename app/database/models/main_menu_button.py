from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MainMenuButton(Base):
    __tablename__ = 'main_menu_buttons'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str]
    url: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
