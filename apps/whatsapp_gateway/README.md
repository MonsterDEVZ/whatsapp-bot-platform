# WhatsApp Gateway

Multi-tenant WhatsApp bot gateway для приема и обработки сообщений от GreenAPI.

## 📋 Описание

WhatsApp Gateway - это FastAPI веб-сервер, который:
- Принимает входящие webhook'и от GreenAPI
- Определяет tenant (evopoliki, five_deluxe) по instance_id
- Использует общее ядро платформы (Config, локализация, база данных)
- Отправляет ответы пользователям через GreenAPI API

## 🏗️ Архитектура

```
GreenAPI Webhook → WhatsApp Gateway → Config + i18n → GreenAPI SendMessage API
                         ↓
                    PostgreSQL
```

## 🚀 Быстрый старт

### Локальная разработка

1. Установите зависимости:
```bash
cd chatbot_platform
pip install -r requirements.txt
pip install -r apps/whatsapp_gateway/requirements.txt
```

2. Настройте переменные окружения в `apps/evopoliki/.env`:
```env
EVOPOLIKI_WHATSAPP_INSTANCE_ID=7105335266
EVOPOLIKI_WHATSAPP_API_TOKEN=your_token_here
EVOPOLIKI_WHATSAPP_API_URL=https://7105.api.greenapi.com
EVOPOLIKI_WHATSAPP_PHONE_NUMBER=+996...
```

3. Запустите сервер:
```bash
python apps/whatsapp_gateway/main.py
```

4. Проверьте работу:
```bash
curl http://localhost:8000/
```

### Production Deployment

См. [DEPLOYMENT.md](DEPLOYMENT.md) для инструкций по развертыванию на Railway.

## 📚 Документация

- [DEPLOYMENT.md](DEPLOYMENT.md) - Инструкции по развертыванию на Railway
- [GREENAPI_SETUP.md](GREENAPI_SETUP.md) - Настройка GreenAPI webhook

## 🔧 Конфигурация

### Переменные окружения

Для каждого tenant нужны следующие переменные:

```env
{TENANT}_WHATSAPP_INSTANCE_ID - ID инстанса GreenAPI
{TENANT}_WHATSAPP_API_TOKEN - API токен GreenAPI
{TENANT}_WHATSAPP_API_URL - URL API GreenAPI
{TENANT}_WHATSAPP_PHONE_NUMBER - Номер телефона WhatsApp
```

Где `{TENANT}` = `EVOPOLIKI` или `FIVE_DELUXE`

### Конфигурация сервера

```env
WHATSAPP_GATEWAY_PORT=8000 - Порт для FastAPI сервера
```

## 🧪 Тестирование

### Health Check

```bash
curl http://localhost:8000/
```

Ожидаемый ответ:
```json
{
  "status": "ok",
  "service": "WhatsApp Gateway",
  "version": "1.0.0",
  "active_tenants": 1
}
```

### Тест webhook

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "typeWebhook": "incomingMessageReceived",
    "instanceData": {
      "idInstance": "7105335266"
    },
    "messageData": {
      "typeMessage": "textMessage",
      "textMessageData": {
        "textMessage": "Привет"
      },
      "senderData": {
        "chatId": "79001234567@c.us",
        "senderName": "Test User"
      }
    }
  }'
```

## 📁 Структура файлов

```
apps/whatsapp_gateway/
├── main.py              # FastAPI приложение
├── requirements.txt     # Python зависимости
├── Dockerfile          # Docker образ
├── railway.toml        # Railway конфигурация
├── README.md           # Этот файл
├── DEPLOYMENT.md       # Инструкции по deployment
└── GREENAPI_SETUP.md   # Настройка GreenAPI
```

## 🔄 API Endpoints

### `GET /`
Health check endpoint

**Response:**
```json
{
  "status": "ok",
  "service": "WhatsApp Gateway",
  "version": "1.0.0",
  "active_tenants": 1
}
```

### `POST /webhook`
Webhook endpoint для GreenAPI

**Request Body:** GreenAPI webhook payload

**Response:**
```json
{
  "status": "ok"
}
```

## 🐛 Troubleshooting

### Ошибка: ModuleNotFoundError: No module named 'packages'

Убедитесь, что вы запускаете приложение из корня проекта или что `sys.path` настроен правильно.

### Ошибка: Unknown instance_id

Проверьте, что переменная `{TENANT}_WHATSAPP_INSTANCE_ID` установлена правильно и совпадает с instance_id из webhook.

### Webhook не приходит

1. Проверьте настройки GreenAPI
2. Убедитесь, что webhook URL правильный
3. Проверьте, что сервер доступен публично (для production)

## 📝 Логи

Сервер логирует все важные события:

```
📨 Received webhook: {...}
🏢 Tenant identified: evopoliki
💬 Message from [name] ([phone]): [text]
✅ Sent welcome message to [name]
```

## 🔐 Безопасность

- ✅ Все токены и пароли хранятся в переменных окружения
- ✅ .env файлы добавлены в .gitignore
- ✅ Используется HTTPS для production
- ✅ Валидация входящих данных

## 🚧 Roadmap

- [x] Базовый прием webhook'ов
- [x] Отправка приветственного сообщения
- [ ] Обработка команд и меню
- [ ] Интеграция с каталогом авто
- [ ] Обработка медиа-файлов
- [ ] Сохранение истории диалогов в БД

## 📄 Лицензия

Proprietary - Evopoliki & Five Deluxe
