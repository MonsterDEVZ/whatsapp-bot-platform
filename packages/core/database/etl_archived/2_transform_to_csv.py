#!/usr/bin/env python3
"""
ETL Pipeline - Step 2: TRANSFORM
=================================
Парсит сырой текст из output/raw_text.txt,
применяет очистку и нормализацию данных,
сохраняет результат в output/patterns_clean.csv

Использование:
    python 2_transform_to_csv.py

Результат:
    Создается файл ../output/patterns_clean.csv
    с колонками: brand, model, category, available
"""

import sys
import csv
import re
from pathlib import Path
from typing import List, Dict, Set

# Добавляем пути
sys.path.insert(0, str(Path(__file__).parent.parent))


class DataTransformer:
    """Класс для парсинга и очистки данных."""

    def __init__(self):
        self.patterns = []
        self.seen = set()  # Для отслеживания дубликатов

    def clean_brand_name(self, brand: str) -> str:
        """
        Очищает название бренда и нормализует регистр.
        """
        brand = brand.strip()
        # Убираем лишние пробелы
        brand = " ".join(brand.split())
        # Нормализуем регистр: первая буква заглавная, остальные строчные
        # Кроме английских аббревиатур типа KIA → Kia
        brand = brand.capitalize()
        return brand

    def clean_model_name(self, model: str, brand: str) -> str:
        """
        Очищает название модели:
        - Убирает префикс бренда если он есть
        - Убирает лишние пробелы и символы
        """
        model = model.strip()

        # Убираем префикс бренда (различные варианты)
        prefixes_to_remove = [
            f"{brand} ",
            f"{brand}-",
            f"{brand}_",
            f"{brand.upper()} ",
            f"{brand.lower()} ",
        ]

        for prefix in prefixes_to_remove:
            if model.startswith(prefix):
                model = model[len(prefix):].strip()
                break

        # Убираем множественные пробелы
        model = " ".join(model.split())

        return model

    def parse_text(self, text: str) -> List[Dict[str, str]]:
        """
        Парсит сырой текст из PDF-таблицы.

        Ожидаемый формат:
        ID Марка Модель Год Описание
        359 Дайхатсу Куаре - 1 поколение с бортами
        218 Honda Инспайер 1999 средний борт 1 кузов
        """
        print("\n🔄 ПАРСИНГ ДАННЫХ")
        print("=" * 70)

        lines = text.split('\n')
        patterns_count = 0

        for line in lines:
            line = line.strip()

            # Пропускаем пустые строки, метки страниц и заголовки
            if not line or line.startswith('===') or line.startswith('ID Марка'):
                continue

            words = line.split()

            # Проверяем, что строка начинается с ID (числа)
            if len(words) >= 3 and words[0].isdigit():
                # Формат: ID Марка Модель [Год Описание...]
                # words[0] = ID (пропускаем)
                # words[1] = Марка
                # words[2] = Модель

                brand_raw = words[1]
                model_raw = words[2]

                # Очищаем бренд и модель
                brand = self.clean_brand_name(brand_raw)
                model = self.clean_model_name(model_raw, brand)

                # Фильтруем некорректные данные
                if brand and model and brand != '-' and model != '-':  # Проверяем что оба не пустые и не прочерки
                    # Создаем уникальный ключ для проверки дубликатов
                    key = f"{brand}|{model}".lower()

                    if key not in self.seen:
                        self.seen.add(key)

                        pattern = {
                            'brand': brand,
                            'model': model,
                            'category': 'eva_mats',  # По умолчанию
                            'available': 'true'
                        }

                        self.patterns.append(pattern)
                        patterns_count += 1

                        if patterns_count % 100 == 0:
                            print(f"   Обработано записей: {patterns_count}", end="\r")

        print(f"\n\n✅ Всего уникальных записей: {len(self.patterns)}")
        return self.patterns

    def save_to_csv(self, patterns: List[Dict[str, str]], output_path: Path):
        """
        Сохраняет данные в CSV файл.
        """
        print("\n💾 СОХРАНЕНИЕ В CSV")
        print("=" * 70)

        # Сортируем по бренду и модели для удобства
        patterns_sorted = sorted(patterns, key=lambda x: (x['brand'], x['model']))

        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['brand', 'model', 'category', 'available']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerows(patterns_sorted)

        print(f"✅ Сохранено записей: {len(patterns_sorted)}")
        print(f"📁 Файл: {output_path}")

        # Показываем примеры
        print("\n📊 ПРИМЕРЫ ЗАПИСЕЙ:")
        for i, pattern in enumerate(patterns_sorted[:10], 1):
            print(f"   {i}. {pattern['brand']} {pattern['model']}")

        if len(patterns_sorted) > 10:
            print(f"   ... и еще {len(patterns_sorted) - 10} записей")


def main():
    """Главная функция."""
    print("=" * 70)
    print("🔄 ETL PIPELINE - STEP 2: TRANSFORM")
    print("=" * 70)

    # Определяем пути
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    input_path = project_root / "output" / "raw_text.txt"
    output_path = project_root / "output" / "patterns_clean.csv"

    if not input_path.exists():
        print(f"\n❌ Файл не найден: {input_path}")
        print("Сначала запустите: python 1_extract_raw_text.py")
        sys.exit(1)

    # Читаем сырой текст
    print(f"\n📖 Чтение: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    print(f"   Размер: {len(raw_text):,} символов")

    # Парсим и очищаем
    transformer = DataTransformer()
    patterns = transformer.parse_text(raw_text)

    if not patterns:
        print("\n⚠️  Не удалось извлечь данные из текста!")
        print("Проверьте формат файла raw_text.txt")
        sys.exit(1)

    # Сохраняем в CSV
    transformer.save_to_csv(patterns, output_path)

    print("\n" + "=" * 70)
    print("✅ ТРАНСФОРМАЦИЯ ЗАВЕРШЕНА")
    print("=" * 70)
    print(f"\nСледующий шаг: python 3_load_from_csv.py")


if __name__ == "__main__":
    main()
