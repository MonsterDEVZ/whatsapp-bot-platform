# Quick Start Guide

Быстрый старт для локальной разработки.

## 1. Клонирование репозитория

```bash
git clone https://github.com/MonsterDEVZ/whatsapp-bot-platform.git
cd whatsapp-bot-platform
```

## 2. Установка зависимостей

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Настройка .env (локально)

Создайте файл `.env` в корне проекта:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=whatsapp_bot
DB_USER=postgres
DB_PASSWORD=your_password

# EVOPOLIKI
EVOPOLIKI_WHATSAPP_INSTANCE_ID=7103XXXXXX
EVOPOLIKI_WHATSAPP_API_TOKEN=abc123...
EVOPOLIKI_ENABLE_DIALOG_MODE=true
EVOPOLIKI_OPENAI_API_KEY=sk-proj-...
EVOPOLIKI_OPENAI_ASSISTANT_ID=asst_...

# FIVE_DELUXE
FIVE_DELUXE_WHATSAPP_INSTANCE_ID=7104XXXXXX
FIVE_DELUXE_WHATSAPP_API_TOKEN=xyz789...
FIVE_DELUXE_ENABLE_DIALOG_MODE=false
```

## 4. Запуск PostgreSQL (Docker)

```bash
docker run --name whatsapp-postgres \
  -e POSTGRES_DB=whatsapp_bot \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  -d postgres:15
```

## 5. Инициализация базы данных

```bash
# Миграции
cd packages/core/database
alembic upgrade head
```

## 6. Запуск сервера

```bash
python main.py
```

Сервер запустится на `http://localhost:8000`

## 7. Настройка ngrok (для тестирования вебхуков)

```bash
# Установка ngrok
brew install ngrok  # macOS
# или скачайте с https://ngrok.com

# Запуск туннеля
ngrok http 8000
```

Скопируйте URL (например `https://abc123.ngrok.io`) и установите в GreenAPI:
```
https://abc123.ngrok.io/webhook
```

## 8. Тестирование

Отправьте сообщение в WhatsApp: **"Привет"**

Проверьте логи сервера:
```
💬 Message from ... : Привет
🔀 [ROUTING] evopoliki: AI mode
✅ [SEND_MESSAGE] Successfully sent response
```

---

## Деплой на Railway

См. [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md)

## Полная документация

См. [README.md](README.md)
