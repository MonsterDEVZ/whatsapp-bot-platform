#!/usr/bin/env python3
"""
Скрипт для очистки данных в таблице models.
Удаляет название бренда из названия модели, если оно там дублируется.

Пример: "Kia РИО" -> "РИО"

Использование:
    python cleanup_models.py --dry-run    # Показывает изменения без применения
    python cleanup_models.py              # Применяет изменения
"""

import sys
import asyncio
import argparse
from pathlib import Path
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Добавляем пути
sys.path.insert(0, str(Path(__file__).parent))

from models import Brand, Model
from config import config as db_config


async def find_models_with_brand_prefix(session: AsyncSession):
    """
    Находит все модели, в названии которых есть префикс с названием бренда.

    Returns:
        list: Список кортежей (brand, model, cleaned_name)
    """
    # Получаем все бренды
    brands_stmt = select(Brand)
    brands_result = await session.execute(brands_stmt)
    brands = brands_result.scalars().all()

    models_to_clean = []

    for brand in brands:
        # Ищем модели этого бренда
        models_stmt = select(Model).where(Model.brand_id == brand.id)
        models_result = await session.execute(models_stmt)
        models = models_result.scalars().all()

        for model in models:
            # Проверяем разные варианты префикса
            prefixes_to_check = [
                f"{brand.name} ",     # "Toyota Camry"
                f"{brand.name}-",     # "Toyota-Camry"
                f"{brand.name}_",     # "Toyota_Camry"
            ]

            for prefix in prefixes_to_check:
                if model.name.startswith(prefix):
                    cleaned_name = model.name[len(prefix):].strip()
                    if cleaned_name:  # Проверяем, что после удаления префикса осталось что-то
                        models_to_clean.append((brand, model, cleaned_name))
                    break

    return models_to_clean


async def cleanup_models(dry_run: bool = True):
    """
    Очищает названия моделей от префиксов с названием бренда.

    Args:
        dry_run: Если True, только показывает изменения без применения
    """
    # Создаем engine и session
    engine = create_async_engine(db_config.async_database_url, echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        try:
            print("=" * 70)
            print("🔍 ПОИСК МОДЕЛЕЙ С ПРЕФИКСОМ БРЕНДА")
            print("=" * 70)

            models_to_clean = await find_models_with_brand_prefix(session)

            if not models_to_clean:
                print("\n✅ Все названия моделей корректны! Очистка не требуется.")
                return

            print(f"\n📊 Найдено {len(models_to_clean)} моделей для очистки:\n")

            # Группируем по брендам для лучшей читаемости
            models_by_brand = {}
            for brand, model, cleaned_name in models_to_clean:
                if brand.name not in models_by_brand:
                    models_by_brand[brand.name] = []
                models_by_brand[brand.name].append((model, cleaned_name))

            # Показываем изменения
            for brand_name in sorted(models_by_brand.keys()):
                print(f"\n🚗 Бренд: {brand_name}")
                for model, cleaned_name in models_by_brand[brand_name]:
                    print(f"   ❌ '{model.name}' → ✅ '{cleaned_name}' (id={model.id})")

            if dry_run:
                print("\n" + "=" * 70)
                print("⚠️  РЕЖИМ СИМУЛЯЦИИ (dry-run)")
                print("   Изменения НЕ были применены к базе данных.")
                print("   Чтобы применить изменения, запустите без флага --dry-run")
                print("=" * 70)
                return

            # Применяем изменения
            print("\n" + "=" * 70)
            print("✏️  ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ")
            print("=" * 70)

            updated_count = 0
            for brand, model, cleaned_name in models_to_clean:
                try:
                    # Обновляем модель
                    stmt = (
                        update(Model)
                        .where(Model.id == model.id)
                        .values(name=cleaned_name)
                    )
                    await session.execute(stmt)
                    updated_count += 1
                    print(f"✅ Обновлено: {brand.name} '{model.name}' → '{cleaned_name}'")
                except Exception as e:
                    print(f"❌ Ошибка обновления модели id={model.id}: {e}")

            # Коммитим изменения
            await session.commit()

            print("\n" + "=" * 70)
            print(f"✅ УСПЕШНО ОБНОВЛЕНО: {updated_count} из {len(models_to_clean)} моделей")
            print("=" * 70)

        except Exception as e:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Очистка названий моделей от префиксов с названием бренда"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Показать изменения без применения (режим симуляции)'
    )

    args = parser.parse_args()

    if args.dry_run:
        print("\n🔍 Запуск в режиме СИМУЛЯЦИИ (dry-run)...")
        print("   Изменения будут показаны, но НЕ применены к базе данных.\n")
    else:
        print("\n⚠️  Запуск в режиме ПРИМЕНЕНИЯ изменений...")
        print("   Изменения будут применены к базе данных!\n")

        # Запрашиваем подтверждение
        response = input("Продолжить? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Отменено пользователем.")
            return

    await cleanup_models(dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
