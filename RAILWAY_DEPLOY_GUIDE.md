# 🚀 Railway Deployment Guide - WhatsApp Platform

## Что нужно сделать

### 1️⃣ Подготовка кода (УЖЕ СДЕЛАНО ✅)

- ✅ Health endpoint на `/` уже настроен
- ✅ `requirements.txt` обновлен (добавлен `greenlet`)
- ✅ `Procfile` настроен
- ✅ `railway.json` настроен

---

## 2️⃣ Деплой на Railway

### Шаг 1: Push в GitHub

```bash
cd /Users/new/Desktop/Проекты/CarChatbot/whatsapp_platform

# Если еще не git репозиторий
git init
git add .
git commit -m "Add WhatsApp Platform with Railway config"

# Push в ваш GitHub репозиторий
git remote add origin <URL вашего репозитория>
git push -u origin main
```

### Шаг 2: Railway Dashboard

1. Откройте [Railway Dashboard](https://railway.app/dashboard)
2. Найдите проект `web-production-2c795`
3. Перейдите в Settings → Service

### Шаг 3: Проверьте настройки

**Build Settings:**
- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`

**Environment Variables** (должны быть установлены):

```bash
# Database
DATABASE_URL=postgresql://postgres:stispeCxzTCLVnCvVGfoDFPRlBZlKpaL@gondola.proxy.rlwy.net:54660/railway

# PORT (Railway автоматически устанавливает)
PORT=8000

# EVOPOLIKI Tenant
EVOPOLIKI_BOT_TOKEN=your_telegram_bot_token_here
EVOPOLIKI_WHATSAPP_INSTANCE_ID=your_instance_id
EVOPOLIKI_WHATSAPP_API_TOKEN=your_greenapi_token
EVOPOLIKI_WHATSAPP_PHONE_NUMBER=+996XXXXXXXXX
EVOPOLIKI_WHATSAPP_API_URL=https://7107.api.green-api.com
EVOPOLIKI_OPENAI_API_KEY=your_openai_key_here
EVOPOLIKI_OPENAI_ASSISTANT_ID=asst_XXXXXXXXXXXXX
EVOPOLIKI_ENABLE_DIALOG_MODE=True

# FIVE_DELUXE Tenant
FIVE_DELUXE_BOT_TOKEN=your_telegram_bot_token_here
FIVE_DELUXE_WHATSAPP_INSTANCE_ID=your_instance_id
FIVE_DELUXE_WHATSAPP_API_TOKEN=your_greenapi_token
FIVE_DELUXE_WHATSAPP_PHONE_NUMBER=+996XXXXXXXXX
FIVE_DELUXE_WHATSAPP_API_URL=https://7107.api.green-api.com
FIVE_DELUXE_OPENAI_API_KEY=your_openai_key_here
FIVE_DELUXE_OPENAI_ASSISTANT_ID=asst_XXXXXXXXXXXXX
FIVE_DELUXE_ENABLE_DIALOG_MODE=True

# Airtable
AIRTABLE_API_KEY=your_airtable_key_here
AIRTABLE_BASE_ID=your_base_id
AIRTABLE_TABLE_NAME=Заявки с ботов

# Debug
DEBUG=false
```

### Шаг 4: Redeploy

1. В Railway нажмите **Deploy** → **Redeploy**
2. Дождитесь окончания деплоя
3. Проверьте логи: **View Logs**

---

## 3️⃣ Проверка деплоя

### Проверьте health endpoint

```bash
curl https://web-production-2c795.up.railway.app/
```

**Ожидаемый ответ:**
```json
{
  "status": "ok",
  "service": "WhatsApp Gateway",
  "version": "1.0.0",
  "active_tenants": 2
}
```

### Если не работает:

1. **Проверьте логи** в Railway Dashboard
2. **Убедитесь**, что все переменные окружения установлены
3. **Проверьте**, что PORT установлен Railway (автоматически)

---

## 4️⃣ Настройка Webhook в GreenAPI

После успешного деплоя нужно настроить webhook для каждого instance.

### EVOPOLIKI (Instance: 7107360346)

**Метод 1: Через GreenAPI Console**

1. Откройте [GreenAPI Console](https://console.green-api.com/)
2. Выберите Instance **7107360346**
3. Перейдите в **Settings** → **Webhook**
4. Установите:
   - **Webhook URL**: `https://web-production-2c795.up.railway.app/webhook`
   - **Method**: POST
   - **Events**: Выберите все (или хотя бы `incomingMessageReceived`)

**Метод 2: Через API**

```bash
curl -X POST "https://7107.api.green-api.com/waInstance{YOUR_INSTANCE_ID}/setSettings/{YOUR_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhookUrl": "https://web-production-2c795.up.railway.app/webhook",
    "outgoingWebhook": "yes",
    "incomingWebhook": "yes"
  }'
```

Замените `{YOUR_INSTANCE_ID}` и `{YOUR_API_TOKEN}` на реальные значения из Railway переменных.

### FIVE_DELUXE (Instance: YOUR_INSTANCE_ID_2)

**Метод 1: Через GreenAPI Console**

1. Откройте [GreenAPI Console](https://console.green-api.com/)
2. Выберите ваш второй Instance
3. Перейдите в **Settings** → **Webhook**
4. Установите:
   - **Webhook URL**: `https://web-production-2c795.up.railway.app/webhook`
   - **Method**: POST
   - **Events**: Выберите все

**Метод 2: Через API**

```bash
curl -X POST "https://7107.api.green-api.com/waInstance{YOUR_INSTANCE_ID_2}/setSettings/{YOUR_API_TOKEN_2}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhookUrl": "https://web-production-2c795.up.railway.app/webhook",
    "outgoingWebhook": "yes",
    "incomingWebhook": "yes"
  }'
```

Замените `{YOUR_INSTANCE_ID_2}` и `{YOUR_API_TOKEN_2}` на реальные значения.

---

## 5️⃣ Тестирование

### Отправьте тестовое сообщение

1. Откройте WhatsApp
2. Напишите на номер EVOPOLIKI: **+996507988088**
3. Отправьте сообщение: "Привет"

### Проверьте логи Railway

В Railway Dashboard → **View Logs** вы должны увидеть:
```
INFO - Received webhook: incomingMessageReceived
INFO - Processing message from: 996...
```

---

## ✅ Checklist

- [ ] Код запушен в GitHub
- [ ] Railway переменные окружения установлены
- [ ] Railway деплой успешен
- [ ] Health endpoint отвечает
- [ ] Webhook настроен для EVOPOLIKI
- [ ] Webhook настроен для FIVE_DELUXE
- [ ] Тестовое сообщение получено

---

## 🆘 Troubleshooting

### Проблема: Сервер не запускается

**Решение:**
1. Проверьте логи Railway
2. Убедитесь, что `DATABASE_URL` правильный
3. Проверьте, что все зависимости в `requirements.txt`

### Проблема: Health endpoint не отвечает

**Решение:**
1. Проверьте, что `PORT` переменная установлена Railway
2. Убедитесь, что сервер запущен: `python main.py`
3. Проверьте логи на ошибки

### Проблема: Webhook не работает

**Решение:**
1. Проверьте URL webhook в GreenAPI Console
2. Убедитесь, что URL правильный: `https://web-production-2c795.up.railway.app/webhook`
3. Проверьте, что `incomingWebhook` = `yes` в настройках
4. Отправьте тестовое сообщение и проверьте логи Railway

---

## 📚 Дополнительные ресурсы

- [Railway Docs](https://docs.railway.app/)
- [GreenAPI Docs](https://green-api.com/docs/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

Готово! 🎉
