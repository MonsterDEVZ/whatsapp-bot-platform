#!/usr/bin/env python3
"""
Мастер-скрипт для полного импорта данных.

Выполняет все этапы импорта последовательно:
1. Создание seed data (tenants, categories, options)
2. Извлечение данных из PDF
3. Очистка и нормализация данных
4. Импорт в базу данных

Удобен для первоначальной настройки или полного переимпорта.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

# Добавляем parent directory в Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def run_command(module_name: str, description: str) -> bool:
    """
    Запускает Python модуль и обрабатывает ошибки.

    Args:
        module_name: Имя модуля для импорта
        description: Описание шага для вывода

    Returns:
        True если успешно, False если ошибка
    """
    print("\n" + "=" * 70)
    print(f"▶️  {description}")
    print("=" * 70)

    try:
        # Динамический импорт модуля
        module = __import__(f"scripts.{module_name}", fromlist=['main'])

        # Запускаем main() функцию
        module.main()

        print(f"\n✅ {description} - ЗАВЕРШЕНО\n")
        return True

    except Exception as e:
        print(f"\n❌ {description} - ОШИБКА")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
        return False


def check_prerequisites() -> bool:
    """
    Проверяет выполнение предварительных условий.

    Returns:
        True если все ОК, False если есть проблемы
    """
    print("🔍 Проверка предварительных условий...\n")

    project_root = Path(__file__).parent.parent.parent
    issues = []

    # Проверка 1: PostgreSQL подключение
    try:
        from database.config import DatabaseConfig
        from sqlalchemy import create_engine, text

        db_config = DatabaseConfig()
        engine = create_engine(db_config.sync_database_url, echo=False)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"   ✅ PostgreSQL: {version[:50]}...")

    except Exception as e:
        issues.append(f"Ошибка подключения к PostgreSQL: {e}")

    # Проверка 2: Миграции применены
    try:
        from database.config import DatabaseConfig
        from sqlalchemy import create_engine, text, inspect

        db_config = DatabaseConfig()
        engine = create_engine(db_config.sync_database_url, echo=False)

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        expected_tables = [
            'tenants', 'brands', 'body_types', 'models',
            'product_categories', 'product_options', 'patterns', 'prices'
        ]

        missing_tables = [t for t in expected_tables if t not in tables]

        if missing_tables:
            issues.append(f"Отсутствуют таблицы: {', '.join(missing_tables)}")
            issues.append("Запустите: alembic upgrade head")
        else:
            print(f"   ✅ Миграции: Все таблицы созданы ({len(tables)} таблиц)")

    except Exception as e:
        issues.append(f"Ошибка проверки миграций: {e}")

    # Проверка 3: PDF файл существует
    pdf_path = project_root / "ТЗ" / "БД_машины.pdf"
    if pdf_path.exists():
        size_mb = pdf_path.stat().st_size / 1024 / 1024
        print(f"   ✅ PDF файл: найден ({size_mb:.1f} MB)")
    else:
        issues.append(f"PDF файл не найден: {pdf_path}")

    # Проверка 4: Необходимые пакеты
    required_packages = [
        'sqlalchemy', 'alembic', 'pandas', 'pdfplumber',
        'psycopg2', 'asyncpg', 'pydantic'
    ]

    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        issues.append(f"Отсутствуют пакеты: {', '.join(missing_packages)}")
        issues.append("Установите: pip install -r requirements.txt")
    else:
        print(f"   ✅ Python пакеты: Все установлены ({len(required_packages)} пакетов)")

    # Вывод результатов
    print()

    if issues:
        print("❌ Найдены проблемы:\n")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print("\nУстраните проблемы и запустите скрипт снова.")
        return False

    print("✅ Все проверки пройдены!\n")
    return True


def main():
    """Основная функция."""

    parser = argparse.ArgumentParser(
        description="Полный импорт данных из PDF в базу данных",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Полный импорт для evopoliki
  python scripts/run_full_import.py --tenant evopoliki

  # Полный импорт для five_deluxe
  python scripts/run_full_import.py --tenant five_deluxe

  # Только seed data (без импорта моделей)
  python scripts/run_full_import.py --seed-only

  # Пропустить seed data (если уже создан)
  python scripts/run_full_import.py --skip-seed --tenant evopoliki

  # Пропустить извлечение PDF (если CSV уже есть)
  python scripts/run_full_import.py --skip-extract --tenant evopoliki
        """
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
        "--skip-seed",
        action="store_true",
        help="Пропустить создание seed data"
    )

    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Пропустить извлечение из PDF (использовать существующий CSV)"
    )

    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Пропустить очистку данных (использовать существующий cleaned CSV)"
    )

    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Только создать seed data (без импорта моделей)"
    )

    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Пропустить проверку предварительных условий"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("🚀 ПОЛНЫЙ ИМПОРТ ДАННЫХ В БАЗУ")
    print("=" * 70)
    print(f"\nTenant:   {args.tenant}")
    print(f"Category: {args.category}\n")

    # Проверка предварительных условий
    if not args.no_check:
        if not check_prerequisites():
            sys.exit(1)

    # Сохраняем исходные аргументы sys.argv
    original_argv = sys.argv.copy()

    success = True

    # Этап 1: Seed data
    if not args.skip_seed:
        sys.argv = [original_argv[0]]  # Сбрасываем аргументы
        if not run_command("seed_data", "Этап 1/4: Создание начальных данных (Seed Data)"):
            success = False

        if args.seed_only:
            print("\n" + "=" * 70)
            print("✅ SEED DATA СОЗДАН УСПЕШНО")
            print("=" * 70)
            print("\nДля импорта моделей запустите:")
            print(f"  python scripts/run_full_import.py --skip-seed --tenant {args.tenant}")
            return

    else:
        print("\n⏭️  Пропущено: Создание seed data (--skip-seed)")

    if not success:
        print("\n❌ Остановлено из-за ошибки на предыдущем этапе")
        sys.exit(1)

    # Этап 2: Извлечение из PDF
    if not args.skip_extract:
        sys.argv = [original_argv[0]]
        if not run_command("extract_pdf_data", "Этап 2/4: Извлечение данных из PDF"):
            success = False
    else:
        print("\n⏭️  Пропущено: Извлечение из PDF (--skip-extract)")

    if not success:
        print("\n❌ Остановлено из-за ошибки на предыдущем этапе")
        sys.exit(1)

    # Этап 3: Очистка данных
    if not args.skip_clean:
        sys.argv = [original_argv[0]]
        if not run_command("clean_data", "Этап 3/4: Очистка и нормализация данных"):
            success = False
    else:
        print("\n⏭️  Пропущено: Очистка данных (--skip-clean)")

    if not success:
        print("\n❌ Остановлено из-за ошибки на предыдущем этапе")
        sys.exit(1)

    # Этап 4: Импорт в БД
    sys.argv = [original_argv[0], "--tenant", args.tenant, "--category", args.category]

    if not run_command("import_to_database", f"Этап 4/4: Импорт в базу данных (tenant={args.tenant})"):
        success = False

    # Восстанавливаем sys.argv
    sys.argv = original_argv

    # Итоги
    print("\n" + "=" * 70)
    if success:
        print("🎉 ПОЛНЫЙ ИМПОРТ ЗАВЕРШЕН УСПЕШНО!")
        print("=" * 70)

        print("\n✅ Выполнено:")
        if not args.skip_seed:
            print("   1. ✅ Seed data создан")
        if not args.skip_extract:
            print("   2. ✅ Данные извлечены из PDF")
        if not args.skip_clean:
            print("   3. ✅ Данные очищены и нормализованы")
        print("   4. ✅ Данные импортированы в базу")

        print("\n📊 Проверьте результаты:")
        print("   psql -U postgres -d car_chatbot")
        print("   SELECT COUNT(*) FROM models;")
        print("   SELECT COUNT(*) FROM patterns WHERE tenant_id = (SELECT id FROM tenants WHERE slug = '" + args.tenant + "');")

        print("\n🚀 Следующие шаги:")
        print("   1. Импортируйте данные для второго tenant:")
        print(f"      python scripts/run_full_import.py --skip-seed --skip-extract --skip-clean --tenant five_deluxe")
        print("   2. Создайте API для чат-бота")
        print("   3. Настройте fuzzy search для поиска моделей")

    else:
        print("❌ ИМПОРТ ЗАВЕРШЕН С ОШИБКАМИ")
        print("=" * 70)
        print("\nПроверьте логи выше для деталей ошибок")

    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Импорт прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
