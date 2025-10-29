#!/usr/bin/env python3
"""
Скрипт для создания начальных данных (seed data) в базе данных.

Создает:
- Tenants (арендаторы): evopoliki, five_deluxe
- ProductCategories (категории продуктов)
- ProductOptions (опции продуктов)
- BotTexts (тексты бота для каждого tenant)
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Добавляем parent directory в Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from database.models import Base, Tenant, ProductCategory, ProductOption, BotText
    from database.config import DatabaseConfig
except ImportError as e:
    print(f"❌ Ошибка импорта моделей: {e}")
    print("Убедитесь, что вы запускаете скрипт из корня проекта")
    sys.exit(1)


def create_tenants(session: Session) -> dict[str, int]:
    """
    Создает записи арендаторов.

    Returns:
        Словарь {slug: tenant_id}
    """
    print("\n🏢 Создание арендаторов...")

    tenants_data = [
        {
            "slug": "evopoliki",
            "name": "EVOPOLIKI",
            "contacts": {
                "phone": "+996 555 123 456",
                "telegram": "@evopoliki",
                "instagram": "@evopoliki"
            },
            "settings": {
                "language": "ru",
                "currency": "KGS",
                "timezone": "Asia/Bishkek"
            }
        },
        {
            "slug": "five_deluxe",
            "name": "5Deluxe",
            "contacts": {
                "phone": "+996 555 789 012",
                "telegram": "@5deluxe",
                "instagram": "@5deluxe"
            },
            "settings": {
                "language": "ru",
                "currency": "KGS",
                "timezone": "Asia/Bishkek"
            }
        }
    ]

    tenant_map = {}

    for data in tenants_data:
        # Проверяем существование
        stmt = select(Tenant).where(Tenant.slug == data["slug"])
        existing = session.scalar(stmt)

        if existing:
            print(f"   ⚠️  Tenant '{data['slug']}' уже существует (ID: {existing.id})")
            tenant_map[data["slug"]] = existing.id
            continue

        # Создаем нового
        tenant = Tenant(**data)
        session.add(tenant)
        session.flush()

        tenant_map[data["slug"]] = tenant.id
        print(f"   ✅ Создан tenant: {data['name']} (ID: {tenant.id})")

    session.commit()
    print(f"   Всего арендаторов: {len(tenant_map)}")

    return tenant_map


def create_product_categories(session: Session) -> dict[str, int]:
    """
    Создает категории продуктов.

    Returns:
        Словарь {slug: category_id}
    """
    print("\n📦 Создание категорий продуктов...")

    categories_data = [
        {
            "code": "eva_mats",
            "name_ru": "EVA коврики",
            "description_ru": "Автомобильные EVA коврики премиум класса"
        },
        {
            "code": "seat_covers",
            "name_ru": "Чехлы из экокожи",
            "description_ru": "Чехлы на сиденья из экокожи"
        },
        {
            "code": "5d_mats",
            "name_ru": "5D коврики",
            "description_ru": "Объемные 5D коврики"
        },
        {
            "code": "trunk_mats",
            "name_ru": "Коврики в багажник",
            "description_ru": "Защитные коврики для багажника"
        }
    ]

    category_map = {}

    for data in categories_data:
        # Проверяем существование
        stmt = select(ProductCategory).where(ProductCategory.code == data["code"])
        existing = session.scalar(stmt)

        if existing:
            print(f"   ⚠️  Категория '{data['code']}' уже существует (ID: {existing.id})")
            category_map[data["code"]] = existing.id
            continue

        # Создаем новую
        category = ProductCategory(**data)
        session.add(category)
        session.flush()

        category_map[data["code"]] = category.id
        print(f"   ✅ Создана категория: {data['name_ru']} (ID: {category.id})")

    session.commit()
    print(f"   Всего категорий: {len(category_map)}")

    return category_map


def create_product_options(session: Session, category_map: dict[str, int]) -> int:
    """
    Создает опции продуктов.

    Args:
        category_map: Маппинг категорий

    Returns:
        Количество созданных опций
    """
    print("\n⚙️  Создание опций продуктов...")

    options_data = [
        # Опции для EVA ковриков
        {
            "category_id": category_map.get("eva_mats"),
            "slug": "with_borders",
            "name": "С бортами",
            "description": "EVA коврики с высокими бортами"
        },
        {
            "category_id": category_map.get("eva_mats"),
            "slug": "third_row",
            "name": "3-й ряд",
            "description": "Дополнительный комплект для 3-го ряда сидений"
        },
        {
            "category_id": category_map.get("eva_mats"),
            "slug": "tunnel",
            "name": "Перемычка (тоннель)",
            "description": "Дополнительная перемычка на центральный тоннель"
        },
        # Опции для чехлов
        {
            "category_id": category_map.get("seat_covers"),
            "slug": "eco_leather_standard",
            "name": "Экокожа стандарт",
            "description": "Стандартная экокожа"
        },
        {
            "category_id": category_map.get("seat_covers"),
            "slug": "eco_leather_premium",
            "name": "Экокожа премиум",
            "description": "Премиальная экокожа с улучшенными характеристиками"
        },
        {
            "category_id": category_map.get("seat_covers"),
            "slug": "perforated",
            "name": "Перфорация",
            "description": "Чехлы с перфорацией для лучшей вентиляции"
        },
        {
            "category_id": category_map.get("seat_covers"),
            "slug": "heating",
            "name": "С подогревом",
            "description": "Встроенный подогрев сидений"
        },
        # Опции для 5D ковриков
        {
            "category_id": category_map.get("5d_mats"),
            "slug": "beige_color",
            "name": "Цвет: бежевый",
            "description": "5D коврики бежевого цвета"
        },
        {
            "category_id": category_map.get("5d_mats"),
            "slug": "black_color",
            "name": "Цвет: черный",
            "description": "5D коврики черного цвета"
        },
        {
            "category_id": category_map.get("5d_mats"),
            "slug": "gray_color",
            "name": "Цвет: серый",
            "description": "5D коврики серого цвета"
        },
    ]

    created = 0

    for data in options_data:
        # Пропускаем если категория не найдена
        if not data["category_id"]:
            continue

        # Проверяем существование
        stmt = select(ProductOption).where(
            ProductOption.category_id == data["category_id"],
            ProductOption.slug == data["slug"]
        )
        existing = session.scalar(stmt)

        if existing:
            print(f"   ⚠️  Опция '{data['slug']}' уже существует")
            continue

        # Создаем новую
        option = ProductOption(**data)
        session.add(option)
        created += 1

    session.commit()
    print(f"   ✅ Создано опций: {created}")

    return created


def create_bot_texts(session: Session, tenant_map: dict[str, int]) -> int:
    """
    Создает тексты бота для каждого tenant.

    Args:
        tenant_map: Маппинг арендаторов

    Returns:
        Количество созданных текстов
    """
    print("\n💬 Создание текстов бота...")

    # Тексты для EVOPOLIKI
    evopoliki_texts = [
        {
            "tenant_id": tenant_map.get("evopoliki"),
            "key": "welcome",
            "language": "ru",
            "text": "Добро пожаловать в EVOPOLIKI! 🚗\n\nМы специализируемся на производстве премиальных EVA ковриков и чехлов из экокожи для вашего автомобиля.\n\nЧем могу помочь?"
        },
        {
            "tenant_id": tenant_map.get("evopoliki"),
            "key": "ask_brand",
            "language": "ru",
            "text": "Укажите марку вашего автомобиля:"
        },
        {
            "tenant_id": tenant_map.get("evopoliki"),
            "key": "ask_model",
            "language": "ru",
            "text": "Выберите модель:"
        },
        {
            "tenant_id": tenant_map.get("evopoliki"),
            "key": "ask_year",
            "language": "ru",
            "text": "Укажите год выпуска:"
        },
        {
            "tenant_id": tenant_map.get("evopoliki"),
            "key": "pattern_available",
            "language": "ru",
            "text": "✅ Отлично! Лекало на вашу модель есть в наличии.\n\nВыберите категорию продукта:"
        },
        {
            "tenant_id": tenant_map.get("evopoliki"),
            "key": "pattern_not_available",
            "language": "ru",
            "text": "❌ К сожалению, лекало на вашу модель пока отсутствует.\n\nОставьте ваши контакты, и мы свяжемся с вами, когда лекало появится."
        },
    ]

    # Тексты для 5Deluxe
    five_deluxe_texts = [
        {
            "tenant_id": tenant_map.get("five_deluxe"),
            "key": "welcome",
            "language": "ru",
            "text": "Добро пожаловать в 5Deluxe! 🌟\n\nПремиум аксессуары для вашего автомобиля:\n• EVA коврики\n• 5D коврики\n• Чехлы из экокожи\n\nНачнем подбор?"
        },
        {
            "tenant_id": tenant_map.get("five_deluxe"),
            "key": "ask_brand",
            "language": "ru",
            "text": "Какой у вас автомобиль? Укажите марку:"
        },
        {
            "tenant_id": tenant_map.get("five_deluxe"),
            "key": "ask_model",
            "language": "ru",
            "text": "Отлично! Теперь выберите модель:"
        },
    ]

    created = 0

    for texts_list in [evopoliki_texts, five_deluxe_texts]:
        for data in texts_list:
            # Пропускаем если tenant не найден
            if not data["tenant_id"]:
                continue

            # Проверяем существование
            stmt = select(BotText).where(
                BotText.tenant_id == data["tenant_id"],
                BotText.key == data["key"],
                BotText.language == data["language"]
            )
            existing = session.scalar(stmt)

            if existing:
                continue

            # Создаем новый
            bot_text = BotText(**data)
            session.add(bot_text)
            created += 1

    session.commit()
    print(f"   ✅ Создано текстов: {created}")

    return created


def main():
    """Основная функция."""

    print("=" * 60)
    print("🌱 СОЗДАНИЕ НАЧАЛЬНЫХ ДАННЫХ (SEED DATA)")
    print("=" * 60)

    # Создаем подключение к БД
    db_config = DatabaseConfig()
    engine = create_engine(db_config.sync_database_url, echo=False)

    print(f"\n🔗 Подключение к БД: {db_config.host}:{db_config.port}/{db_config.database}")

    # Проверяем подключение
    try:
        with engine.connect() as conn:
            print("   ✅ Подключение успешно")
    except Exception as e:
        print(f"   ❌ Ошибка подключения: {e}")
        print("\nПроверьте:")
        print("1. PostgreSQL запущен")
        print("2. База данных создана")
        print("3. Переменные окружения в .env корректны")
        print("4. Миграции применены (alembic upgrade head)")
        sys.exit(1)

    with Session(engine) as session:
        # Создаем арендаторов
        tenant_map = create_tenants(session)

        # Создаем категории продуктов
        category_map = create_product_categories(session)

        # Создаем опции продуктов
        # TODO: Исправить структуру данных под новую схему (code, name_ru)
        # options_count = create_product_options(session, category_map)
        options_count = 0

        # Создаем тексты бота
        # TODO: Исправить структуру данных под новую схему
        # texts_count = create_bot_texts(session, tenant_map)
        texts_count = 0

    print("\n" + "=" * 60)
    print("✅ SEED DATA СОЗДАН УСПЕШНО")
    print("=" * 60)

    print(f"\n📊 Итого:")
    print(f"   Арендаторов:        {len(tenant_map)}")
    print(f"   Категорий:          {len(category_map)}")
    print(f"   Опций:              {options_count}")
    print(f"   Текстов бота:       {texts_count}")

    print(f"\nТеперь можно импортировать данные о моделях:")
    print(f"  python scripts/import_to_database.py --tenant evopoliki")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
