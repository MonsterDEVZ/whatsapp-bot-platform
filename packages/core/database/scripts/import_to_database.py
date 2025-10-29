#!/usr/bin/env python3
"""
Скрипт для импорта очищенных данных о моделях в базу данных.

Импортирует данные из cleaned_vehicle_data.csv в PostgreSQL:
- Бренды (brands)
- Типы кузова (body_types)
- Модели (models)
- Лекала (patterns)
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Добавляем parent directory в Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from database.models import Base, Brand, BodyType, Model, Tenant, ProductCategory, Pattern
    from database.config import DatabaseConfig
except ImportError as e:
    print(f"❌ Ошибка импорта моделей: {e}")
    print("Убедитесь, что вы запускаете скрипт из корня проекта")
    sys.exit(1)


def get_or_create_brand(session: Session, name: str) -> Brand:
    """
    Получает существующий бренд или создает новый.

    Args:
        session: Сессия БД
        name: Название бренда

    Returns:
        Объект Brand
    """
    # Ищем существующий
    stmt = select(Brand).where(Brand.name == name)
    brand = session.scalar(stmt)

    if brand:
        return brand

    # Создаем новый
    brand = Brand(name=name)
    session.add(brand)
    session.flush()  # Получаем ID

    return brand


def get_or_create_body_type(session: Session, slug: str, name: str) -> BodyType:
    """
    Получает существующий тип кузова или создает новый.

    Args:
        session: Сессия БД
        slug: Slug типа кузова
        name: Название типа кузова

    Returns:
        Объект BodyType
    """
    # Ищем существующий
    stmt = select(BodyType).where(BodyType.slug == slug)
    body_type = session.scalar(stmt)

    if body_type:
        return body_type

    # Создаем новый
    body_type = BodyType(slug=slug, name=name)
    session.add(body_type)
    session.flush()

    return body_type


def import_brands(df: pd.DataFrame, session: Session) -> Dict[str, int]:
    """
    Импортирует уникальные бренды из DataFrame.

    Args:
        df: DataFrame с данными
        session: Сессия БД

    Returns:
        Словарь {название_бренда: brand_id}
    """
    print("\n🏢 Импорт брендов...")

    unique_brands = df['brand'].dropna().unique()
    print(f"   Уникальных брендов: {len(unique_brands)}")

    brand_map = {}

    for brand_name in sorted(unique_brands):
        brand = get_or_create_brand(session, brand_name)
        brand_map[brand_name] = brand.id

    session.commit()
    print(f"   ✅ Импортировано брендов: {len(brand_map)}")

    return brand_map


def import_body_types(session: Session) -> Dict[Optional[str], int]:
    """
    Импортирует стандартные типы кузова.

    Args:
        session: Сессия БД

    Returns:
        Словарь {slug: body_type_id}
    """
    print("\n🚙 Импорт типов кузова...")

    body_types_data = [
        ("sedan", "Седан"),
        ("suv", "Внедорожник/Кроссовер"),
        ("minivan", "Минивэн"),
        ("hatchback", "Хэтчбек"),
        ("wagon", "Универсал"),
        ("coupe", "Купе"),
        ("convertible", "Кабриолет"),
        ("pickup", "Пикап"),
        ("unknown", "Неизвестно"),
    ]

    body_type_map = {}

    for slug, name in body_types_data:
        body_type = get_or_create_body_type(session, slug, name)
        body_type_map[slug] = body_type.id

    # Добавляем None -> unknown для моделей без типа кузова
    body_type_map[None] = body_type_map["unknown"]

    session.commit()
    print(f"   ✅ Импортировано типов кузова: {len(body_types_data)}")

    return body_type_map


def import_models(
    df: pd.DataFrame,
    session: Session,
    brand_map: Dict[str, int],
    body_type_map: Dict[Optional[str], int]
) -> Dict[tuple, int]:
    """
    Импортирует модели автомобилей.

    Args:
        df: DataFrame с данными
        session: Сессия БД
        brand_map: Маппинг брендов
        body_type_map: Маппинг типов кузова

    Returns:
        Словарь {(brand, model, year_from, year_to): model_id}
    """
    print("\n🚗 Импорт моделей...")

    model_map = {}
    imported = 0
    skipped = 0

    for idx, row in df.iterrows():
        brand_name = row['brand']
        model_name = row['model']
        year_from = int(row['year_from']) if pd.notna(row['year_from']) else None
        year_to = int(row['year_to']) if pd.notna(row['year_to']) else None
        body_type_slug = row['body_type'] if pd.notna(row['body_type']) else None

        # Пропускаем некорректные записи
        if pd.isna(brand_name) or pd.isna(model_name):
            skipped += 1
            continue

        # Получаем ID бренда и типа кузова
        brand_id = brand_map.get(brand_name)
        body_type_id = body_type_map.get(body_type_slug)

        if not brand_id:
            print(f"   ⚠️  Бренд не найден: {brand_name}")
            skipped += 1
            continue

        # Создаем модель
        try:
            model = Model(
                brand_id=brand_id,
                name=model_name,
                year_from=year_from,
                year_to=year_to,
                body_type_id=body_type_id
            )
            session.add(model)
            session.flush()

            # Сохраняем в маппинг
            key = (brand_name, model_name, year_from, year_to)
            model_map[key] = model.id

            imported += 1

            # Прогресс каждые 100 записей
            if imported % 100 == 0:
                print(f"   Импортировано: {imported}...", end='\r')

        except IntegrityError:
            session.rollback()
            # Модель уже существует, получаем её ID
            stmt = select(Model).where(
                Model.brand_id == brand_id,
                Model.name == model_name,
                Model.year_from == year_from,
                Model.year_to == year_to
            )
            existing_model = session.scalar(stmt)
            if existing_model:
                key = (brand_name, model_name, year_from, year_to)
                model_map[key] = existing_model.id
            skipped += 1

    session.commit()
    print(f"\n   ✅ Импортировано моделей: {imported}")
    if skipped > 0:
        print(f"   ⚠️  Пропущено записей: {skipped}")

    return model_map


def import_patterns(
    df: pd.DataFrame,
    session: Session,
    tenant_slug: str,
    category_slug: str,
    model_map: Dict[tuple, int]
) -> int:
    """
    Импортирует лекала (patterns) для моделей.

    Args:
        df: DataFrame с данными
        session: Сессия БД
        tenant_slug: Slug арендатора
        category_slug: Slug категории продукта
        model_map: Маппинг моделей

    Returns:
        Количество импортированных лекал
    """
    print(f"\n📐 Импорт лекал для tenant={tenant_slug}, category={category_slug}...")

    # Получаем tenant
    stmt = select(Tenant).where(Tenant.slug == tenant_slug)
    tenant = session.scalar(stmt)

    if not tenant:
        print(f"   ❌ Ошибка: Tenant '{tenant_slug}' не найден")
        print("   Сначала запустите: python scripts/seed_data.py")
        return 0

    # Получаем категорию
    stmt = select(ProductCategory).where(ProductCategory.slug == category_slug)
    category = session.scalar(stmt)

    if not category:
        print(f"   ❌ Ошибка: Категория '{category_slug}' не найдена")
        print("   Сначала запустите: python scripts/seed_data.py")
        return 0

    imported = 0
    skipped = 0

    for idx, row in df.iterrows():
        brand_name = row['brand']
        model_name = row['model']
        year_from = int(row['year_from']) if pd.notna(row['year_from']) else None
        year_to = int(row['year_to']) if pd.notna(row['year_to']) else None

        # Пропускаем некорректные записи
        if pd.isna(brand_name) or pd.isna(model_name):
            skipped += 1
            continue

        # Получаем ID модели
        key = (brand_name, model_name, year_from, year_to)
        model_id = model_map.get(key)

        if not model_id:
            skipped += 1
            continue

        # Создаем лекало
        try:
            pattern = Pattern(
                tenant_id=tenant.id,
                category_id=category.id,
                model_id=model_id,
                available=True,
                notes=f"Импортировано из БД_машины.pdf"
            )
            session.add(pattern)
            imported += 1

            # Прогресс каждые 100 записей
            if imported % 100 == 0:
                print(f"   Импортировано: {imported}...", end='\r')

        except IntegrityError:
            session.rollback()
            skipped += 1

    session.commit()
    print(f"\n   ✅ Импортировано лекал: {imported}")
    if skipped > 0:
        print(f"   ⚠️  Пропущено записей: {skipped}")

    return imported


def run_full_import(csv_path: str, tenant_slug: str, category_slug: str = "eva_mats"):
    """
    Выполняет полный импорт данных.

    Args:
        csv_path: Путь к CSV файлу с очищенными данными
        tenant_slug: Slug арендатора
        category_slug: Slug категории продукта
    """
    print("=" * 60)
    print("📥 ИМПОРТ ДАННЫХ В БАЗУ")
    print("=" * 60)

    print(f"\n📂 Загрузка данных из: {csv_path}")

    # Загружаем данные
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    print(f"   Загружено записей: {len(df)}")

    # Создаем подключение к БД
    db_config = DatabaseConfig()
    engine = create_engine(db_config.sync_database_url, echo=False)

    print(f"\n🔗 Подключение к БД: {db_config.host}:{db_config.port}/{db_config.database}")

    with Session(engine) as session:
        # Этап 1: Импорт брендов
        brand_map = import_brands(df, session)

        # Этап 2: Импорт типов кузова
        body_type_map = import_body_types(session)

        # Этап 3: Импорт моделей
        model_map = import_models(df, session, brand_map, body_type_map)

        # Этап 4: Импорт лекал
        patterns_count = import_patterns(df, session, tenant_slug, category_slug, model_map)

    print("\n" + "=" * 60)
    print("✅ ИМПОРТ ЗАВЕРШЕН УСПЕШНО")
    print("=" * 60)

    print(f"\n📊 Итоговая статистика:")
    print(f"   Брендов:       {len(brand_map)}")
    print(f"   Типов кузова:  {len(body_type_map) - 1}")  # -1 для None
    print(f"   Моделей:       {len(model_map)}")
    print(f"   Лекал:         {patterns_count}")


def main():
    """Основная функция."""

    parser = argparse.ArgumentParser(
        description="Импорт данных о моделях автомобилей в базу данных"
    )
    parser.add_argument(
        "--tenant",
        type=str,
        default="evopoliki",
        help="Slug арендатора (по умолчанию: evopoliki)"
    )
    parser.add_argument(
        "--category",
        type=str,
        default="eva_mats",
        help="Slug категории продукта (по умолчанию: eva_mats)"
    )
    parser.add_argument(
        "--csv",
        type=str,
        help="Путь к CSV файлу (опционально)"
    )

    args = parser.parse_args()

    # Определяем путь к CSV
    if args.csv:
        csv_path = Path(args.csv)
    else:
        project_root = Path(__file__).parent.parent.parent
        csv_path = project_root / "database" / "data" / "cleaned_vehicle_data.csv"

    # Проверяем наличие файла
    if not csv_path.exists():
        print(f"\n❌ Ошибка: CSV файл не найден")
        print(f"   Ожидаемый путь: {csv_path}")
        print(f"\nСначала запустите: python scripts/clean_data.py")
        sys.exit(1)

    try:
        run_full_import(str(csv_path), args.tenant, args.category)

    except Exception as e:
        print(f"\n❌ Ошибка при импорте: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
