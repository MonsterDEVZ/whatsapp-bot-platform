# WhatsApp Bot Platform - Project Summary

## 📦 Репозиторий

**GitHub:** https://github.com/MonsterDEVZ/whatsapp-bot-platform

**Организация:** MonsterDEVZ

**Ветка:** main

---

## 🏗️ Структура проекта

```
whatsapp_platform/
├── main.py                      # Точка входа (FastAPI server)
├── requirements.txt             # Python зависимости
├── Dockerfile                   # Docker конфигурация
├── Procfile                     # Railway deployment
├── railway.json                 # Railway настройки
│
├── packages/core/               # Общий код (из chatbot_platform)
│   ├── config.py                # Tenant-scoped конфигурация
│   ├── ai/                      # OpenAI интеграция
│   ├── db/                      # Database queries
│   ├── handlers/                # Message handlers
│   ├── keyboards/               # UI components
│   ├── locales/                 # i18n (ru, ky)
│   │   ├── evopoliki/
│   │   └── five_deluxe/
│   ├── memory.py                # Dialog history
│   └── services/                # Airtable, etc.
│
├── apps/whatsapp_gateway/       # WhatsApp-specific код
│   ├── main.py                  # FastAPI app + webhook handler
│   ├── whatsapp_handlers.py    # WhatsApp message handlers
│   ├── ivr_handlers_5deluxe.py # IVR меню для Five Deluxe
│   ├── state_manager.py         # FSM state management
│   └── smart_input_handler.py  # AI input processing
│
└── docs/
    ├── RAILWAY_DEPLOYMENT.md    # Деплой на Railway
    └── (другие MD файлы)
```

---

## 🚀 Что было сделано

### 1. Перенесена WhatsApp часть из chatbot_platform

✅ Скопирован `packages/core` (с tenant isolation fixes)
✅ Скопирован `apps/whatsapp_gateway`
✅ Создан standalone entry point (`main.py`)

### 2. Настроена инфраструктура

✅ `Dockerfile` для контейнеризации
✅ `requirements.txt` с минимальными зависимостями
✅ `Procfile` для Railway/Heroku
✅ `railway.json` для автодеплоя
✅ `.gitignore` и `.dockerignore`

### 3. Документация

✅ `README.md` - полное описание проекта
✅ `QUICK_START.md` - быстрый старт для разработки
✅ `docs/RAILWAY_DEPLOYMENT.md` - деплой на Railway
✅ Документация из `apps/whatsapp_gateway/` сохранена

### 4. GitHub репозиторий

✅ Создан в организации MonsterDEVZ
✅ Первый commit с полной кодовой базой
✅ Автоматический push в main
✅ Публичный репозиторий

---

## 🔧 Технологии

| Технология | Версия | Назначение |
|------------|--------|------------|
| Python | 3.13+ | Основной язык |
| FastAPI | 0.115.6 | Web framework |
| SQLAlchemy | 2.0.43 | ORM для PostgreSQL |
| OpenAI | 1.59.7 | AI ассистент |
| httpx | 0.28.1 | HTTP клиент (GreenAPI) |
| uvicorn | 0.34.0 | ASGI сервер |

---

## 🎯 Особенности

### Multi-tenant архитектура

- Каждый клиент имеет изолированную конфигурацию
- Tenant-specific переменные окружения
- Независимые AI ассистенты
- Раздельные локализации (ru/ky)

### AI-powered режим

- OpenAI Assistants API
- Dialog memory (история диалогов)
- Smart input handling
- JSON response parsing

### IVR fallback

- Традиционное меню при `ENABLE_DIALOG_MODE=false`
- FSM state management
- Пошаговые сценарии (выбор товара, сбор контактов)

### Database integration

- PostgreSQL с async поддержкой
- Alembic миграции
- Multi-tenant data isolation

---

## 🌐 Деплой

### Railway (рекомендуется)

1. Подключить GitHub репозиторий
2. Добавить PostgreSQL сервис
3. Настроить переменные окружения
4. Автоматический деплой при push

**Инструкция:** [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md)

### Docker

```bash
docker build -t whatsapp-bot .
docker run -p 8000:8000 whatsapp-bot
```

---

## 📝 Environment Variables (примеры)

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=whatsapp_bot
DB_USER=postgres
DB_PASSWORD=xxx

# EVOPOLIKI (AI режим)
EVOPOLIKI_WHATSAPP_INSTANCE_ID=7103XXXXXX
EVOPOLIKI_WHATSAPP_API_TOKEN=abc123
EVOPOLIKI_ENABLE_DIALOG_MODE=true
EVOPOLIKI_OPENAI_API_KEY=sk-proj-xxx
EVOPOLIKI_OPENAI_ASSISTANT_ID=asst_xxx

# FIVE_DELUXE (IVR режим)
FIVE_DELUXE_WHATSAPP_INSTANCE_ID=7104XXXXXX
FIVE_DELUXE_WHATSAPP_API_TOKEN=xyz789
FIVE_DELUXE_ENABLE_DIALOG_MODE=false
```

---

## 📊 Статистика проекта

| Метрика | Значение |
|---------|----------|
| Файлов Python | 103 |
| Строк кода | ~25,885 |
| Tenants | 2 (evopoliki, five_deluxe) |
| Языки | Русский, Кыргызский |
| Commits | 3 |

---

## 🔗 Ссылки

- **GitHub:** https://github.com/MonsterDEVZ/whatsapp-bot-platform
- **Organization:** https://github.com/MonsterDEVZ
- **Родительский проект:** https://github.com/MonsterDEVZ/chatbot-platform

---

## 📞 Support

Issues: https://github.com/MonsterDEVZ/whatsapp-bot-platform/issues

---

**Дата создания:** 29 октября 2025
**Автор:** MonsterDEVZ Team
**Статус:** ✅ Ready for production
