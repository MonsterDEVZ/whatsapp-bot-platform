#!/usr/bin/env python3
"""
Скрипт загрузки данных из CSV в PostgreSQL.

Загружает данные о лекалах из CSV файла patterns_clean.csv
в продакшн базу данных PostgreSQL на Railway.

Author: Claude
Date: 2025-10-17
"""

import csv
import os
import sys
from pathlib import Path
from typing import Dict, List, Set
import asyncio

try:
    from slugify import slugify
except ImportError:
    # Fallback: простая функция для создания slug
    def slugify(text: str) -> str:
        return text.lower().replace(" ", "-").replace("_", "-")

# Добавляем путь к корню проекта
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from core.database.models import (
    Base, Brand, Model, Pattern, ProductCategory, Tenant
)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Путь к CSV файлу
CSV_FILE = Path(__file__).parent / "output" / "patterns_clean.csv"

# Категория товара (по умолчанию EVA-коврики)
DEFAULT_CATEGORY_CODE = "eva_mats"

# Настройка базы данных (из переменных окружения)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:stispeCxzTCLVnCvVGfoDFPRlBZlKpaL@gondola.proxy.rlwy.net:54660/railway"
)


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def load_csv_file() -> List[Dict]:
    """
    Загружает данные из CSV файла.

    Returns:
        Список всех записей из CSV
    """
    if not CSV_FILE.exists():
        print(f"❌ ОШИБКА: Файл не найден: {CSV_FILE}")
        return []

    print(f"📂 Загружаю {CSV_FILE.name}...")

    all_data = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_data.append(row)

    print(f"   ✅ Загружено {len(all_data)} записей")
    print(f"\n📊 Всего загружено {len(all_data)} записей\n")

    return all_data


async def clear_database(session: AsyncSession):
    """
    ПОЛНОСТЬЮ ОЧИЩАЕТ все связанные таблицы перед загрузкой.

    Порядок важен из-за внешних ключей:
    1. patterns (зависит от models, categories, tenants)
    2. models (зависит от brands)
    3. brands
    """
    print("🗑️  ОЧИСТКА БАЗЫ ДАННЫХ...")
    print("=" * 60)

    # Удаляем patterns (первыми, так как они зависят от всего)
    result = await session.execute(delete(Pattern))
    print(f"   ✅ Удалено {result.rowcount} записей из patterns")

    # Удаляем models (зависят от brands)
    result = await session.execute(delete(Model))
    print(f"   ✅ Удалено {result.rowcount} записей из models")

    # Удаляем brands (независимые)
    result = await session.execute(delete(Brand))
    print(f"   ✅ Удалено {result.rowcount} записей из brands")

    await session.commit()
    print("   ✅ База данных очищена\n")


async def get_or_create_category(session: AsyncSession) -> ProductCategory:
    """
    Получает категорию EVA-коврики или создает, если не существует.

    Returns:
        ProductCategory для EVA-ковриков
    """
    stmt = select(ProductCategory).where(ProductCategory.code == DEFAULT_CATEGORY_CODE)
    result = await session.execute(stmt)
    category = result.scalar_one_or_none()

    if not category:
        print(f"⚠️  Категория '{DEFAULT_CATEGORY_CODE}' не найдена, создаю...")
        category = ProductCategory(
            code=DEFAULT_CATEGORY_CODE,
            name_ru="EVA-коврики",
            name_kg="EVA-килемчелер",
            sort_order=1,
            active=True
        )
        session.add(category)
        await session.commit()
        await session.refresh(category)
        print(f"   ✅ Создана категория: {category.name_ru} (id={category.id})")

    return category


async def get_tenants(session: AsyncSession) -> List[Tenant]:
    """
    Получает всех активных арендаторов из базы данных.

    Returns:
        Список Tenant объектов
    """
    stmt = select(Tenant).where(Tenant.active == True)
    result = await session.execute(stmt)
    tenants = result.scalars().all()

    print(f"📋 Найдено {len(tenants)} активных арендаторов:")
    for tenant in tenants:
        print(f"   • {tenant.name} (slug: {tenant.slug}, id: {tenant.id})")
    print()

    return list(tenants)


async def load_data_to_database(data: List[Dict], session: AsyncSession):
    """
    Загружает данные из CSV в базу данных с нормализацией.

    Процесс:
    1. Извлекает уникальные brands и создает записи
    2. Для каждой записи создает model
    3. Для каждого tenant создает pattern

    Args:
        data: Список записей из CSV
        session: Сессия базы данных
    """
    print("📥 ЗАГРУЗКА ДАННЫХ В POSTGRESQL...")
    print("=" * 60)

    # Получаем категорию и арендаторов
    category = await get_or_create_category(session)
    tenants = await get_tenants(session)

    if not tenants:
        print("❌ ОШИБКА: В базе нет активных арендаторов!")
        print("   Пожалуйста, создайте хотя бы одного tenant перед загрузкой данных.")
        return

    # Шаг 1: Создаем brands
    print("🏭 ШАГ 1: Создание уникальных марок...")

    # Извлекаем уникальные марки
    unique_brands: Set[str] = set()
    for record in data:
        brand_name = record.get("brand", "").strip()
        if brand_name:
            unique_brands.add(brand_name)

    print(f"   Найдено {len(unique_brands)} уникальных марок")

    # Создаем Brand записи
    brand_map: Dict[str, Brand] = {}

    for brand_name in sorted(unique_brands):
        brand = Brand(
            name=brand_name,
            name_ru=brand_name,
            slug=slugify(brand_name)
        )
        session.add(brand)
        brand_map[brand_name] = brand

    await session.commit()

    # Обновляем brand_map с ID из базы
    for brand_name, brand in brand_map.items():
        await session.refresh(brand)

    print(f"   ✅ Создано {len(brand_map)} марок в таблице brands\n")

    # Шаг 2: Создаем models и patterns
    print("🚗 ШАГ 2: Создание моделей и лекал...")

    models_created = 0
    patterns_created = 0
    errors_count = 0

    # Словарь для отслеживания уже созданных models (чтобы избежать дубликатов)
    # Ключ: (brand_id, model_name)
    model_cache: Dict[tuple, Model] = {}

    for i, record in enumerate(data, 1):
        try:
            brand_name = record.get("brand", "").strip()
            model_name = record.get("model", "").strip()
            available = record.get("available", "true").lower() == "true"

            if not brand_name or not model_name:
                print(f"   ⚠️  Запись {i}/{len(data)}: Пропущена (пустой brand или model)")
                continue

            brand = brand_map.get(brand_name)
            if not brand:
                print(f"   ⚠️  Запись {i}/{len(data)}: Марка не найдена: {brand_name}")
                continue

            # Проверяем, существует ли уже такая модель
            cache_key = (brand.id, model_name)

            if cache_key not in model_cache:
                # Создаем новую Model
                model = Model(
                    brand_id=brand.id,
                    name=model_name,
                    name_ru=model_name,
                    year_from=None,
                    year_to=None,
                    model_metadata=None
                )
                session.add(model)
                models_created += 1

                # Нужно сохранить model, чтобы получить ID для patterns
                await session.flush()

                # Сохраняем в кэш
                model_cache[cache_key] = model
            else:
                # Модель уже существует, используем её
                model = model_cache[cache_key]

            # Создаем Pattern для каждого tenant
            for tenant in tenants:
                # Проверяем, существует ли уже такой pattern
                stmt = select(Pattern).where(
                    Pattern.tenant_id == tenant.id,
                    Pattern.category_id == category.id,
                    Pattern.model_id == model.id
                )
                result = await session.execute(stmt)
                existing_pattern = result.scalar_one_or_none()

                if not existing_pattern:
                    pattern = Pattern(
                        tenant_id=tenant.id,
                        category_id=category.id,
                        model_id=model.id,
                        available=available,
                        notes=None
                    )
                    session.add(pattern)
                    patterns_created += 1

            # Прогресс каждые 50 записей
            if i % 50 == 0:
                print(f"   📊 Обработано {i}/{len(data)} записей...")

        except Exception as e:
            errors_count += 1
            print(f"   ❌ Ошибка при обработке записи {i}/{len(data)}: {e}")
            print(f"      Запись: {record}")
            continue

    await session.commit()

    print(f"\n   ✅ Создано {models_created} моделей в таблице models")
    print(f"   ✅ Создано {patterns_created} лекал в таблице patterns")
    print(f"      ({patterns_created // len(tenants)} лекал на каждого из {len(tenants)} арендаторов)")

    if errors_count > 0:
        print(f"   ⚠️  Пропущено {errors_count} записей из-за ошибок")

    print()


async def verify_data(session: AsyncSession):
    """
    Проверяет корректность загруженных данных.

    Выводит статистику по загруженным данным.
    """
    print("✅ ВЕРИФИКАЦИЯ ЗАГРУЖЕННЫХ ДАННЫХ...")
    print("=" * 60)

    # Считаем brands
    stmt = select(Brand)
    result = await session.execute(stmt)
    brands_count = len(result.scalars().all())
    print(f"   📊 Brands:   {brands_count}")

    # Считаем models
    stmt = select(Model)
    result = await session.execute(stmt)
    models_count = len(result.scalars().all())
    print(f"   📊 Models:   {models_count}")

    # Считаем patterns
    stmt = select(Pattern)
    result = await session.execute(stmt)
    patterns_count = len(result.scalars().all())
    print(f"   📊 Patterns: {patterns_count}")

    # Получаем топ-10 марок по количеству моделей
    print("\n   📈 Топ-10 марок по количеству моделей:")

    stmt = select(Brand).order_by(Brand.name)
    result = await session.execute(stmt)
    brands = result.scalars().all()

    brand_stats = []
    for brand in brands:
        stmt = select(Model).where(Model.brand_id == brand.id)
        result = await session.execute(stmt)
        models = result.scalars().all()
        brand_stats.append((brand.name, len(models)))

    brand_stats.sort(key=lambda x: x[1], reverse=True)

    for i, (brand_name, count) in enumerate(brand_stats[:10], 1):
        print(f"      {i:2d}. {brand_name}: {count} моделей")

    print("\n   ✅ Данные загружены корректно!")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

async def main():
    """
    Главная функция - выполняет полную миграцию данных.
    """
    print("\n" + "=" * 60)
    print("🚀 ЗАГРУЗКА ДАННЫХ: CSV → PostgreSQL")
    print("=" * 60)
    print(f"📍 База данных: {DATABASE_URL.split('@')[1]}")  # Скрываем пароль
    print(f"📂 CSV файл: {CSV_FILE}")
    print("=" * 60 + "\n")

    try:
        # 1. Загружаем данные из CSV
        data = load_csv_file()

        if not data:
            print("❌ ОШИБКА: Нет данных для загрузки!")
            return

        # 2. Подключаемся к базе данных
        async with async_session_maker() as session:
            # 3. Очищаем базу данных
            await clear_database(session)

            # 4. Загружаем данные
            await load_data_to_database(data, session)

            # 5. Верифицируем результат
            await verify_data(session)

        print("\n" + "=" * 60)
        print("✅ ЗАГРУЗКА ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 60)
        print("\n💡 Следующие шаги:")
        print("   1. Проверить количество марок в базе: SELECT COUNT(*) FROM brands;")
        print("   2. Проверить пагинацию в боте (должно быть больше страниц)")
        print("   3. Убедиться, что все данные доступны пользователям\n")

    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
