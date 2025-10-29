# Environment Variables Guide

Полное руководство по настройке переменных окружения для WhatsApp Bot Platform.

---

## 📁 Файлы окружения

Проект содержит 3 примера .env файлов:

| Файл | Назначение |
|------|------------|
| `.env.example` | Основной шаблон для всех переменных |
| `.env.local.example` | Для локальной разработки |
| `.env.production.example` | Для Railway/production деплоя |

---

## 🚀 Быстрый старт

### Локальная разработка

```bash
# 1. Скопируйте пример
cp .env.local.example .env

# 2. Отредактируйте .env файл
nano .env

# 3. Запустите PostgreSQL (Docker)
docker run --name whatsapp-postgres \
  -e POSTGRES_DB=whatsapp_bot_dev \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  -d postgres:15

# 4. Запустите сервер
python main.py
```

### Production (Railway)

```bash
# 1. Скопируйте содержимое .env.production.example
cat .env.production.example

# 2. Вставьте в Railway Dashboard:
# Project → Settings → Variables → Raw Editor

# 3. Замените плейсхолдеры реальными значениями

# 4. Deploy автоматически
```

---

## 📋 Описание переменных

### Database (обязательно)

| Переменная | Пример | Описание |
|------------|--------|----------|
| `DB_HOST` | `localhost` | PostgreSQL хост |
| `DB_PORT` | `5432` | PostgreSQL порт |
| `DB_NAME` | `whatsapp_bot` | Название базы данных |
| `DB_USER` | `postgres` | Пользователь БД |
| `DB_PASSWORD` | `your_password` | Пароль БД |

**Railway:** Используйте reference на PostgreSQL сервис:
```bash
DB_HOST=${{Postgres.PGHOST}}
DB_PORT=${{Postgres.PGPORT}}
DB_NAME=${{Postgres.PGDATABASE}}
DB_USER=${{Postgres.PGUSER}}
DB_PASSWORD=${{Postgres.PGPASSWORD}}
```

---

### WhatsApp (GreenAPI) - обязательно для каждого tenant

#### Формат переменной:
```
{TENANT}_WHATSAPP_{PARAMETER}
```

#### EVOPOLIKI

| Переменная | Пример | Где получить |
|------------|--------|--------------|
| `EVOPOLIKI_WHATSAPP_INSTANCE_ID` | `7103XXXXXX` | GreenAPI → Instance ID |
| `EVOPOLIKI_WHATSAPP_API_TOKEN` | `abc123...` | GreenAPI → API Token |
| `EVOPOLIKI_WHATSAPP_PHONE_NUMBER` | `+996XXXXXXXXX` | Ваш WhatsApp номер (опц.) |
| `EVOPOLIKI_WHATSAPP_API_URL` | `https://7103.api.green-api.com` | GreenAPI API URL |

#### FIVE_DELUXE

| Переменная | Пример | Где получить |
|------------|--------|--------------|
| `FIVE_DELUXE_WHATSAPP_INSTANCE_ID` | `7104XXXXXX` | GreenAPI → Instance ID |
| `FIVE_DELUXE_WHATSAPP_API_TOKEN` | `xyz789...` | GreenAPI → API Token |
| `FIVE_DELUXE_WHATSAPP_PHONE_NUMBER` | `+996YYYYYYYYY` | Ваш WhatsApp номер (опц.) |
| `FIVE_DELUXE_WHATSAPP_API_URL` | `https://7104.api.green-api.com` | GreenAPI API URL |

---

### AI Configuration (OpenAI) - опционально

#### EVOPOLIKI (AI режим включен)

| Переменная | Пример | Где получить |
|------------|--------|--------------|
| `EVOPOLIKI_ENABLE_DIALOG_MODE` | `true` | `true` для AI, `false` для IVR |
| `EVOPOLIKI_OPENAI_API_KEY` | `sk-proj-xxx...` | https://platform.openai.com/api-keys |
| `EVOPOLIKI_OPENAI_ASSISTANT_ID` | `asst_xxx...` | https://platform.openai.com/assistants |

#### FIVE_DELUXE (IVR режим)

| Переменная | Значение | Описание |
|------------|----------|----------|
| `FIVE_DELUXE_ENABLE_DIALOG_MODE` | `false` | IVR режим без AI |

---

### Airtable Integration (опционально)

| Переменная | Пример | Описание |
|------------|--------|----------|
| `AIRTABLE_API_KEY` | `keyXXXXXXXXXXXXXX` | Airtable API key |
| `AIRTABLE_BASE_ID` | `appXXXXXXXXXXXXXX` | Airtable Base ID |
| `AIRTABLE_TABLE_NAME` | `Заявки с ботов` | Название таблицы |

**Где получить:**
1. Airtable → Account → Generate API key
2. Airtable → Base → Help → API documentation → Base ID

---

### Server Configuration

| Переменная | Default | Описание |
|------------|---------|----------|
| `PORT` | `8000` | Порт сервера (Railway устанавливает автоматически) |
| `DEBUG` | `false` | Debug режим (`true`/`false`) |

---

## 🔑 Получение credentials

### 1. GreenAPI (WhatsApp)

1. Зарегистрируйтесь на https://green-api.com
2. Создайте новый instance для каждого клиента
3. Скопируйте:
   - **Instance ID** (7-значное число)
   - **API Token** (длинная строка)
4. Привяжите WhatsApp номер к instance
5. Настройте webhook URL (после деплоя)

### 2. OpenAI (AI Assistant)

1. Создайте аккаунт на https://platform.openai.com
2. Сгенерируйте API key:
   - Dashboard → API Keys → Create new secret key
   - Формат: `sk-proj-xxxxxxxxxxxxxxxx`
3. Создайте Assistant:
   - Dashboard → Assistants → Create
   - Загрузите FAQ файл (knowledge base)
   - Скопируйте Assistant ID: `asst_xxxxxxxxxxxxxxxx`

### 3. PostgreSQL

**Локально (Docker):**
```bash
docker run --name whatsapp-postgres \
  -e POSTGRES_DB=whatsapp_bot \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  -d postgres:15
```

**Railway:**
1. Project → New → Database → PostgreSQL
2. Railway автоматически создаст переменные
3. Используйте reference в main сервисе

### 4. Airtable (опционально)

1. Создайте аккаунт на https://airtable.com
2. Создайте Base для заявок
3. Получите API key: Account → Generate API key
4. Получите Base ID: Base → Help → API documentation

---

## 🔒 Безопасность

### ❌ НЕ делайте:

- ❌ Не коммитьте `.env` файлы в Git
- ❌ Не публикуйте credentials в публичных репозиториях
- ❌ Не используйте одинаковые пароли для всех окружений
- ❌ Не храните токены в коде

### ✅ ДЕЛАЙТЕ:

- ✅ Используйте `.env.example` как шаблон
- ✅ Добавьте `.env` в `.gitignore`
- ✅ Используйте разные credentials для dev/prod
- ✅ Ротируйте токены регулярно
- ✅ Используйте Railway Secrets для production

---

## 🧪 Проверка переменных

### Локально

```bash
# Проверить что .env загружен
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('DB_HOST'))"

# Проверить все EVOPOLIKI переменные
env | grep EVOPOLIKI
```

### Railway

```bash
# Просмотр всех переменных
railway variables

# Проверка конкретной переменной
railway variables | grep EVOPOLIKI_ENABLE_DIALOG_MODE
```

---

## 📝 Примеры .env файлов

### Минимальный (только IVR, без AI)

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=whatsapp_bot
DB_USER=postgres
DB_PASSWORD=postgres

# EVOPOLIKI (IVR режим)
EVOPOLIKI_WHATSAPP_INSTANCE_ID=7103000000
EVOPOLIKI_WHATSAPP_API_TOKEN=test_token
EVOPOLIKI_ENABLE_DIALOG_MODE=false
```

### Полный (с AI для обоих tenants)

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=whatsapp_bot
DB_USER=postgres
DB_PASSWORD=postgres

# EVOPOLIKI (AI режим)
EVOPOLIKI_WHATSAPP_INSTANCE_ID=7103XXXXXX
EVOPOLIKI_WHATSAPP_API_TOKEN=token1
EVOPOLIKI_ENABLE_DIALOG_MODE=true
EVOPOLIKI_OPENAI_API_KEY=sk-proj-xxx
EVOPOLIKI_OPENAI_ASSISTANT_ID=asst_xxx

# FIVE_DELUXE (AI режим)
FIVE_DELUXE_WHATSAPP_INSTANCE_ID=7104XXXXXX
FIVE_DELUXE_WHATSAPP_API_TOKEN=token2
FIVE_DELUXE_ENABLE_DIALOG_MODE=true
FIVE_DELUXE_OPENAI_API_KEY=sk-proj-yyy
FIVE_DELUXE_OPENAI_ASSISTANT_ID=asst_yyy

# Airtable
AIRTABLE_API_KEY=keyXXXXXX
AIRTABLE_BASE_ID=appXXXXXX
AIRTABLE_TABLE_NAME=Заявки с ботов
```

---

## 🐛 Troubleshooting

### Ошибка: "Database connection failed"

**Причина:** Неверные DB_* переменные

**Решение:**
```bash
# Проверить переменные
echo $DB_HOST $DB_PORT $DB_NAME

# Проверить что PostgreSQL запущен
docker ps | grep postgres

# Проверить подключение
psql -h localhost -p 5432 -U postgres -d whatsapp_bot
```

### Ошибка: "Unknown instance_id"

**Причина:** Instance ID не найден в переменных окружения

**Решение:**
```bash
# Проверить переменные
env | grep WHATSAPP_INSTANCE_ID

# Должно вывести:
# EVOPOLIKI_WHATSAPP_INSTANCE_ID=7103XXXXXX
# FIVE_DELUXE_WHATSAPP_INSTANCE_ID=7104XXXXXX
```

### Ошибка: "OpenAI API key not found"

**Причина:** AI режим включен, но ключ не установлен

**Решение:**
```bash
# Проверить enable_dialog_mode
env | grep ENABLE_DIALOG_MODE

# Если true, проверить ключ
env | grep OPENAI_API_KEY

# Установить ключ
echo 'EVOPOLIKI_OPENAI_API_KEY=sk-proj-xxx' >> .env
```

---

## 📚 Дополнительные ресурсы

- [GreenAPI Documentation](https://green-api.com/docs/)
- [OpenAI Assistants Guide](https://platform.openai.com/docs/assistants/overview)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)

---

## ❓ FAQ

**Q: Можно ли использовать один OpenAI ключ для всех tenants?**

A: Да, можно использовать глобальный `OPENAI_API_KEY` вместо tenant-specific. Но рекомендуется использовать отдельные ключи для изоляции.

**Q: Нужен ли WHATSAPP_PHONE_NUMBER?**

A: Нет, это опциональный параметр. GreenAPI работает без него.

**Q: Что будет если не установить ENABLE_DIALOG_MODE?**

A: По умолчанию будет `false` (IVR режим).

**Q: Как добавить нового tenant?**

A: Добавьте переменные с префиксом нового tenant (например, `NEW_CLIENT_WHATSAPP_INSTANCE_ID`) и добавьте tenant в `apps/whatsapp_gateway/main.py:154`.

---

**Документация актуальна на:** 29 октября 2025
