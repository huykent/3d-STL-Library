from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppConfig(Base):
    """
    Store dynamic application configurations (e.g. Telegram API keys, Ollama URL).
    Replaces static variables in .env so Admins can change them via Web UI.
    """
    __tablename__ = "app_configs"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
