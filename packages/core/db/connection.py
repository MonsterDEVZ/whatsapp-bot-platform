"""
Управление подключением к базе данных PostgreSQL.
"""

import sys
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

# Импортируем через относительные импорты
from ..database.models import Base
from ..config import Config

# Глобальные переменные для engine и session factory
engine = None
async_session_factory = None


async def init_db(config: Config) -> None:
    """
    Инициализирует подключение к базе данных.

    Args:
        config: Экземпляр конфигурации с настройками БД

    Creates:
        - Async engine
        - Session factory
    """
    global engine, async_session_factory

    # Создаем async engine
    engine = create_async_engine(
        config.database.async_url,
        echo=config.debug,  # Логировать SQL запросы если debug=True
        pool_pre_ping=True,  # Проверять соединение перед использованием
        pool_size=5,
        max_overflow=10
    )

    # Создаем фабрику сессий
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Проверяем подключение
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("[OK] Podklyuchenie k baze dannykh ustanovleno")
    except Exception as e:
        print(f"[ERROR] Oshibka podklyucheniya k baze dannykh: {e}")
        raise


async def close_db() -> None:
    """
    Закрывает подключение к базе данных.
    """
    global engine

    if engine:
        await engine.dispose()
        print("[OK] Podklyuchenie k baze dannykh zakryto")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Создает и возвращает сессию базы данных.

    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy

    Example:
        async for session in get_session():
            result = await session.execute(select(Tenant))
            tenants = result.scalars().all()
    """
    if async_session_factory is None:
        raise RuntimeError(
            "База данных не инициализирована. "
            "Вызовите init_db() перед использованием get_session()."
        )

    async with async_session_factory() as session:
        yield session
