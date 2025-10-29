#!/usr/bin/env python3
"""
Скрипт для очистки и нормализации данных о моделях автомобилей.

Обрабатывает raw_vehicle_data.csv и создает cleaned_vehicle_data.csv
с нормализованными брендами, годами и типами кузова.
"""

import sys
import re
from pathlib import Path
from typing import Tuple, Optional
import pandas as pd


# Добавляем parent directory в Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Маппинг русских названий брендов на английские
BRAND_MAPPING = {
    # Русские варианты
    "ТОЙОТА": "Toyota",
    "ХОНДА": "Honda",
    "МАЗДА": "Mazda",
    "НИССАН": "Nissan",
    "МИТСУБИСИ": "Mitsubishi",
    "МИТСУБИШИ": "Mitsubishi",
    "СУБАРУ": "Subaru",
    "СУЗУКИ": "Suzuki",
    "ЛЕКСУС": "Lexus",
    "ИНФИНИТИ": "Infiniti",
    "БМВ": "BMW",
    "МЕРСЕДЕС": "Mercedes-Benz",
    "МЕРСЕДЕС-БЕНЦ": "Mercedes-Benz",
    "АУДИ": "Audi",
    "ФОЛЬКСВАГЕН": "Volkswagen",
    "ФОЛЬЦВАГЕН": "Volkswagen",
    "ПОРШЕ": "Porsche",
    "РЕНО": "Renault",
    "ПЕЖО": "Peugeot",
    "СИТРОЕН": "Citroen",
    "ФИАТ": "Fiat",
    "ФОРД": "Ford",
    "ШЕВРОЛЕ": "Chevrolet",
    "ДОДЖ": "Dodge",
    "ДЖИП": "Jeep",
    "КРАЙСЛЕР": "Chrysler",
    "КАДИЛЛАК": "Cadillac",
    "ХЕНДАЙ": "Hyundai",
    "ХЕНДЭ": "Hyundai",
    "КИА": "Kia",
    "ДЭВО": "Daewoo",
    "ДЭВОО": "Daewoo",
    "ССАНГ ЙОНГ": "SsangYong",
    "ССАНЪЁН": "SsangYong",
    "ЧЕРИ": "Chery",
    "ДЖИЛИ": "Geely",
    "ЛАДА": "Lada",
    "ГАЗ": "GAZ",
    "УАЗ": "UAZ",

    # Английские варианты (нормализация регистра)
    "TOYOTA": "Toyota",
    "HONDA": "Honda",
    "MAZDA": "Mazda",
    "NISSAN": "Nissan",
    "MITSUBISHI": "Mitsubishi",
    "SUBARU": "Subaru",
    "SUZUKI": "Suzuki",
    "LEXUS": "Lexus",
    "INFINITI": "Infiniti",
    "BMW": "BMW",
    "MERCEDES": "Mercedes-Benz",
    "MERCEDES-BENZ": "Mercedes-Benz",
    "AUDI": "Audi",
    "VOLKSWAGEN": "Volkswagen",
    "VW": "Volkswagen",
    "PORSCHE": "Porsche",
    "RENAULT": "Renault",
    "PEUGEOT": "Peugeot",
    "CITROEN": "Citroen",
    "FIAT": "Fiat",
    "FORD": "Ford",
    "CHEVROLET": "Chevrolet",
    "DODGE": "Dodge",
    "JEEP": "Jeep",
    "CHRYSLER": "Chrysler",
    "CADILLAC": "Cadillac",
    "HYUNDAI": "Hyundai",
    "KIA": "Kia",
    "DAEWOO": "Daewoo",
    "SSANGYONG": "SsangYong",
    "CHERY": "Chery",
    "GEELY": "Geely",
    "LADA": "Lada",
    "GAZ": "GAZ",
    "UAZ": "UAZ",
    "VOLVO": "Volvo",
    "SAAB": "Saab",
    "SKODA": "Skoda",
    "SEAT": "Seat",
    "OPEL": "Opel",
    "LAND ROVER": "Land Rover",
    "RANGE ROVER": "Land Rover",
    "JAGUAR": "Jaguar",
}


# Ключевые слова для определения типа кузова
BODY_TYPE_KEYWORDS = {
    "sedan": ["sedan", "седан"],
    "suv": ["suv", "внедорожник", "кроссовер", "crossover"],
    "minivan": ["minivan", "минивэн", "минивен", "van"],
    "hatchback": ["hatchback", "хэтчбек", "хетчбэк", "хэтч"],
    "wagon": ["wagon", "универсал", "estate"],
    "coupe": ["coupe", "купе"],
    "convertible": ["convertible", "кабриолет", "cabriolet"],
    "pickup": ["pickup", "пикап"],
}


def normalize_brand(brand: str) -> str:
    """
    Нормализует название бренда.

    Args:
        brand: Исходное название бренда

    Returns:
        Нормализованное название
    """
    if not brand:
        return ""

    # Приводим к верхнему регистру для поиска
    brand_upper = brand.strip().upper()

    # Ищем в маппинге
    normalized = BRAND_MAPPING.get(brand_upper)

    if normalized:
        return normalized

    # Если не нашли, возвращаем с заглавной буквы
    return brand.strip().title()


def parse_year_range(year_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Парсит год или диапазон лет.

    Примеры:
        "2018" -> (2018, 2018)
        "2018-2022" -> (2018, 2022)
        "2018-н.в." -> (2018, None)
        "до 2006г" -> (None, 2006)
        "" -> (None, None)

    Args:
        year_str: Строка с годом/диапазоном

    Returns:
        Кортеж (год_с, год_по)
    """
    if not year_str or year_str.strip() == '':
        return (None, None)

    year_str = year_str.strip().lower()

    # "до 2006г" -> (None, 2006)
    match = re.search(r'до\s*(\d{4})', year_str)
    if match:
        return (None, int(match.group(1)))

    # "с 2018" -> (2018, None)
    match = re.search(r'с\s*(\d{4})', year_str)
    if match:
        return (int(match.group(1)), None)

    # "2018-н.в." или "2018-" -> (2018, None)
    match = re.search(r'(\d{4})\s*[-–]\s*(?:н\.?\s*в\.?|$)', year_str)
    if match:
        return (int(match.group(1)), None)

    # "2018-2022" -> (2018, 2022)
    match = re.search(r'(\d{4})\s*[-–]\s*(\d{4})', year_str)
    if match:
        year_from = int(match.group(1))
        year_to = int(match.group(2))
        return (year_from, year_to)

    # Просто год "2018" -> (2018, 2018)
    match = re.search(r'(\d{4})', year_str)
    if match:
        year = int(match.group(1))
        return (year, year)

    return (None, None)


def detect_body_type(model: str, description: str) -> Optional[str]:
    """
    Определяет тип кузова из модели или описания.

    Args:
        model: Название модели
        description: Описание

    Returns:
        Тип кузова или None
    """
    # Объединяем для поиска
    text = f"{model} {description}".lower()

    for body_type, keywords in BODY_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return body_type

    return None


def clean_model_name(model: str) -> str:
    """
    Очищает название модели от лишних символов и пробелов.

    Args:
        model: Исходное название модели

    Returns:
        Очищенное название
    """
    if not model:
        return ""

    # Убираем лишние пробелы
    model = re.sub(r'\s+', ' ', model.strip())

    # Убираем точки в конце
    model = model.rstrip('.')

    return model


def clean_data(input_path: str, output_path: str) -> pd.DataFrame:
    """
    Очищает и нормализует данные.

    Args:
        input_path: Путь к исходному CSV
        output_path: Путь для сохранения очищенного CSV

    Returns:
        Очищенный DataFrame
    """
    print(f"📂 Загружаю данные из: {input_path}")

    # Загружаем данные
    df = pd.read_csv(input_path, encoding='utf-8-sig')

    print(f"   Загружено записей: {len(df)}")

    # Нормализуем бренды
    print("\n🔧 Нормализация брендов...")
    df['brand_normalized'] = df['brand'].apply(normalize_brand)

    brands_before = df['brand'].nunique()
    brands_after = df['brand_normalized'].nunique()
    print(f"   Уникальных брендов: {brands_before} → {brands_after}")

    # Очищаем названия моделей
    print("\n🔧 Очистка названий моделей...")
    df['model_cleaned'] = df['model'].apply(clean_model_name)

    # Парсим годы
    print("\n🔧 Парсинг годов...")
    year_parsed = df['year'].apply(parse_year_range)
    df['year_from'] = year_parsed.apply(lambda x: x[0])
    df['year_to'] = year_parsed.apply(lambda x: x[1])

    # Статистика по годам
    with_years = df[(df['year_from'].notna()) | (df['year_to'].notna())]
    print(f"   Записей с годами: {len(with_years)} из {len(df)}")

    # Определяем типы кузова
    print("\n🔧 Определение типов кузова...")
    df['body_type'] = df.apply(
        lambda row: detect_body_type(
            row['model_cleaned'],
            row['description'] if pd.notna(row['description']) else ''
        ),
        axis=1
    )

    with_body_type = df[df['body_type'].notna()]
    print(f"   Определен тип кузова: {len(with_body_type)} из {len(df)}")

    # Статистика по типам кузова
    if len(with_body_type) > 0:
        print("\n   Распределение типов кузова:")
        for body_type, count in df['body_type'].value_counts().items():
            print(f"     {body_type}: {count}")

    # Удаляем дубликаты после нормализации
    print("\n🔧 Удаление дубликатов...")
    before_dedup = len(df)
    df = df.drop_duplicates(
        subset=['brand_normalized', 'model_cleaned', 'year_from', 'year_to'],
        keep='first'
    )
    after_dedup = len(df)
    removed = before_dedup - after_dedup

    if removed > 0:
        print(f"   Удалено дубликатов: {removed}")

    # Переименовываем колонки для финальной версии
    df_final = df[[
        'id',
        'brand_normalized',
        'model_cleaned',
        'year_from',
        'year_to',
        'body_type',
        'description'
    ]].rename(columns={
        'brand_normalized': 'brand',
        'model_cleaned': 'model'
    })

    # Сохраняем
    print(f"\n💾 Сохраняю очищенные данные: {output_path}")
    df_final.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"   Финальных записей: {len(df_final)}")
    print(f"   Размер файла: {Path(output_path).stat().st_size / 1024:.1f} KB")

    return df_final


def print_statistics(df: pd.DataFrame) -> None:
    """
    Выводит статистику по очищенным данным.

    Args:
        df: DataFrame с данными
    """
    print("\n" + "=" * 60)
    print("📊 СТАТИСТИКА ОЧИЩЕННЫХ ДАННЫХ")
    print("=" * 60)

    print(f"\n📝 Общее количество записей: {len(df)}")
    print(f"🏢 Уникальных брендов: {df['brand'].nunique()}")
    print(f"🚗 Уникальных моделей: {df['model'].nunique()}")

    # Топ-10 брендов
    print("\n🏆 Топ-10 брендов по количеству моделей:")
    for i, (brand, count) in enumerate(df['brand'].value_counts().head(10).items(), 1):
        print(f"   {i:2}. {brand:20} {count:4} моделей")

    # Распределение по типам кузова
    print("\n🚙 Распределение по типам кузова:")
    body_type_counts = df['body_type'].value_counts()
    for body_type, count in body_type_counts.items():
        percentage = count / len(df) * 100
        print(f"   {body_type or 'unknown':15} {count:4} ({percentage:5.1f}%)")

    # Распределение по годам
    print("\n📅 Распределение по годам:")
    with_years = df[(df['year_from'].notna()) | (df['year_to'].notna())]
    without_years = len(df) - len(with_years)
    print(f"   С указанием года:  {len(with_years):4} ({len(with_years)/len(df)*100:5.1f}%)")
    print(f"   Без указания года: {without_years:4} ({without_years/len(df)*100:5.1f}%)")


def main():
    """Основная функция."""

    print("=" * 60)
    print("🧹 ОЧИСТКА И НОРМАЛИЗАЦИЯ ДАННЫХ О МОДЕЛЯХ")
    print("=" * 60)

    # Определяем пути
    project_root = Path(__file__).parent.parent.parent
    input_path = project_root / "database" / "data" / "raw_vehicle_data.csv"
    output_path = project_root / "database" / "data" / "cleaned_vehicle_data.csv"

    # Проверяем наличие исходного файла
    if not input_path.exists():
        print(f"\n❌ Ошибка: Исходный файл не найден")
        print(f"   Ожидаемый путь: {input_path}")
        print(f"\nСначала запустите: python scripts/extract_pdf_data.py")
        sys.exit(1)

    try:
        # Очищаем данные
        df = clean_data(str(input_path), str(output_path))

        # Выводим статистику
        print_statistics(df)

        print("\n" + "=" * 60)
        print("✅ ОЧИСТКА ЗАВЕРШЕНА УСПЕШНО")
        print("=" * 60)
        print(f"\nСледующий шаг: python scripts/import_to_database.py")

    except Exception as e:
        print(f"\n❌ Ошибка при очистке данных: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
