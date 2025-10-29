# Database Layer - Car Accessories Chatbot SaaS

Этот каталог содержит все необходимое для работы с базой данных:
- SQLAlchemy модели
- Alembic миграции
- Конфигурация подключения
- Утилиты для импорта данных

## 📋 Содержание

- [Быстрый старт](#быстрый-старт)
- [Структура проекта](#структура-проекта)
- [Настройка окружения](#настройка-окружения)
- [Работа с миграциями](#работа-с-миграциями)
- [Импорт данных](#импорт-данных)
- [Полезные команды](#полезные-команды)

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
cd database
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

```bash
# Скопируйте пример конфигурации
cp .env.example .env

# Отредактируйте .env и укажите реальные данные
nano .env
```

Минимальная конфигурация `.env`:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=car_chatbot
DB_USER=postgres
DB_PASSWORD=your_password_here
```

### 3. Создание базы данных

```bash
# Подключитесь к PostgreSQL
psql -U postgres

# Создайте базу данных
CREATE DATABASE car_chatbot;

# Создайте пользователя (опционально)
CREATE USER car_bot_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE car_chatbot TO car_bot_user;

# Выйдите из psql
\q
```

### 4. Применение миграций

```bash
# Применить все миграции
alembic upgrade head

# Проверить текущую версию БД
alembic current

# Посмотреть историю миграций
alembic history
```

### 5. Проверка подключения

```python
# Запустите Python shell
python

# Проверьте подключение
>>> from database.config import check_connection
>>> import asyncio
>>> asyncio.run(check_connection())
True
```

---

## 📁 Структура проекта

```
database/
├── alembic/                    # Директория Alembic
│   ├── versions/               # Файлы миграций
│   │   └── 20250109_0001_initial_schema.py
│   ├── env.py                  # Конфигурация Alembic
│   └── script.py.mako          # Шаблон для генерации миграций
│
├── models.py                   # SQLAlchemy модели
├── config.py                   # Конфигурация подключения к БД
├── alembic.ini                 # Настройки Alembic
├── requirements.txt            # Python зависимости
├── .env.example                # Пример переменных окружения
├── .env                        # Реальные переменные (не коммитится в Git!)
│
├── ARCHITECTURE.md             # Подробная документация архитектуры
└── README.md                   # Этот файл
```

---

## ⚙️ Настройка окружения

### Переменные окружения

| Переменная | Описание | По умолчанию | Обязательна |
|------------|----------|--------------|-------------|
| `DATABASE_URL` | Полный URL подключения | - | Нет¹ |
| `DB_HOST` | Хост PostgreSQL | localhost | Да |
| `DB_PORT` | Порт PostgreSQL | 5432 | Нет |
| `DB_NAME` | Имя базы данных | car_chatbot | Да |
| `DB_USER` | Пользователь БД | postgres | Да |
| `DB_PASSWORD` | Пароль БД | - | Да |
| `DB_ECHO` | Логировать SQL | false | Нет |
| `DB_POOL_SIZE` | Размер connection pool | 5 | Нет |
| `DB_MAX_OVERFLOW` | Макс. overflow connections | 10 | Нет |

¹ Если указан `DATABASE_URL`, остальные параметры игнорируются.

### Пример для production (с DATABASE_URL)

```env
DATABASE_URL=postgresql://user:password@db.example.com:5432/production_db
DB_ECHO=false
```

---

## 🔄 Работа с миграциями

### Создание новой миграции

```bash
# Автоматическая генерация на основе изменений в models.py
alembic revision --autogenerate -m "Add new table for orders"

# Ручное создание пустой миграции
alembic revision -m "Add custom index"
```

### Применение миграций

```bash
# Применить все pending миграции
alembic upgrade head

# Применить до конкретной ревизии
alembic upgrade abc123

# Применить на 1 версию вперед
alembic upgrade +1
```

### Откат миграций

```bash
# Откатить на 1 версию назад
alembic downgrade -1

# Откатить до конкретной ревизии
alembic downgrade abc123

# Откатить все миграции
alembic downgrade base
```

### Просмотр информации

```bash
# Текущая версия БД
alembic current

# История миграций
alembic history --verbose

# Показать SQL без применения (dry-run)
alembic upgrade head --sql
```

---

## 📊 Импорт данных

### Автоматический импорт (рекомендуется)

Используйте мастер-скрипт для полного автоматического импорта:

```bash
# Полный импорт для evopoliki (все этапы)
python scripts/run_full_import.py --tenant evopoliki

# Для второго tenant (пропуская создание seed data и извлечение из PDF)
python scripts/run_full_import.py --skip-seed --skip-extract --skip-clean --tenant five_deluxe
```

Мастер-скрипт автоматически выполнит:
1. ✅ Создание seed data (tenants, категории, опции, тексты бота)
2. ✅ Извлечение данных из `БД_машины.pdf`
3. ✅ Очистку и нормализацию данных
4. ✅ Импорт брендов, моделей и лекал в базу

### Ручной импорт (пошаговый)

Если нужен контроль над каждым этапом:

```bash
# Шаг 1: Создание начальных данных
python scripts/seed_data.py

# Шаг 2: Извлечение из PDF
python scripts/extract_pdf_data.py

# Шаг 3: Очистка данных
python scripts/clean_data.py

# Шаг 4: Импорт в БД
python scripts/import_to_database.py --tenant evopoliki --category eva_mats
```

### Проверка результатов

```bash
# Подключитесь к БД
psql -U postgres -d car_chatbot

# Проверьте количество записей
SELECT 'Tenants' as table, COUNT(*) FROM tenants
UNION ALL SELECT 'Brands', COUNT(*) FROM brands
UNION ALL SELECT 'Models', COUNT(*) FROM models
UNION ALL SELECT 'Patterns', COUNT(*) FROM patterns;

# Топ-5 брендов
SELECT b.name, COUNT(m.id) as models
FROM brands b
JOIN models m ON b.id = m.brand_id
GROUP BY b.name
ORDER BY models DESC
LIMIT 5;
```

Подробнее см. [scripts/README.md](./scripts/README.md) и [DATA_IMPORT_PLAN.md](./DATA_IMPORT_PLAN.md)

---

## 🛠 Полезные команды

### Сброс и пересоздание БД (ТОЛЬКО ДЛЯ РАЗРАБОТКИ!)

```bash
# Откатить все миграции
alembic downgrade base

# Применить заново
alembic upgrade head
```

### Работа с моделями в Python

```python
from database.models import Tenant, Brand, Model
from database.config import get_sync_session
from sqlalchemy import select

# Синхронная работа (для скриптов)
with get_sync_session() as session:
    tenants = session.query(Tenant).all()
    for tenant in tenants:
        print(tenant.name)

# Асинхронная работа (для приложения)
from database.config import get_async_session
import asyncio

async def get_tenants():
    async with get_async_session() as session:
        result = await session.execute(select(Tenant))
        return result.scalars().all()

asyncio.run(get_tenants())
```

### Проверка схемы БД

```bash
# Через psql
psql -U postgres -d car_chatbot -c "\dt"

# Описание таблицы
psql -U postgres -d car_chatbot -c "\d tenants"

# Список индексов
psql -U postgres -d car_chatbot -c "\di"
```

---

## 🔒 Безопасность

### Row-Level Security (RLS)

Для включения изоляции данных по tenant_id раскомментируйте соответствующие строки в миграции `20250109_0001_initial_schema.py`:

```python
op.execute('ALTER TABLE patterns ENABLE ROW LEVEL SECURITY')
op.execute('''
    CREATE POLICY tenant_isolation ON patterns
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::INTEGER)
''')
```

### Использование RLS в коде

```python
from database.config import set_tenant_context

async with get_async_session() as session:
    # Установить контекст арендатора
    await set_tenant_context(session, tenant_id=1)

    # Теперь все запросы автоматически фильтруются
    result = await session.execute(select(Pattern))
    patterns = result.scalars().all()
    # Вернет только patterns для tenant_id = 1
```

---

## 📝 Troubleshooting

### Ошибка: "could not connect to server"

```bash
# Проверьте, запущен ли PostgreSQL
sudo systemctl status postgresql  # Linux
brew services list  # macOS

# Запустите PostgreSQL
sudo systemctl start postgresql  # Linux
brew services start postgresql@15  # macOS
```

### Ошибка: "relation does not exist"

```bash
# Проверьте, применены ли миграции
alembic current

# Если нет, примените
alembic upgrade head
```

### Ошибка: "permission denied for database"

```sql
-- Выдайте права пользователю
GRANT ALL PRIVILEGES ON DATABASE car_chatbot TO your_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
```

---

## 📚 Дополнительная документация

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Подробное описание архитектуры БД
- [DATA_IMPORT_PLAN.md](./DATA_IMPORT_PLAN.md) - План импорта данных
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

---

## 🤝 Контакты

По вопросам архитектуры БД обращайтесь к команде разработки.

**Версия:** 1.0
**Дата:** 2025-01-09
