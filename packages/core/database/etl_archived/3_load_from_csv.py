#!/usr/bin/env python3
"""
ETL Pipeline - Step 3: LOAD
============================
Загружает данные из output/patterns_clean.csv в PostgreSQL.
ВАЖНО: Перед загрузкой полностью очищает таблицы patterns, models, brands!

Использование:
    python 3_load_from_csv.py              # Загрузить с подтверждением
    python 3_load_from_csv.py --force      # Загрузить без подтверждения

Результат:
    - Таблицы patterns, models, brands очищены
    - Загружены новые данные из CSV
"""

import sys
import csv
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict

# Добавляем пути
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from models import Brand, Model, ProductCategory, Pattern, Tenant
from config import config as db_config


class DataLoader:
    """Класс для загрузки данных в БД."""

    def __init__(self, session: AsyncSession, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id
        self.brand_cache = {}  # brand_name -> Brand
        self.model_cache = {}  # (brand_id, model_name) -> Model
        self.category_cache = {}  # category_code -> ProductCategory

    async def clear_tables(self):
        """Очищает таблицы patterns, models, brands."""
        print("\n🗑️  ОЧИСТКА ТАБЛИЦ")
        print("=" * 70)

        try:
            # Очищаем в правильном порядке (из-за foreign keys)

            # 1. Patterns
            result = await self.session.execute(
                delete(Pattern).where(Pattern.tenant_id == self.tenant_id)
            )
            patterns_deleted = result.rowcount
            print(f"   ✅ Удалено записей patterns: {patterns_deleted}")

            # 2. Models (удаляем все, так как они общие)
            result = await self.session.execute(delete(Model))
            models_deleted = result.rowcount
            print(f"   ✅ Удалено записей models: {models_deleted}")

            # 3. Brands (удаляем все)
            result = await self.session.execute(delete(Brand))
            brands_deleted = result.rowcount
            print(f"   ✅ Удалено записей brands: {brands_deleted}")

            await self.session.commit()
            print("\n✅ Таблицы очищены")

        except Exception as e:
            print(f"\n❌ Ошибка при очистке таблиц: {e}")
            await self.session.rollback()
            raise

    async def get_or_create_brand(self, brand_name: str) -> Brand:
        """Получает или создает бренд."""
        if brand_name in self.brand_cache:
            return self.brand_cache[brand_name]

        # Ищем в БД
        stmt = select(Brand).where(Brand.name == brand_name)
        result = await self.session.execute(stmt)
        brand = result.scalar_one_or_none()

        if not brand:
            # Создаем новый бренд
            # Генерируем slug из имени (URL-friendly версия)
            slug = brand_name.lower().replace(' ', '-').replace('_', '-')
            brand = Brand(name=brand_name, slug=slug)
            self.session.add(brand)
            await self.session.flush()  # Чтобы получить ID

        self.brand_cache[brand_name] = brand
        return brand

    async def get_or_create_model(self, brand: Brand, model_name: str) -> Model:
        """Получает или создает модель."""
        cache_key = (brand.id, model_name)

        if cache_key in self.model_cache:
            return self.model_cache[cache_key]

        # Ищем в БД
        stmt = select(Model).where(
            Model.brand_id == brand.id,
            Model.name == model_name
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            # Создаем новую модель
            model = Model(
                brand_id=brand.id,
                name=model_name
            )
            self.session.add(model)
            await self.session.flush()  # Чтобы получить ID

        self.model_cache[cache_key] = model
        return model

    async def get_category(self, category_code: str) -> ProductCategory:
        """Получает категорию."""
        if category_code in self.category_cache:
            return self.category_cache[category_code]

        stmt = select(ProductCategory).where(ProductCategory.code == category_code)
        result = await self.session.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            raise ValueError(f"Категория '{category_code}' не найдена в БД!")

        self.category_cache[category_code] = category
        return category

    async def load_patterns(self, patterns_data: List[Dict[str, str]]):
        """Загружает лекала из CSV данных."""
        print("\n📥 ЗАГРУЗКА ДАННЫХ")
        print("=" * 70)

        total = len(patterns_data)
        loaded = 0
        errors = 0

        for i, row in enumerate(patterns_data, 1):
            try:
                # Получаем или создаем бренд
                brand = await self.get_or_create_brand(row['brand'])

                # Получаем или создаем модель
                model = await self.get_or_create_model(brand, row['model'])

                # Получаем категорию
                category = await self.get_category(row.get('category', 'eva_mats'))

                # Создаем pattern
                pattern = Pattern(
                    tenant_id=self.tenant_id,
                    model_id=model.id,
                    category_id=category.id,
                    available=row.get('available', 'true').lower() == 'true'
                )

                self.session.add(pattern)
                loaded += 1

                # Коммитим каждые 100 записей
                if i % 100 == 0:
                    await self.session.commit()
                    print(f"   Загружено: {loaded}/{total} ({loaded/total*100:.1f}%)", end="\r")

            except Exception as e:
                errors += 1
                print(f"\n   ⚠️  Ошибка в строке {i}: {e}")
                continue

        # Финальный коммит
        await self.session.commit()

        print(f"\n\n✅ Загрузка завершена:")
        print(f"   - Успешно: {loaded}")
        print(f"   - Ошибок: {errors}")
        print(f"   - Всего брендов: {len(self.brand_cache)}")
        print(f"   - Всего моделей: {len(self.model_cache)}")


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Загрузка данных из CSV в PostgreSQL"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Загрузить без подтверждения (опасно!)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("📥 ETL PIPELINE - STEP 3: LOAD")
    print("=" * 70)

    # Определяем пути
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    input_path = project_root / "output" / "patterns_clean.csv"

    if not input_path.exists():
        print(f"\n❌ Файл не найден: {input_path}")
        print("Сначала запустите: python 2_transform_to_csv.py")
        sys.exit(1)

    # Читаем CSV
    print(f"\n📖 Чтение: {input_path}")
    patterns_data = []
    with open(input_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        patterns_data = list(reader)

    print(f"   Записей в CSV: {len(patterns_data)}")

    if not patterns_data:
        print("\n⚠️  CSV файл пустой!")
        sys.exit(1)

    # Предупреждение
    if not args.force:
        print("\n" + "⚠️  " * 20)
        print("   ВНИМАНИЕ! Эта операция:")
        print("   1. ПОЛНОСТЬЮ ОЧИСТИТ таблицы patterns, models, brands")
        print("   2. Загрузит новые данные из CSV")
        print("   3. ЭТО НЕОБРАТИМАЯ ОПЕРАЦИЯ!")
        print("⚠️  " * 20 + "\n")

        response = input("Продолжить? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Отменено пользователем.")
            sys.exit(0)

    # Создаем engine и session
    engine = create_async_engine(db_config.async_database_url, echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        try:
            # Получаем tenant
            stmt = select(Tenant).where(Tenant.slug == "evopoliki")
            result = await session.execute(stmt)
            tenant = result.scalar_one_or_none()

            if not tenant:
                print("\n❌ Tenant 'evopoliki' не найден в БД!")
                sys.exit(1)

            print(f"\n✅ Tenant: {tenant.name} (id={tenant.id})")

            # Создаем loader
            loader = DataLoader(session, tenant.id)

            # Очищаем таблицы
            await loader.clear_tables()

            # Загружаем данные
            await loader.load_patterns(patterns_data)

            print("\n" + "=" * 70)
            print("✅ ЗАГРУЗКА ЗАВЕРШЕНА")
            print("=" * 70)
            print("\n🎉 Данные успешно загружены в БД!")
            print("Теперь можно тестировать бот.")

        except Exception as e:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
