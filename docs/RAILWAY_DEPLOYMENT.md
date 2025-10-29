# Railway Deployment Guide

Пошаговое руководство по развертыванию WhatsApp Bot Platform на Railway.

---

## Предварительные требования

- GitHub аккаунт с доступом к репозиторию
- Railway аккаунт (https://railway.app)
- PostgreSQL база данных (можно создать в Railway)
- GreenAPI аккаунт с настроенными инстансами
- OpenAI API ключи (опционально, для AI режима)

---

## Шаг 1: Создание проекта в Railway

### 1.1. Подключение репозитория

1. Войдите в Railway Dashboard
2. Нажмите **"New Project"**
3. Выберите **"Deploy from GitHub repo"**
4. Найдите `MonsterDEVZ/whatsapp-bot-platform`
5. Нажмите **"Deploy Now"**

### 1.2. Автоматическое развертывание

Railway автоматически:
- Обнаружит `Dockerfile`
- Соберёт Docker образ
- Запустит контейнер

**Первый деплой займёт 2-3 минуты.**

---

## Шаг 2: Создание PostgreSQL базы данных

### 2.1. Добавление сервиса PostgreSQL

1. В проекте нажмите **"+ New"**
2. Выберите **"Database" → "PostgreSQL"**
3. Railway автоматически создаст базу и переменные окружения

### 2.2. Подключение к WhatsApp сервису

1. Откройте настройки WhatsApp сервиса
2. Перейдите в **"Variables"**
3. Добавьте ссылку на PostgreSQL:
   - Нажмите **"+ Reference"**
   - Выберите PostgreSQL сервис
   - Выберите все переменные (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`)

### 2.3. Переименование переменных

Railway создаёт переменные с префиксом `PG`. Нужно создать алиасы:

```bash
DB_HOST=${{Postgres.PGHOST}}
DB_PORT=${{Postgres.PGPORT}}
DB_NAME=${{Postgres.PGDATABASE}}
DB_USER=${{Postgres.PGUSER}}
DB_PASSWORD=${{Postgres.PGPASSWORD}}
```

---

## Шаг 3: Настройка переменных окружения

### 3.1. Tenant 1: EVOPOLIKI

```bash
# WhatsApp (GreenAPI)
EVOPOLIKI_WHATSAPP_INSTANCE_ID=7103XXXXXX
EVOPOLIKI_WHATSAPP_API_TOKEN=abc123...
EVOPOLIKI_WHATSAPP_PHONE_NUMBER=+996XXXXXXXXX  # опционально

# AI режим
EVOPOLIKI_ENABLE_DIALOG_MODE=true
EVOPOLIKI_OPENAI_API_KEY=sk-proj-...
EVOPOLIKI_OPENAI_ASSISTANT_ID=asst_...
```

### 3.2. Tenant 2: FIVE_DELUXE

```bash
# WhatsApp (GreenAPI)
FIVE_DELUXE_WHATSAPP_INSTANCE_ID=7104XXXXXX
FIVE_DELUXE_WHATSAPP_API_TOKEN=xyz789...
FIVE_DELUXE_WHATSAPP_PHONE_NUMBER=+996YYYYYYYYY  # опционально

# IVR режим (без AI)
FIVE_DELUXE_ENABLE_DIALOG_MODE=false
```

### 3.3. Опциональные переменные

```bash
# Airtable (для сохранения заявок)
AIRTABLE_API_KEY=key...
AIRTABLE_BASE_ID=app...
AIRTABLE_TABLE_NAME=Заявки с ботов

# Порт (Railway автоматически устанавливает)
PORT=8000
```

---

## Шаг 4: Настройка вебхука GreenAPI

После успешного деплоя получите URL вашего сервиса:

1. В Railway Dashboard откройте WhatsApp сервис
2. Перейдите в **"Settings" → "Networking"**
3. Скопируйте **Public URL** (например: `https://whatsapp-bot-platform-production.up.railway.app`)

### 4.1. Настройка вебхука для EVOPOLIKI

1. Откройте GreenAPI кабинет для инстанса EVOPOLIKI
2. Перейдите в **"API" → "Webhook"**
3. Установите URL:
   ```
   https://your-app.railway.app/webhook
   ```
4. Выберите события:
   - ✅ `incomingMessageReceived`
5. Сохраните настройки

### 4.2. Настройка вебхука для FIVE_DELUXE

Повторите для инстанса FIVE_DELUXE (используйте **тот же URL**).

---

## Шаг 5: Инициализация базы данных

### 5.1. Подключение к Railway PostgreSQL

```bash
# Установите Railway CLI
npm install -g @railway/cli

# Войдите в Railway
railway login

# Подключитесь к проекту
railway link

# Откройте PostgreSQL shell
railway run psql
```

### 5.2. Запуск миграций

```bash
# В контейнере приложения
railway run alembic upgrade head
```

Или вручную через PostgreSQL client:

```sql
-- Создание таблиц (см. packages/core/database/models.py)
-- Миграции в packages/core/database/alembic/versions/
```

---

## Шаг 6: Проверка работы

### 6.1. Health Check

```bash
curl https://your-app.railway.app/

# Ожидаемый ответ:
{
  "status": "ok",
  "service": "WhatsApp Gateway",
  "version": "1.0.0",
  "active_tenants": 2
}
```

### 6.2. Проверка логов

```bash
# Через Railway CLI
railway logs

# Или в Railway Dashboard
# Settings → Deployments → View Logs
```

Ожидаемые логи при старте:

```
✅ Loaded WhatsApp config for evopoliki (instance: 7103XXXXXX)
✅ AssistantManager initialized for evopoliki (Assistant ID: asst_...)
✅ Loaded WhatsApp config for five_deluxe (instance: 7104XXXXXX)
📱 Total active WhatsApp instances: 2
🤖 Total active AI Assistants: 1
🚀 Starting WhatsApp Gateway...
```

### 6.3. Тест сообщения

1. Отправьте сообщение в WhatsApp EVOPOLIKI: `Привет`
2. Проверьте логи:
   ```bash
   railway logs | grep "evopoliki" -A5
   ```
3. Ожидаемый ответ:
   ```
   💬 Message from Иван (79001234567@c.us): Привет
   🔀 [ROUTING] evopoliki: AI mode
   🤖 [ROUTING] Dialog mode ENABLED -> AI Assistant flow
   ✅ [SEND_MESSAGE] Successfully sent response
   ```

---

## Шаг 7: Мониторинг и масштабирование

### 7.1. Мониторинг

Railway предоставляет метрики:
- CPU usage
- Memory usage
- Network traffic
- Response times

Доступ: **Settings → Metrics**

### 7.2. Алерты

Настройте уведомления о сбоях:
1. **Settings → Alerts**
2. Добавьте webhook для Slack/Discord/Telegram

### 7.3. Масштабирование

Railway автоматически масштабирует приложение.

Для увеличения ресурсов:
1. **Settings → Resources**
2. Выберите план (Hobby → Pro)

---

## Шаг 8: CI/CD (автоматический деплой)

Railway автоматически деплоит при push в `main` ветку.

### 8.1. Триггеры деплоя

- Push в `main` → автодеплой
- Pull Request → preview deployment (опционально)

### 8.2. Откат деплоя

Если деплой сломал продакшн:

1. **Settings → Deployments**
2. Найдите рабочий деплой
3. Нажмите **"Redeploy"**

---

## Переменные окружения (полный список)

### Обязательные (для каждого tenant)

```bash
# EVOPOLIKI
EVOPOLIKI_WHATSAPP_INSTANCE_ID=7103XXXXXX
EVOPOLIKI_WHATSAPP_API_TOKEN=abc123...

# FIVE_DELUXE
FIVE_DELUXE_WHATSAPP_INSTANCE_ID=7104XXXXXX
FIVE_DELUXE_WHATSAPP_API_TOKEN=xyz789...
```

### Опциональные (для AI режима)

```bash
EVOPOLIKI_ENABLE_DIALOG_MODE=true
EVOPOLIKI_OPENAI_API_KEY=sk-proj-...
EVOPOLIKI_OPENAI_ASSISTANT_ID=asst_...
```

### База данных (автоматически из PostgreSQL сервиса)

```bash
DB_HOST=${{Postgres.PGHOST}}
DB_PORT=${{Postgres.PGPORT}}
DB_NAME=${{Postgres.PGDATABASE}}
DB_USER=${{Postgres.PGUSER}}
DB_PASSWORD=${{Postgres.PGPASSWORD}}
```

---

## Troubleshooting

### Проблема: Бот не отвечает

**Решение:**
1. Проверьте логи: `railway logs | grep ERROR`
2. Проверьте вебхук в GreenAPI (URL должен быть доступен)
3. Проверьте переменные окружения (instance_id, api_token)

### Проблема: AI не работает

**Решение:**
1. Проверьте `ENABLE_DIALOG_MODE=true`
2. Проверьте OpenAI API key валиден
3. Проверьте Assistant ID существует в OpenAI dashboard
4. Логи: `railway logs | grep "AI\|ROUTING"`

### Проблема: Database connection error

**Решение:**
1. Проверьте PostgreSQL сервис работает
2. Проверьте переменные `DB_*` установлены
3. Проверьте Reference на PostgreSQL сервис

### Проблема: Deployment failed

**Решение:**
1. Проверьте Dockerfile синтаксис
2. Проверьте requirements.txt валиден
3. Логи билда: **Settings → Deployments → Build Logs**

---

## Полезные команды Railway CLI

```bash
# Просмотр логов
railway logs

# Просмотр переменных
railway variables

# Установка переменной
railway variables set KEY=VALUE

# Открыть dashboard
railway open

# Подключение к PostgreSQL
railway run psql

# Выполнение команды в контейнере
railway run python main.py
```

---

## Best Practices

1. **Используйте Railway PostgreSQL** вместо внешней БД
2. **Настройте автобэкапы** базы данных
3. **Мониторьте логи** регулярно (особенно ERROR/CRITICAL)
4. **Не коммитьте .env** файлы в Git
5. **Используйте Railway Secrets** для чувствительных данных
6. **Настройте алерты** для critical errors
7. **Тестируйте в staging** перед деплоем в production

---

## Следующие шаги

✅ Проект задеплоен на Railway
✅ Вебхуки настроены в GreenAPI
✅ Боты отвечают на сообщения

Теперь можно:
- Добавить новых tenants
- Настроить мониторинг
- Интегрировать с CRM
- Добавить аналитику

---

## Support

Проблемы с деплоем? Создайте issue:
https://github.com/MonsterDEVZ/whatsapp-bot-platform/issues
