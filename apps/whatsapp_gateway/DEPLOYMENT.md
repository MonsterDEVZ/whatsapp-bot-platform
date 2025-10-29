# WhatsApp Gateway - Deployment на Railway

## Шаг 1: Подготовка кода

✅ Все файлы уже созданы:
- `apps/whatsapp_gateway/main.py` - FastAPI приложение
- `apps/whatsapp_gateway/Dockerfile` - Docker образ
- `apps/whatsapp_gateway/railway.toml` - конфигурация Railway
- `apps/whatsapp_gateway/requirements.txt` - зависимости

## Шаг 2: Коммит и Push в Git

```bash
git add .
git commit -m "Add WhatsApp Gateway service with Docker support"
git push origin main
```

## Шаг 3: Создание нового сервиса на Railway

### 3.1 Войдите на Railway
1. Откройте https://railway.app
2. Войдите в ваш аккаунт
3. Выберите ваш проект (chatbot_platform)

### 3.2 Добавьте новый сервис
1. Нажмите **"+ New"** → **"Service"**
2. Выберите **"GitHub Repo"**
3. Выберите репозиторий `chatbot_platform`
4. В разделе **"Root Directory"** укажите: `apps/whatsapp_gateway`
5. Нажмите **"Deploy"**

### 3.3 Альтернативный способ (если есть railway CLI)
```bash
cd apps/whatsapp_gateway
railway up
```

## Шаг 4: Настройка переменных окружения в Railway

После создания сервиса, перейдите в его настройки:

1. Откройте сервис **whatsapp-gateway**
2. Перейдите в раздел **"Variables"**
3. Добавьте следующие переменные:

### Обязательные переменные для Evopoliki:

```
EVOPOLIKI_WHATSAPP_INSTANCE_ID=7105335266
EVOPOLIKI_WHATSAPP_API_TOKEN=5f59dcf72e9641709a36a9b2217e089235e68cb92a7b4f2197
EVOPOLIKI_WHATSAPP_API_URL=https://7105.api.greenapi.com
EVOPOLIKI_WHATSAPP_PHONE_NUMBER=+996...

BOT_TOKEN=8396195173:AAHpk8yVcTM3pJ0feq2LerHH9lgqqXEKvAE
TENANT_SLUG=evopoliki

DB_HOST=<ваш Railway PostgreSQL хост>
DB_PORT=5432
DB_NAME=railway
DB_USER=postgres
DB_PASSWORD=<пароль из Railway PostgreSQL>
```

### Опциональные переменные для Five Deluxe (если нужно):

```
FIVE_DELUXE_WHATSAPP_INSTANCE_ID=<instance_id>
FIVE_DELUXE_WHATSAPP_API_TOKEN=<api_token>
FIVE_DELUXE_WHATSAPP_API_URL=https://api.greenapi.com
FIVE_DELUXE_WHATSAPP_PHONE_NUMBER=<phone>
```

### Переменная порта:
```
PORT=8000
WHATSAPP_GATEWAY_PORT=8000
```

## Шаг 5: Получение публичного URL

1. После успешного deployment, откройте вкладку **"Settings"** → **"Networking"**
2. Нажмите **"Generate Domain"**
3. Скопируйте сгенерированный URL (например: `whatsapp-gateway-production.up.railway.app`)

## Шаг 6: Проверка работы сервиса

Откройте в браузере или через curl:

```bash
curl https://whatsapp-gateway-production.up.railway.app/

# Должен вернуть:
# {"status":"ok","service":"WhatsApp Gateway","version":"1.0.0","active_tenants":1}
```

## Шаг 7: Мониторинг логов

В Railway откройте вкладку **"Deployments"** и выберите последний deployment.

Вы должны увидеть в логах:
```
🚀 Starting WhatsApp Gateway...
✅ Loaded WhatsApp config for evopoliki (instance: 7105335266)
📱 Total active WhatsApp instances: 1
✅ WhatsApp Gateway is ready!
```

## Troubleshooting

### Проблема: Build Failed
- Проверьте логи build в Railway
- Убедитесь, что все файлы закоммичены в Git
- Проверьте синтаксис Dockerfile

### Проблема: Application Crashed
- Проверьте переменные окружения
- Убедитесь, что все обязательные переменные установлены
- Проверьте логи приложения в Railway

### Проблема: Health check failed
- Убедитесь, что порт 8000 открыт
- Проверьте, что endpoint `/` отвечает

## Следующий шаг

После успешного deployment переходите к настройке GreenAPI webhook (см. GREENAPI_SETUP.md)
