# План импорта данных из БД_машины.pdf

Этот документ описывает пошаговый план импорта "грязных" данных из файла **БД_машины.pdf** в нормализованную структуру базы данных.

---

## 📋 Обзор задачи

**Источник данных:** `/ТЗ/БД_машины.pdf`
**Формат:** PDF-таблица с 39 страницами, содержащая ~900+ записей
**Структура:** ID, Марка, Модель, Год, Описание

**Цель:** Импортировать данные в нормализованные таблицы:
- `brands` - марки автомобилей
- `models` - модели автомобилей с привязкой к маркам
- `body_types` - типы кузова (извлечь из описания)
- `patterns` - наличие лекал для конкретных моделей

---

## 🎯 Стратегия импорта

### Этап 1: Извлечение и очистка данных из PDF

**Задача:** Конвертировать PDF в структурированный формат (CSV/JSON)

**Технический подход:**

```python
# Использовать библиотеку для парсинга PDF
# Опции:
# 1. pdfplumber - хорош для таблиц
# 2. tabula-py - специализирован для таблиц в PDF
# 3. PyPDF2 + регулярные выражения
```

**Пример кода:**

```python
import pdfplumber
import pandas as pd
from pathlib import Path

def extract_tables_from_pdf(pdf_path: str) -> pd.DataFrame:
    """
    Извлечь все таблицы из PDF и объединить в один DataFrame.

    Returns:
        DataFrame со столбцами: ID, Марка, Модель, Год, Описание
    """
    all_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Извлекаем таблицу со страницы
            table = page.extract_table()

            if table:
                # Пропускаем заголовок (первая строка)
                for row in table[1:]:
                    if row[0]:  # Проверка, что ID не пустой
                        all_data.append({
                            'id': row[0],
                            'brand': row[1],
                            'model': row[2],
                            'year': row[3],
                            'description': row[4]
                        })

    df = pd.DataFrame(all_data)
    return df

# Использование
df = extract_tables_from_pdf('../ТЗ/БД_машины.pdf')
df.to_csv('raw_vehicle_data.csv', index=False)
```

**Ожидаемый результат:** Файл `raw_vehicle_data.csv` с ~900 строками

---

### Этап 2: Нормализация и обогащение данных

**Задача:** Очистить данные и привести к консистентному виду

**Проблемы в исходных данных (по анализу БД_машины.pdf):**

1. **Непоследовательность марок:** "Honda" vs "HONDA" vs "хонда"
2. **Смешанные языки:** Кириллица и латиница
3. **Отсутствие годов:** Множество записей с пустым полем "Год"
4. **Неструктурированное описание:** "с бортами левый руль", "полный салон", "3 ряда"
5. **Дублирование:** Одна и та же модель может встречаться несколько раз

**Код очистки:**

```python
import re
from typing import Optional, Tuple

def normalize_brand(brand: str) -> str:
    """
    Нормализовать название марки.

    Примеры:
        "HONDA" -> "Honda"
        "Тойота" -> "Toyota"
        "мерседес-бенц" -> "Mercedes-Benz"
    """
    # Словарь для транслитерации кириллицы
    brand_mapping = {
        "Тойота": "Toyota",
        "Хонда": "Honda",
        "БМВ": "BMW",
        "Мерседес": "Mercedes-Benz",
        # ... расширить для всех марок
    }

    brand = brand.strip()

    # Проверка в словаре
    if brand in brand_mapping:
        return brand_mapping[brand]

    # Capitalize first letter of each word
    return brand.title()


def extract_body_type_from_description(description: str) -> Optional[str]:
    """
    Извлечь тип кузова из описания.

    Примеры:
        "с бортами левый руль" -> None (не определен)
        "седан левый руль" -> "sedan"
        "внедорожник 3 ряда" -> "suv"
    """
    if not description:
        return None

    desc_lower = description.lower()

    # Словарь ключевых слов
    body_type_keywords = {
        'sedan': ['седан'],
        'hatchback': ['хэтчбек', 'хетчбек'],
        'suv': ['внедорожник', 'джип'],
        'minivan': ['минивэн', 'минивен', 'полный салон', '3 ряда'],
        'truck': ['грузовой', 'грузовик', 'кабина'],
        'coupe': ['купе', 'купэ'],
        'wagon': ['универсал'],
    }

    for body_code, keywords in body_type_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return body_code

    return None


def parse_year_range(year_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Парсинг года или диапазона лет.

    Примеры:
        "2020" -> (2020, 2020)
        "2018-2022" -> (2018, 2022)
        "до 2006г" -> (None, 2006)
        "-" -> (None, None)
    """
    if not year_str or year_str.strip() in ['-', '']:
        return (None, None)

    # Убираем "г", "г.", пробелы
    year_str = re.sub(r'[гг\.]', '', year_str).strip()

    # Диапазон: 2018-2022
    if '-' in year_str:
        parts = year_str.split('-')
        try:
            year_from = int(parts[0]) if parts[0] else None
            year_to = int(parts[1]) if parts[1] else None
            return (year_from, year_to)
        except ValueError:
            return (None, None)

    # Одно число: 2020
    try:
        year = int(year_str)
        return (year, year)
    except ValueError:
        return (None, None)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Применить все очистки к DataFrame."""
    df_clean = df.copy()

    # Нормализация марок
    df_clean['brand'] = df_clean['brand'].apply(normalize_brand)

    # Извлечение типа кузова
    df_clean['body_type'] = df_clean['description'].apply(extract_body_type_from_description)

    # Парсинг годов
    years = df_clean['year'].apply(parse_year_range)
    df_clean['year_from'] = years.apply(lambda x: x[0])
    df_clean['year_to'] = years.apply(lambda x: x[1])

    # Удаление дублей (по марке, модели, годам)
    df_clean = df_clean.drop_duplicates(
        subset=['brand', 'model', 'year_from', 'year_to'],
        keep='first'
    )

    return df_clean

# Использование
df_raw = pd.read_csv('raw_vehicle_data.csv')
df_clean = clean_dataframe(df_raw)
df_clean.to_csv('cleaned_vehicle_data.csv', index=False)
```

**Ожидаемый результат:** Файл `cleaned_vehicle_data.csv` с очищенными данными

---

### Этап 3: Загрузка в базу данных

**Задача:** Импортировать очищенные данные в PostgreSQL с соблюдением нормализации

**Последовательность действий:**

1. **Создать справочник марок** (`brands`)
2. **Создать справочник типов кузова** (`body_types`) - если еще не создан
3. **Загрузить модели** (`models`)
4. **Создать записи лекал** (`patterns`) для tenant

**Пример кода:**

```python
from sqlalchemy.orm import Session
from database.models import Tenant, Brand, BodyType, Model, Pattern, ProductCategory
from database.config import get_sync_session
import pandas as pd

def import_brands(df: pd.DataFrame, session: Session) -> dict:
    """
    Импортировать уникальные марки.

    Returns:
        Словарь {brand_name: brand_id}
    """
    unique_brands = df['brand'].unique()
    brand_map = {}

    for brand_name in unique_brands:
        # Проверяем, существует ли марка
        brand = session.query(Brand).filter_by(name=brand_name).first()

        if not brand:
            # Создаем новую марку
            brand = Brand(
                name=brand_name,
                slug=brand_name.lower().replace(' ', '_').replace('-', '_')
            )
            session.add(brand)
            session.flush()  # Получить ID

        brand_map[brand_name] = brand.id

    session.commit()
    return brand_map


def import_body_types(session: Session) -> dict:
    """
    Создать стандартные типы кузова, если не существуют.

    Returns:
        Словарь {code: id}
    """
    standard_body_types = [
        {'code': 'sedan', 'name_ru': 'Седан'},
        {'code': 'hatchback', 'name_ru': 'Хэтчбек'},
        {'code': 'suv', 'name_ru': 'Внедорожник'},
        {'code': 'minivan', 'name_ru': 'Минивэн'},
        {'code': 'truck', 'name_ru': 'Грузовой'},
        {'code': 'coupe', 'name_ru': 'Купе'},
        {'code': 'wagon', 'name_ru': 'Универсал'},
    ]

    body_type_map = {}

    for bt_data in standard_body_types:
        bt = session.query(BodyType).filter_by(code=bt_data['code']).first()

        if not bt:
            bt = BodyType(**bt_data)
            session.add(bt)
            session.flush()

        body_type_map[bt_data['code']] = bt.id

    session.commit()
    return body_type_map


def import_models(df: pd.DataFrame, session: Session, brand_map: dict, body_type_map: dict) -> dict:
    """
    Импортировать модели автомобилей.

    Returns:
        Словарь {(brand, model, year_from, year_to): model_id}
    """
    model_map = {}

    for _, row in df.iterrows():
        brand_id = brand_map.get(row['brand'])
        body_type_id = body_type_map.get(row['body_type']) if row['body_type'] else None

        # Проверяем существование модели
        existing_model = session.query(Model).filter_by(
            brand_id=brand_id,
            name=row['model'],
            year_from=row['year_from'],
            year_to=row['year_to']
        ).first()

        if not existing_model:
            model = Model(
                brand_id=brand_id,
                name=row['model'],
                year_from=row['year_from'],
                year_to=row['year_to'],
                body_type_id=body_type_id,
                metadata={'source': 'pdf_import'}
            )
            session.add(model)
            session.flush()
            model_id = model.id
        else:
            model_id = existing_model.id

        key = (row['brand'], row['model'], row['year_from'], row['year_to'])
        model_map[key] = model_id

    session.commit()
    return model_map


def import_patterns(
    df: pd.DataFrame,
    session: Session,
    tenant_slug: str,
    category_code: str,
    model_map: dict
) -> None:
    """
    Создать записи лекал (patterns) для tenant.

    Args:
        tenant_slug: Идентификатор арендатора (evopoliki, five_deluxe)
        category_code: Код категории (eva_mats, car_covers, etc.)
    """
    # Получаем tenant и category
    tenant = session.query(Tenant).filter_by(slug=tenant_slug).first()
    category = session.query(ProductCategory).filter_by(code=category_code).first()

    if not tenant or not category:
        raise ValueError(f"Tenant '{tenant_slug}' or category '{category_code}' not found")

    for _, row in df.iterrows():
        key = (row['brand'], row['model'], row['year_from'], row['year_to'])
        model_id = model_map.get(key)

        if not model_id:
            continue

        # Проверяем, существует ли лекало
        existing_pattern = session.query(Pattern).filter_by(
            tenant_id=tenant.id,
            category_id=category.id,
            model_id=model_id
        ).first()

        if not existing_pattern:
            pattern = Pattern(
                tenant_id=tenant.id,
                category_id=category.id,
                model_id=model_id,
                available=True,
                notes=row['description']  # Сохраняем оригинальное описание
            )
            session.add(pattern)

    session.commit()


def run_full_import(csv_path: str, tenant_slug: str, category_code: str = 'eva_mats'):
    """
    Полный цикл импорта данных.

    Usage:
        run_full_import('cleaned_vehicle_data.csv', 'evopoliki')
    """
    df = pd.read_csv(csv_path)

    with get_sync_session() as session:
        print("1. Импорт марок...")
        brand_map = import_brands(df, session)
        print(f"   Импортировано марок: {len(brand_map)}")

        print("2. Создание типов кузова...")
        body_type_map = import_body_types(session)
        print(f"   Создано типов кузова: {len(body_type_map)}")

        print("3. Импорт моделей...")
        model_map = import_models(df, session, brand_map, body_type_map)
        print(f"   Импортировано моделей: {len(model_map)}")

        print("4. Создание записей лекал...")
        import_patterns(df, session, tenant_slug, category_code, model_map)
        print(f"   Создано записей лекал: {len(df)}")

    print("✅ Импорт завершен успешно!")


# Запуск импорта
if __name__ == "__main__":
    run_full_import('cleaned_vehicle_data.csv', 'evopoliki', 'eva_mats')
```

---

## 📝 Пошаговая инструкция

### Шаг 1: Установка дополнительных зависимостей

```bash
pip install pdfplumber pandas tabula-py
```

### Шаг 2: Извлечение данных из PDF

```bash
python scripts/extract_pdf_data.py
# Создается файл: raw_vehicle_data.csv
```

### Шаг 3: Очистка и нормализация

```bash
python scripts/clean_data.py
# Создается файл: cleaned_vehicle_data.csv
```

### Шаг 4: Ручная проверка данных

```bash
# Откройте CSV в Excel/LibreOffice
# Проверьте правильность нормализации марок
# Добавьте недостающие типы кузова вручную (опционально)
```

### Шаг 5: Импорт в БД

```bash
python scripts/import_to_database.py --tenant evopoliki --category eva_mats
```

### Шаг 6: Верификация

```sql
-- Проверка количества импортированных записей
SELECT COUNT(*) FROM brands;
SELECT COUNT(*) FROM models;
SELECT COUNT(*) FROM patterns WHERE tenant_id = 1;

-- Проверка корректности связей
SELECT
    b.name AS brand,
    m.name AS model,
    bt.name_ru AS body_type,
    p.notes
FROM patterns p
JOIN models m ON p.model_id = m.id
JOIN brands b ON m.brand_id = b.id
LEFT JOIN body_types bt ON m.body_type_id = bt.id
WHERE p.tenant_id = 1
LIMIT 10;
```

---

## ⚠️ Важные замечания

1. **Резервная копия:** Перед импортом сделайте backup БД
   ```bash
   pg_dump car_chatbot > backup_before_import.sql
   ```

2. **Пробный запуск:** Сначала импортируйте 10-20 записей для проверки

3. **Логирование:** Сохраняйте логи импорта для отладки
   ```python
   import logging
   logging.basicConfig(filename='import.log', level=logging.INFO)
   ```

4. **Дедупликация:** Проверяйте наличие дублей на каждом этапе

5. **Валидация:** После импорта проверьте целостность данных:
   - Все ли марки корректно распознаны?
   - Все ли модели имеют корректные foreign keys?
   - Все ли patterns связаны с существующими моделями?

---

## 🔄 Дальнейшие шаги

После успешного импорта:

1. **Импорт цен** из отчета по встрече в таблицу `prices`
2. **Создание тестовых данных** для второго tenant (five_deluxe)
3. **Настройка админ-панели** для управления данными
4. **Интеграция с ботом** для поиска по моделям

---

## 📊 Ожидаемые результаты

После выполнения всех шагов:

- ✅ **~50-100** уникальных марок в таблице `brands`
- ✅ **~900+** моделей в таблице `models`
- ✅ **7** типов кузова в таблице `body_types`
- ✅ **~900+** записей лекал в таблице `patterns` (для tenant evopoliki)
- ✅ Все данные нормализованы и готовы к использованию

---

**Версия:** 1.0
**Автор:** Claude
**Дата:** 2025-01-09
