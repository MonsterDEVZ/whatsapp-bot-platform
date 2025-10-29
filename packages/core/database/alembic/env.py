"""
Alembic environment configuration.

Этот модуль настраивает Alembic для работы с нашей базой данных.
Поддерживает как online (подключение к БД), так и offline (SQL скрипт) миграции.

Author: Claude
Date: 2025-01-09
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Добавляем parent directory в PYTHONPATH для импорта наших модулей
# Поднимаемся на 2 уровня вверх от alembic/env.py к корню проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Загружаем переменные окружения из .env файла
from dotenv import load_dotenv
load_dotenv()

# Импортируем нашу конфигурацию БД и модели
from database.config import config as db_config
from database.models import Base

# Alembic Config object
config = context.config

# Устанавливаем sqlalchemy.url из нашей конфигурации
config.set_main_option("sqlalchemy.url", db_config.sync_database_url)

# Интерпретация конфигурационного файла для логирования
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные для автогенерации миграций
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Генерирует SQL скрипт без подключения к БД.
    Полезно для ревью миграций или применения на production вручную.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Настройки для корректной генерации DDL
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Подключается к БД и применяет миграции напрямую.
    Стандартный режим для локальной разработки.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Настройки для автогенерации
            compare_type=True,              # Сравнивать типы колонок
            compare_server_default=True,    # Сравнивать server defaults
            include_schemas=False,          # Не включать другие схемы
            # Опции для PostgreSQL
            render_as_batch=False,          # Batch mode не нужен для PostgreSQL
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
