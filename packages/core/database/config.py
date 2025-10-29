"""
Конфигурация подключения к базе данных.

Использует переменные окружения для безопасного хранения credentials.
Поддерживает как локальную разработку, так и production окружение.

Environment variables:
    DATABASE_URL: Полный URL подключения (опционально)
    DB_HOST: Хост БД (default: localhost)
    DB_PORT: Порт БД (default: 5432)
    DB_NAME: Имя БД (default: car_chatbot)
    DB_USER: Пользователь БД (default: postgres)
    DB_PASSWORD: Пароль БД (required)
    DB_ECHO: Логировать SQL запросы (default: False)

Author: Claude
Date: 2025-01-09
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)


class DatabaseConfig:
    """Конфигурация базы данных из переменных окружения."""

    def __init__(self):
        # Проверяем наличие полного DATABASE_URL
        self.database_url = os.getenv("DATABASE_URL")

        if not self.database_url:
            # Собираем URL из отдельных компонентов
            self.host = os.getenv("DB_HOST", "localhost")
            self.port = int(os.getenv("DB_PORT", "5432"))
            self.database = os.getenv("DB_NAME", "car_chatbot")
            self.user = os.getenv("DB_USER", "postgres")
            self.password = os.getenv("DB_PASSWORD", "")

            # Экранируем пароль для URL (может быть пустым для локальных подключений)
            escaped_password = quote_plus(self.password) if self.password else ""

            # Формируем sync URL для миграций
            if escaped_password:
                self.database_url = (
                    f"postgresql://{self.user}:{escaped_password}"
                    f"@{self.host}:{self.port}/{self.database}"
                )
            else:
                # Без пароля (для локальных подключений с peer authentication)
                self.database_url = (
                    f"postgresql://{self.user}"
                    f"@{self.host}:{self.port}/{self.database}"
                )

        # Async URL для приложения (asyncpg)
        self.async_database_url = self.database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )

        # Sync URL для Alembic миграций (psycopg2)
        self.sync_database_url = self.database_url.replace(
            "postgresql://", "postgresql+psycopg2://"
        )

        # Настройки SQLAlchemy
        self.echo = os.getenv("DB_ECHO", "false").lower() == "true"
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))


# Создаем глобальный экземпляр конфигурации
config = DatabaseConfig()


# ============================================================================
# SYNC ENGINE (для Alembic миграций и скриптов)
# ============================================================================

sync_engine = create_engine(
    config.sync_database_url,
    echo=config.echo,
    pool_size=config.pool_size,
    max_overflow=config.max_overflow,
    pool_pre_ping=True,  # Проверка соединения перед использованием
)


def get_sync_session() -> Session:
    """
    Получить синхронную сессию БД (для скриптов миграции данных).

    Usage:
        with get_sync_session() as session:
            tenants = session.query(Tenant).all()
    """
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ============================================================================
# ASYNC ENGINE (для приложения)
# ============================================================================

async_engine = create_async_engine(
    config.async_database_url,
    echo=config.echo,
    pool_size=config.pool_size,
    max_overflow=config.max_overflow,
    pool_pre_ping=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncSession:
    """
    Получить асинхронную сессию БД (для использования в боте).

    Usage:
        async with get_async_session() as session:
            result = await session.execute(select(Tenant))
            tenants = result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ============================================================================
# TENANT CONTEXT (для Row-Level Security)
# ============================================================================

class TenantContext:
    """
    Контекст текущего арендатора для изоляции данных.

    Используется для установки tenant_id в сессии PostgreSQL
    для работы Row-Level Security (RLS).
    """

    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id

    def __enter__(self):
        """Устанавливаем текущий tenant_id в сессии PostgreSQL."""
        self.session.execute(
            f"SET LOCAL app.current_tenant_id = {self.tenant_id}"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Сбрасываем tenant_id после завершения."""
        self.session.execute("RESET app.current_tenant_id")


async def set_tenant_context(session: AsyncSession, tenant_id: int):
    """
    Асинхронная версия установки контекста арендатора.

    Usage:
        async with get_async_session() as session:
            await set_tenant_context(session, tenant_id=1)
            # Все запросы будут автоматически фильтроваться по tenant_id
    """
    await session.execute(f"SET LOCAL app.current_tenant_id = {tenant_id}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def check_connection() -> bool:
    """
    Проверить подключение к базе данных.

    Returns:
        True если подключение успешно, False в противном случае
    """
    try:
        async with async_engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


def create_all_tables():
    """
    Создать все таблицы (только для локальной разработки!).

    В production используйте Alembic миграции.
    """
    from database.models import Base

    Base.metadata.create_all(bind=sync_engine)
    print("All tables created successfully!")


def drop_all_tables():
    """
    Удалить все таблицы (ОСТОРОЖНО! Только для разработки).
    """
    from database.models import Base

    Base.metadata.drop_all(bind=sync_engine)
    print("All tables dropped!")


if __name__ == "__main__":
    # Тестирование конфигурации
    print("Database Configuration:")
    print(f"  Host: {config.host if hasattr(config, 'host') else 'from DATABASE_URL'}")
    print(f"  Database: {config.database if hasattr(config, 'database') else 'from DATABASE_URL'}")
    print(f"  Sync URL: {config.sync_database_url}")
    print(f"  Async URL: {config.async_database_url}")
    print(f"  Echo SQL: {config.echo}")
