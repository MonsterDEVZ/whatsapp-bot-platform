# ЧТО ОТ ВАС НУЖНО СДЕЛАТЬ 🎯

## ✅ Уже исправлено автоматически:

1. ✅ Health endpoint работает на `/`
2. ✅ `requirements.txt` обновлен (добавлен `greenlet`)
3. ✅ Локально сервер работает на порту 8001

---

## 🔥 Что нужно сделать СРОЧНО:

### 1. Push изменения в GitHub

```bash
cd /Users/new/Desktop/Проекты/CarChatbot/whatsapp_platform

git add requirements.txt
git commit -m "Fix: Add greenlet to requirements.txt for Railway"
git push origin main
```

### 2. Railway Redeploy

1. Откройте Railway Dashboard: https://railway.app/dashboard
2. Найдите проект `web-production-2c795`
3. Нажмите **Deploy** → **Redeploy**
4. Дождитесь окончания (2-3 минуты)

### 3. Проверьте, что работает

Откройте в браузере или выполните:

```bash
curl https://web-production-2c795.up.railway.app/
```

**Должно вернуть:**
```json
{
  "status": "ok",
  "service": "WhatsApp Gateway",
  "version": "1.0.0",
  "active_tenants": 2
}
```

---

## 📱 Настройка Webhook в GreenAPI

После успешного деплоя:

### Для EVOPOLIKI (Instance: 7107360346)

**Вариант 1: Через Web Console**
1. Откройте https://console.green-api.com/
2. Выберите instance `7107360346`
3. Settings → Webhook
4. Webhook URL: `https://web-production-2c795.up.railway.app/webhook`
5. Включите все события

**Вариант 2: Через API (быстрее)**

```bash
# Замените {INSTANCE_ID} и {API_TOKEN} на реальные из Railway
curl -X POST "https://7107.api.green-api.com/waInstance{INSTANCE_ID}/setSettings/{API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhookUrl": "https://web-production-2c795.up.railway.app/webhook",
    "outgoingWebhook": "yes",
    "incomingWebhook": "yes"
  }'
```

### Для FIVE_DELUXE (второй Instance)

```bash
# Замените {INSTANCE_ID_2} и {API_TOKEN_2} на реальные из Railway
curl -X POST "https://7107.api.green-api.com/waInstance{INSTANCE_ID_2}/setSettings/{API_TOKEN_2}" \
  -H "Content-Type: application/json" \
  -d '{
    "webhookUrl": "https://web-production-2c795.up.railway.app/webhook",
    "outgoingWebhook": "yes",
    "incomingWebhook": "yes"
  }'
```

---

## ✅ Тестирование

### Отправьте тестовое сообщение:

1. Откройте WhatsApp
2. Напишите на **+996507988088** (EVOPOLIKI)
3. Отправьте: "Привет"
4. Проверьте, что бот ответил

### Проверьте логи в Railway:

1. Railway Dashboard → **View Logs**
2. Должны увидеть: `Received webhook: incomingMessageReceived`

---

## 📋 Checklist

- [ ] **Git push** изменений
- [ ] **Railway redeploy** успешен
- [ ] **Health endpoint** работает (проверить в браузере)
- [ ] **Webhook EVOPOLIKI** настроен
- [ ] **Webhook FIVE_DELUXE** настроен
- [ ] **Тестовое сообщение** получено и бот ответил

---

## 🆘 Если что-то не работает

Смотрите подробную инструкцию: **RAILWAY_DEPLOY_GUIDE.md**

**Основные проблемы:**
1. Забыли push в GitHub → делаем push
2. Railway не видит изменения → делаем Redeploy
3. Webhook не работает → проверяем URL в GreenAPI Console

---

## 🎯 Итого за 5 минут:

1. ✅ Push `requirements.txt`
2. ✅ Railway Redeploy
3. ✅ Проверить health endpoint
4. ✅ Настроить 2 webhook
5. ✅ Отправить тестовое сообщение

Готово! 🚀
