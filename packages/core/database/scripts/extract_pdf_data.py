#!/usr/bin/env python3
"""
Скрипт для извлечения данных о моделях автомобилей из PDF файла.

Извлекает данные из БД_машины.pdf и сохраняет в CSV формате.
Использует pdfplumber для парсинга таблиц.
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

# Добавляем parent directory в Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import pdfplumber
except ImportError:
    print("❌ Ошибка: pdfplumber не установлен")
    print("Установите: pip install pdfplumber")
    sys.exit(1)


def extract_tables_from_pdf(pdf_path: str) -> pd.DataFrame:
    """
    Извлекает все таблицы из PDF файла.

    Args:
        pdf_path: Путь к PDF файлу

    Returns:
        DataFrame со всеми извлеченными данными
    """
    all_data: List[Dict[str, Any]] = []

    print(f"📄 Открываю PDF файл: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"📊 Всего страниц: {total_pages}")

        for page_num, page in enumerate(pdf.pages, start=1):
            print(f"  Обработка страницы {page_num}/{total_pages}...", end="\r")

            # Извлекаем таблицу со страницы
            table = page.extract_table()

            if not table:
                continue

            # Пропускаем заголовок на первой странице
            start_row = 1 if page_num == 1 else 0

            for row in table[start_row:]:
                # Пропускаем пустые строки и строки-заголовки
                if not row or not row[0] or row[0].strip().lower() in ['№', 'п/п', '']:
                    continue

                # Очищаем данные от None и лишних пробелов
                cleaned_row = [cell.strip() if cell else '' for cell in row]

                # Пропускаем строки без модели
                if len(cleaned_row) < 3 or not cleaned_row[2]:
                    continue

                # Формируем запись
                record = {
                    'id': cleaned_row[0] if len(cleaned_row) > 0 else '',
                    'brand': cleaned_row[1] if len(cleaned_row) > 1 else '',
                    'model': cleaned_row[2] if len(cleaned_row) > 2 else '',
                    'year': cleaned_row[3] if len(cleaned_row) > 3 else '',
                    'description': cleaned_row[4] if len(cleaned_row) > 4 else ''
                }

                all_data.append(record)

        print()  # Новая строка после прогресса

    df = pd.DataFrame(all_data)
    print(f"✅ Извлечено записей: {len(df)}")

    return df


def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Базовая валидация извлеченных данных.

    Args:
        df: DataFrame с данными

    Returns:
        Очищенный DataFrame
    """
    print("\n🔍 Валидация данных...")

    initial_count = len(df)

    # Удаляем полностью пустые строки
    df = df.dropna(how='all')

    # Удаляем дубликаты
    duplicates = df.duplicated(subset=['brand', 'model', 'year'], keep='first').sum()
    if duplicates > 0:
        print(f"  ⚠️  Найдено дубликатов: {duplicates}")
        df = df.drop_duplicates(subset=['brand', 'model', 'year'], keep='first')

    # Удаляем записи без модели
    df = df[df['model'].str.strip() != '']

    # Статистика по брендам
    brands_count = df['brand'].nunique()
    print(f"  📊 Уникальных брендов: {brands_count}")

    # Топ-5 брендов по количеству моделей
    top_brands = df['brand'].value_counts().head(5)
    print("\n  🏆 Топ-5 брендов:")
    for brand, count in top_brands.items():
        print(f"     {brand}: {count} моделей")

    removed = initial_count - len(df)
    if removed > 0:
        print(f"\n  🗑️  Удалено некорректных записей: {removed}")

    print(f"  ✅ Осталось записей: {len(df)}")

    return df


def save_to_csv(df: pd.DataFrame, output_path: str) -> None:
    """
    Сохраняет DataFrame в CSV файл.

    Args:
        df: DataFrame с данными
        output_path: Путь для сохранения CSV
    """
    # Создаем директорию если не существует
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Сохраняем с UTF-8 BOM для правильного отображения в Excel
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n💾 Данные сохранены: {output_path}")
    print(f"   Размер файла: {os.path.getsize(output_path) / 1024:.1f} KB")


def main():
    """Основная функция."""

    print("=" * 60)
    print("🚗 ИЗВЛЕЧЕНИЕ ДАННЫХ О МОДЕЛЯХ АВТОМОБИЛЕЙ ИЗ PDF")
    print("=" * 60)

    # Определяем пути
    project_root = Path(__file__).parent.parent.parent
    pdf_path = project_root / "ТЗ" / "БД_машины.pdf"
    output_path = project_root / "database" / "data" / "raw_vehicle_data.csv"

    # Проверяем наличие PDF файла
    if not pdf_path.exists():
        print(f"\n❌ Ошибка: PDF файл не найден")
        print(f"   Ожидаемый путь: {pdf_path}")
        sys.exit(1)

    try:
        # Извлекаем данные
        df = extract_tables_from_pdf(str(pdf_path))

        if df.empty:
            print("\n❌ Ошибка: Не удалось извлечь данные из PDF")
            sys.exit(1)

        # Валидируем
        df = validate_data(df)

        # Сохраняем
        save_to_csv(df, str(output_path))

        print("\n" + "=" * 60)
        print("✅ ИЗВЛЕЧЕНИЕ ЗАВЕРШЕНО УСПЕШНО")
        print("=" * 60)
        print(f"\nСледующий шаг: python scripts/clean_data.py")

    except Exception as e:
        print(f"\n❌ Ошибка при извлечении данных: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
