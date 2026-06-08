from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MessageTemplate(Base):
    __tablename__ = 'message_templates'

    key: Mapped[str] = mapped_column(primary_key=True)
    content_type: Mapped[str]
    file_id: Mapped[Optional[str]]
    html_text: Mapped[Optional[str]]
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
    )
