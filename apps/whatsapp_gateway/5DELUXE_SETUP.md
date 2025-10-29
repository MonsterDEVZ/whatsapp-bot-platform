# Настройка WhatsApp-бота для 5deluxe

## 📋 Обзор

WhatsApp-бот для **5deluxe** работает в режиме **простого IVR-меню** (без OpenAI) и использует цифровые команды вместо кнопок.

---

## 🏗️ Архитектура

### Роутинг по tenant:
- **evopoliki** → Умный AI-ассистент с OpenAI (существующий)
- **5deluxe** → Простое IVR-меню (новый)

### Основные файлы:
1. **`main.py`** - главный роутер, различает tenant по `idInstance`
2. **`ivr_handlers_5deluxe.py`** - обработчик IVR-сценария для 5deluxe
3. **`packages/core/keyboards/whatsapp_ui.py`** - генератор текстовых меню
4. **`state_manager.py`** - FSM для управления состояниями пользователей

---

## ⚙️ Настройка

### Шаг 1: Добавьте WhatsApp-настройки в `.env`

Откройте файл `apps/five_deluxe/.env` и заполните следующие поля:

```env
# WhatsApp Configuration (GreenAPI)
FIVE_DELUXE_WHATSAPP_INSTANCE_ID=your_instance_id_here    # Замените на ваш idInstance
FIVE_DELUXE_WHATSAPP_API_TOKEN=your_api_token_here        # Замените на ваш apiTokenInstance
FIVE_DELUXE_WHATSAPP_API_URL=https://your_instance.api.greenapi.com  # URL вашего инстанса
FIVE_DELUXE_WHATSAPP_PHONE_NUMBER=+996XXXXXXXXX           # Ваш WhatsApp номер
```

**ВАЖНО:** Префикс `FIVE_DELUXE_` должен быть написан **ЗАГЛАВНЫМИ БУКВАМИ**.

### Шаг 2: Настройте Webhook в GreenAPI

1. Войдите в личный кабинет GreenAPI
2. Перейдите в настройки вашего инстанса для **5deluxe**
3. Установите **Webhook URL**:
   ```
   https://your-domain.com/webhook
   ```
4. Включите события:
   - ✅ `incomingMessageReceived`

---

## 🚀 Запуск

### Локальная разработка:

```bash
# Из корня проекта
python apps/whatsapp_gateway/main.py
```

### Production (Railway):

WhatsApp Gateway автоматически запустится через `Procfile`:
```
whatsapp_gateway: python apps/whatsapp_gateway/main.py
```

---

## 📊 Логи

При старте сервера вы должны увидеть:

```
✅ Loaded WhatsApp config for evopoliki (instance: 7105335266)
✅ Loaded WhatsApp config for five_deluxe (instance: YOUR_INSTANCE_ID)
📱 Total active WhatsApp instances: 2
```

При получении сообщения:

```
🏢 Tenant identified: five_deluxe
📋 [ROUTING] Tenant: five_deluxe -> IVR menu flow
[5DELUXE_IVR] User 996777510804@c.us in state: main_menu, message: '1'
```

---

## 🎯 IVR-сценарий для 5deluxe

### Главное меню:
```
1 - 💎 5D-коврики Deluxe
2 - 👑 Премиум-чехлы
3 - ✨ Накидки из алькантары
4 - 📞 Связаться с менеджером
```

### Сценарий заказа:
1. Пользователь выбирает категорию (цифра 1-4)
2. Бот предлагает выбрать марку автомобиля (пагинация: 00/99)
3. Пользователь выбирает модель автомобиля
4. Бот ищет лекала в **общей БД PostgreSQL**
5. Если лекала найдены → выбор опций → подтверждение заказа
6. Бот запрашивает имя и телефон
7. Заявка создается (TODO: интеграция с Airtable)

---

## 🔍 Отладка

### Проверка подключения к БД:

```bash
python check_db_connection.py five_deluxe
```

Ожидаемый результат:
```
✅ Конфигурация загружена успешно
   Tenant: five_deluxe
✅ Подключение к базе данных... УСПЕШНО.
✅ Результат: Найдено 82 марок.
```

### Health Check:

```bash
curl http://localhost:8000/
```

Ожидаемый ответ:
```json
{
  "status": "ok",
  "service": "WhatsApp Gateway",
  "version": "1.0.0",
  "active_tenants": 2
}
```

---

## 📦 Зависимости

Все зависимости уже установлены через:
- `requirements.txt` (основной проект)
- `apps/whatsapp_gateway/requirements.txt` (FastAPI, httpx)

---

## ✅ Критерии успеха

- ✅ При запуске сервера видны 2 активных tenant (evopoliki + five_deluxe)
- ✅ При отправке сообщения на номер 5deluxe бот отвечает IVR-меню
- ✅ При отправке сообщения на номер evopoliki бот отвечает через AI
- ✅ IVR-сценарий для 5deluxe успешно находит лекала в общей БД
- ✅ Заявки создаются с правильным `tenant_id`

---

## 🔧 Дополнительная настройка

### Интеграция с Airtable

Для создания заявок в Airtable, добавьте в `ivr_handlers_5deluxe.py` функцию `handle_phone_input()`:

```python
# TODO: Вызвать функцию создания заявки
# from packages.core.handlers.requests import create_request
# await create_request(user_data, config)
```

---

## 📞 Поддержка

Для вопросов по настройке обратитесь к документации:
- [GreenAPI Setup](GREENAPI_SETUP.md)
- [Deployment](DEPLOYMENT.md)
