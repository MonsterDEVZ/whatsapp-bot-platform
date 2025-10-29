# 📜 Скрипты импорта данных

Набор скриптов для импорта данных о моделях автомобилей из PDF в базу данных PostgreSQL.

---

## 🎯 Назначение

Эти скрипты автоматизируют процесс извлечения, очистки и импорта данных из PDF файла `БД_машины.pdf` в базу данных. Данные используются для определения наличия лекал (выкроек) для различных моделей автомобилей.

---

## 📁 Файлы

| Скрипт | Описание | Выходные данные |
|--------|----------|-----------------|
| `seed_data.py` | Создает начальные данные (tenants, категории, опции) | Записи в БД |
| `extract_pdf_data.py` | Извлекает данные из PDF таблиц | `data/raw_vehicle_data.csv` |
| `clean_data.py` | Нормализует и очищает данные | `data/cleaned_vehicle_data.csv` |
| `import_to_database.py` | Импортирует данные в PostgreSQL | Записи в БД |

---

## 🚀 Быстрый старт

### Шаг 1: Установка зависимостей

```bash
cd database
pip install -r requirements.txt
```

### Шаг 2: Настройка окружения

```bash
# Создайте .env файл из примера
cp .env.example .env

# Отредактируйте .env с вашими credentials
nano .env
```

Пример `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=car_chatbot
DB_USER=postgres
DB_PASSWORD=your_secure_password_here
```

### Шаг 3: Создание базы данных

```sql
-- Подключитесь к PostgreSQL
psql -U postgres

-- Создайте базу данных
CREATE DATABASE car_chatbot;

-- Создайте пользователя (опционально)
CREATE USER car_bot WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE car_chatbot TO car_bot;

\q
```

### Шаг 4: Применение миграций

```bash
# Из директории database/
alembic upgrade head
```

Вы должны увидеть:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 20250109_0001, Initial schema
```

### Шаг 5: Создание начальных данных

```bash
python scripts/seed_data.py
```

Этот скрипт создаст:
- ✅ 2 tenants (evopoliki, five_deluxe)
- ✅ 4 категории продуктов (EVA коврики, чехлы, 5D коврики, коврики в багажник)
- ✅ ~10 опций продуктов (с бортами, 3-й ряд, типы экокожи, цвета)
- ✅ ~15 текстов бота для каждого tenant

### Шаг 6: Импорт данных о моделях

```bash
# Извлечение данных из PDF
python scripts/extract_pdf_data.py

# Очистка и нормализация
python scripts/clean_data.py

# Импорт в базу данных
python scripts/import_to_database.py --tenant evopoliki
```

---

## 📋 Подробное описание

### 1️⃣ seed_data.py

**Назначение**: Создает базовые справочные данные.

**Запуск**:

```bash
python scripts/seed_data.py
```

**Что создается**:

- **Tenants** (арендаторы):
  - `evopoliki` - EVOPOLIKI
  - `five_deluxe` - 5Deluxe

- **ProductCategories** (категории):
  - `eva_mats` - EVA коврики
  - `seat_covers` - Чехлы из экокожи
  - `5d_mats` - 5D коврики
  - `trunk_mats` - Коврики в багажник

- **ProductOptions** (опции):
  - Для EVA: с бортами, 3-й ряд, перемычка
  - Для чехлов: типы экокожи, перфорация, подогрев
  - Для 5D: цвета (бежевый, черный, серый)

- **BotTexts** (тексты):
  - Приветствия, вопросы, уведомления для каждого tenant

**Идемпотентность**: ✅ Скрипт можно запускать повторно - существующие записи не дублируются.

---

### 2️⃣ extract_pdf_data.py

**Назначение**: Извлекает данные о моделях из PDF файла.

**Запуск**:

```bash
python scripts/extract_pdf_data.py
```

**Требования**:
- PDF файл должен находиться по пути: `ТЗ/БД_машины.pdf`
- Установлен пакет `pdfplumber`

**Процесс**:

1. Открывает PDF файл (39 страниц)
2. Извлекает таблицы со всех страниц
3. Парсит колонки: №, Марка, Модель, Год, Примечание
4. Удаляет заголовки и пустые строки
5. Удаляет дубликаты

**Выход**: `database/data/raw_vehicle_data.csv` (~900 записей)

**Пример вывода**:

```
📄 Открываю PDF файл: ТЗ/БД_машины.pdf
📊 Всего страниц: 39
  Обработка страницы 39/39...
✅ Извлечено записей: 897

🔍 Валидация данных...
  📊 Уникальных брендов: 52

  🏆 Топ-5 брендов:
     Toyota: 156 моделей
     Honda: 89 моделей
     Nissan: 72 моделей
     BMW: 54 моделей
     Mercedes-Benz: 47 моделей
```

---

### 3️⃣ clean_data.py

**Назначение**: Нормализует и очищает извлеченные данные.

**Запуск**:

```bash
python scripts/clean_data.py
```

**Требования**:
- Наличие файла `database/data/raw_vehicle_data.csv`
- Установлен пакет `pandas`

**Процесс нормализации**:

1. **Бренды**:
   - "ТОЙОТА" → "Toyota"
   - "ХОНДА" → "Honda"
   - "БМВ" → "BMW"
   - И т.д. (~70 вариантов в маппинге)

2. **Годы**:
   - "2018" → `(2018, 2018)`
   - "2018-2022" → `(2018, 2022)`
   - "2018-н.в." → `(2018, None)`
   - "до 2006г" → `(None, 2006)`

3. **Типы кузова** (автоопределение):
   - "Camry 70 sedan" → `sedan`
   - "X5 SUV" → `suv`
   - "Odyssey минивэн" → `minivan`

4. **Очистка моделей**:
   - Удаление лишних пробелов
   - Удаление точек в конце
   - Нормализация регистра

**Выход**: `database/data/cleaned_vehicle_data.csv`

**Пример вывода**:

```
🔧 Нормализация брендов...
   Уникальных брендов: 52 → 48

🔧 Парсинг годов...
   Записей с годами: 823 из 897

🔧 Определение типов кузова...
   Определен тип кузова: 645 из 897

   Распределение типов кузова:
     sedan: 312
     suv: 198
     minivan: 85
     hatchback: 50

🔧 Удаление дубликатов...
   Удалено дубликатов: 12
```

---

### 4️⃣ import_to_database.py

**Назначение**: Импортирует очищенные данные в PostgreSQL.

**Запуск**:

```bash
# Для tenant evopoliki
python scripts/import_to_database.py --tenant evopoliki

# Для tenant five_deluxe
python scripts/import_to_database.py --tenant five_deluxe --category eva_mats

# С указанием пути к CSV
python scripts/import_to_database.py --csv /path/to/data.csv --tenant evopoliki
```

**Аргументы**:

| Аргумент | Описание | По умолчанию |
|----------|----------|--------------|
| `--tenant` | Slug арендатора | `evopoliki` |
| `--category` | Slug категории продукта | `eva_mats` |
| `--csv` | Путь к CSV файлу | `data/cleaned_vehicle_data.csv` |

**Требования**:
- PostgreSQL запущен и доступен
- Миграции применены (`alembic upgrade head`)
- Seed data создан (`python scripts/seed_data.py`)
- Файл `cleaned_vehicle_data.csv` существует

**Процесс импорта** (4 этапа):

1. **Импорт брендов** (`brands`):
   - Создает уникальные бренды
   - Пропускает существующие
   - Возвращает маппинг {name → id}

2. **Импорт типов кузова** (`body_types`):
   - Создает стандартные типы: sedan, suv, minivan, и т.д.
   - Идемпотентный

3. **Импорт моделей** (`models`):
   - Привязывает к брендам (FK)
   - Привязывает к типам кузова (FK)
   - Сохраняет диапазоны лет
   - Пропускает дубликаты по (brand_id, name, year_from, year_to)

4. **Импорт лекал** (`patterns`):
   - Создает запись о наличии лекала
   - Привязывает к tenant (FK)
   - Привязывает к категории продукта (FK)
   - Привязывает к модели (FK)
   - Устанавливает `available=True`

**Пример вывода**:

```
📥 ИМПОРТ ДАННЫХ В БАЗУ
==========================================

📂 Загрузка данных из: data/cleaned_vehicle_data.csv
   Загружено записей: 885

🔗 Подключение к БД: localhost:5432/car_chatbot

🏢 Импорт брендов...
   Уникальных брендов: 48
   ✅ Импортировано брендов: 48

🚙 Импорт типов кузова...
   ✅ Импортировано типов кузова: 9

🚗 Импорт моделей...
   Импортировано: 800...
   ✅ Импортировано моделей: 885
   ⚠️  Пропущено записей: 0

📐 Импорт лекал для tenant=evopoliki, category=eva_mats...
   Импортировано: 800...
   ✅ Импортировано лекал: 885

✅ ИМПОРТ ЗАВЕРШЕН УСПЕШНО
==========================================

📊 Итоговая статистика:
   Брендов:       48
   Типов кузова:  9
   Моделей:       885
   Лекал:         885
```

---

## 🔧 Устранение проблем

### Ошибка: "PDF файл не найден"

**Причина**: Файл `БД_машины.pdf` отсутствует или находится не в той директории.

**Решение**:

```bash
# Проверьте наличие файла
ls -la ТЗ/БД_машины.pdf

# Убедитесь, что запускаете скрипт из корня проекта
pwd  # Должно быть: /path/to/CarChatbot
```

### Ошибка: "Ошибка подключения к БД"

**Причина**: PostgreSQL не запущен или неверные credentials.

**Решение**:

```bash
# Проверьте статус PostgreSQL
pg_isready -h localhost -p 5432

# Если не запущен, запустите
# macOS (Homebrew):
brew services start postgresql@15

# Linux:
sudo systemctl start postgresql

# Проверьте переменные окружения
cat .env
```

### Ошибка: "Tenant 'evopoliki' не найден"

**Причина**: Не создан seed data.

**Решение**:

```bash
# Создайте начальные данные
python scripts/seed_data.py
```

### Ошибка: "relation 'tenants' does not exist"

**Причина**: Миграции не применены.

**Решение**:

```bash
# Примените миграции
alembic upgrade head

# Проверьте список таблиц
psql -U postgres -d car_chatbot -c "\dt"
```

---

## 📊 Проверка результатов

После успешного импорта проверьте данные:

```sql
-- Подключитесь к БД
psql -U postgres -d car_chatbot

-- Проверьте количество записей
SELECT 'Tenants' as table_name, COUNT(*) as count FROM tenants
UNION ALL
SELECT 'Brands', COUNT(*) FROM brands
UNION ALL
SELECT 'Models', COUNT(*) FROM models
UNION ALL
SELECT 'Patterns', COUNT(*) FROM patterns
UNION ALL
SELECT 'Product Categories', COUNT(*) FROM product_categories
UNION ALL
SELECT 'Product Options', COUNT(*) FROM product_options;

-- Топ-5 брендов по количеству моделей
SELECT
    b.name,
    COUNT(m.id) as models_count
FROM brands b
LEFT JOIN models m ON b.id = m.brand_id
GROUP BY b.id, b.name
ORDER BY models_count DESC
LIMIT 5;

-- Проверка лекал для Toyota Camry
SELECT
    t.name as tenant,
    b.name as brand,
    m.name as model,
    m.year_from,
    m.year_to,
    pc.name as category,
    p.available
FROM patterns p
JOIN tenants t ON p.tenant_id = t.id
JOIN product_categories pc ON p.category_id = pc.id
JOIN models m ON p.model_id = m.id
JOIN brands b ON m.brand_id = b.id
WHERE b.name = 'Toyota' AND m.name LIKE '%Camry%'
ORDER BY m.year_from;
```

---

## 🎯 Следующие шаги

После успешного импорта данных:

1. **Импорт цен** - Создайте скрипт для импорта цен из отчета по встрече
2. **Дублирование для второго tenant** - Импортируйте данные для `five_deluxe`
3. **API разработка** - Создайте FastAPI эндпоинты для чат-бота
4. **Тестирование fuzzy search** - Проверьте поиск моделей с опечатками
5. **Админ-панель** - Добавьте интерфейс для управления данными

---

## 📝 Примечания

- Все скрипты **идемпотентны** - можно запускать повторно без дублирования данных
- CSV файлы добавлены в `.gitignore` и не коммитятся в Git
- Скрипты используют **синхронную** SQLAlchemy (sync) для простоты
- Для production бота используйте **асинхронную** версию из `config.py`

---

**Автор**: Claude (AI Assistant)
**Дата**: 2025-01-09
**Версия**: 1.0
