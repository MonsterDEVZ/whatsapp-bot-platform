# Настройка GreenAPI Webhook

## Предварительные требования

✅ WhatsApp Gateway успешно развернут на Railway
✅ Получен публичный URL (например: `https://whatsapp-gateway-production.up.railway.app`)
✅ Сервис запущен и health check проходит

## Шаг 1: Войдите в личный кабинет GreenAPI

1. Откройте https://console.green-api.com
2. Войдите в ваш аккаунт
3. Выберите инстанс **7105335266** (Instance 7105335266 - подключи вотсапп)

## Шаг 2: Настройка Webhook URL

### 2.1 Перейдите в настройки инстанса

1. В списке инстансов найдите **7105335266**
2. Нажмите на кнопку **"Настройки"** или **"Settings"**
3. Найдите раздел **"Webhooks"** или **"Вебхуки"**

### 2.2 Установите URL вебхука

В поле **"Webhook URL"** или **"URL вебхука"** введите:

```
https://your-railway-url.up.railway.app/webhook
```

**Пример:**
```
https://whatsapp-gateway-production.up.railway.app/webhook
```

⚠️ **ВАЖНО:**
- URL должен начинаться с `https://` (не `http://`)
- Endpoint должен быть `/webhook` (без tenant_slug в пути)
- Не добавляйте слэш в конце URL

### 2.3 Включите необходимые типы вебхуков

Найдите список типов вебхуков и включите следующие:

✅ **incomingMessageReceived** - входящие сообщения от пользователей
✅ **outgoingMessageStatus** - статусы отправленных сообщений (опционально)
✅ **deviceInfo** - информация об устройстве (опционально)

**Минимально необходимо включить:** `incomingMessageReceived`

### 2.4 Сохраните настройки

Нажмите кнопку **"Сохранить"** или **"Save"**

## Шаг 3: Проверка настроек через API (опционально)

Вы можете проверить настройки через API:

```bash
curl "https://7105.api.greenapi.com/waInstance7105335266/getSettings/5f59dcf72e9641709a36a9b2217e089235e68cb92a7b4f2197"
```

В ответе должно быть:
```json
{
  "webhookUrl": "https://your-railway-url.up.railway.app/webhook",
  "incomingWebhook": "yes",
  ...
}
```

## Шаг 4: Установка webhook через API (альтернативный способ)

Если не получается через UI, можете настроить через API:

```bash
curl -X POST "https://7105.api.greenapi.com/waInstance7105335266/setSettings/5f59dcf72e9641709a36a9b2217e089235e68cb92a7b4f2197" \
  -H "Content-Type: application/json" \
  -d '{
    "webhookUrl": "https://your-railway-url.up.railway.app/webhook",
    "incomingWebhook": "yes",
    "outgoingWebhook": "yes"
  }'
```

## Шаг 5: Тестирование webhook

### 5.1 Отправьте тестовое сообщение

1. Откройте WhatsApp на телефоне
2. Найдите чат с вашим бизнес-номером (привязанным к инстансу 7105335266)
3. Отправьте любое текстовое сообщение, например: "Привет"

### 5.2 Проверьте логи на Railway

1. Откройте Railway Dashboard
2. Перейдите в сервис **whatsapp-gateway**
3. Откройте вкладку **"Deployments"** → последний deployment → **"View Logs"**

Вы должны увидеть в логах:

```
📨 Received webhook: {...}
🏢 Tenant identified: evopoliki
💬 Message from [Ваше имя] ([ваш номер]): Привет
✅ Sent welcome message to [Ваше имя]
```

### 5.3 Проверьте ответ бота

В WhatsApp должно прийти приветственное сообщение из локализации evopoliki:

```
🚗 Добро пожаловать в Evopoliki!

Мы рады приветствовать вас в нашем автосалоне...
```

## Troubleshooting

### Проблема: Webhook не приходит

**Решение:**
1. Убедитесь, что URL webhook правильный и доступен
2. Проверьте, что в настройках GreenAPI включен `incomingWebhook`
3. Проверьте логи Railway - возможно webhook приходит, но есть ошибка обработки
4. Попробуйте отправить тестовый webhook через API:

```bash
curl -X POST "https://your-railway-url.up.railway.app/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "typeWebhook": "incomingMessageReceived",
    "instanceData": {
      "idInstance": "7105335266"
    },
    "messageData": {
      "typeMessage": "textMessage",
      "textMessageData": {
        "textMessage": "test"
      },
      "senderData": {
        "chatId": "79001234567@c.us",
        "senderName": "Test User"
      }
    }
  }'
```

### Проблема: Webhook приходит, но бот не отвечает

**Решение:**
1. Проверьте логи Railway на наличие ошибок
2. Убедитесь, что все переменные окружения установлены правильно
3. Проверьте, что `EVOPOLIKI_WHATSAPP_API_TOKEN` и `EVOPOLIKI_WHATSAPP_INSTANCE_ID` совпадают с вашими данными

### Проблема: Unknown instance_id

**Решение:**
1. Проверьте в логах, какой `instance_id` приходит в webhook
2. Убедитесь, что переменная `EVOPOLIKI_WHATSAPP_INSTANCE_ID` на Railway установлена правильно (должна быть "7105335266")

## Полезные ссылки

- [GreenAPI Documentation](https://green-api.com/docs/)
- [Webhook Format Reference](https://green-api.com/docs/api/receiving/technology-webhook-endpoint/)
- [Testing Webhooks](https://green-api.com/docs/api/receiving/webhook-examples/)

## Следующие шаги

После успешной настройки webhook:
1. ✅ Бот отвечает на входящие сообщения
2. 🔄 Переходите к следующей итерации - добавление обработки команд и каталога
3. 🔄 Интеграция с базой данных для сохранения истории диалогов
