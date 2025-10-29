"""
WhatsApp-specific модели пользователей
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from datetime import datetime
import sys
from pathlib import Path

# Добавляем путь к shared
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.database.connection import Base
from shared.models.base import IDMixin, TimestampMixin, TenantMixin


class WhatsAppUser(Base, IDMixin, TimestampMixin, TenantMixin):
    """
    Дополнительные данные пользователя WhatsApp.

    Таблица: whatsapp_users
    Связана с shared_tenants через tenant_id
    """
    __tablename__ = "whatsapp_users"
    __table_args__ = {'comment': 'Пользователи WhatsApp (platform-specific)'}

    # WhatsApp ID (формат: 996507988088@c.us)
    whatsapp_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="WhatsApp ID (phone@c.us)"
    )

    # Основные данные
    phone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Номер телефона"
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Имя пользователя из WhatsApp"
    )

    # WhatsApp-specific поля
    instance_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="GreenAPI instance ID"
    )
    profile_picture_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="URL аватара пользователя"
    )

    def __repr__(self) -> str:
        return f"<WhatsAppUser(id={self.id}, whatsapp_id={self.whatsapp_id}, name={self.name})>"


class WhatsAppSession(Base, IDMixin, TimestampMixin):
    """
    Сессии WhatsApp (для OpenAI threads и состояний).

    Таблица: whatsapp_sessions
    Хранит активные сессии диалогов
    """
    __tablename__ = "whatsapp_sessions"
    __table_args__ = {'comment': 'Сессии WhatsApp диалогов'}

    whatsapp_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("whatsapp_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID пользователя WhatsApp"
    )

    # OpenAI Thread ID (для AI-диалогов)
    thread_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="OpenAI Thread ID"
    )

    # Состояние диалога
    state: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Текущее состояние диалога"
    )
    state_data: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="JSON данные состояния"
    )

    # Метаданные
    last_activity: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        comment="Время последней активности"
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Количество сообщений в сессии"
    )

    # Связь с пользователем
    whatsapp_user: Mapped["WhatsAppUser"] = relationship(
        "WhatsAppUser",
        backref="sessions"
    )

    def __repr__(self) -> str:
        return f"<WhatsAppSession(user_id={self.whatsapp_user_id}, thread_id={self.thread_id})>"
