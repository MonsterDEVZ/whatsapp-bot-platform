# Railway Deployment Guide - Five Deluxe Multi-Tenant

## 🚀 Quick Deployment Checklist

### 1. Environment Variables to Add on Railway

Откройте Railway Dashboard → Your Project → Variables и добавьте:

```bash
# Five Deluxe Airtable Credentials
# ⚠️ ВАЖНО: Используйте реальные значения из вашего .env файла или документации проекта
FIVE_DELUXE_AIRTABLE_API_TOKEN=pat***********************************
FIVE_DELUXE_AIRTABLE_BASE_ID=app***************
FIVE_DELUXE_AIRTABLE_TABLE_ID=tbl***************
```

**ВАЖНО**:
- Эти три переменные обязательны для работы Five Deluxe!
- Фактические значения найдите в вашем локальном `.env` файле или у администратора проекта
- НЕ коммитьте реальные API tokens в Git!

### 2. Verify Auto-Deploy

После push в GitHub, Railway автоматически:
1. Обнаружит новый коммит (074e994)
2. Запустит новый build
3. Задеплоит обновленный код

Проверьте в Railway Dashboard:
- Deployment Status: ✅ Success
- Logs: Нет ошибок при старте

### 3. Testing Checklist

#### Test 1: EVOPOLIKI (existing tenant)
```
1. Отправьте "Меню" на номер EVOPOLIKI
2. ✅ Должно появиться меню с 4 категориями:
   - 💎 5D-коврики Deluxe
   - 🌿 EVA-коврики
   - 👑 Премиум-чехлы
   - ✨ Накидки из алькантары
3. Выберите любую категорию
4. ✅ Должен запуститься процесс заказа
5. Пройдите весь флоу до отправки в Airtable
6. ✅ Лид должен появиться в Airtable EVOPOLIKI
```

#### Test 2: FIVE_DELUXE (new tenant)
```
1. Отправьте "Меню" на номер FIVE_DELUXE
2. ✅ Должно появиться меню с 3 категориями (БЕЗ EVA):
   - 💎 5D-коврики Deluxe
   - 👑 Премиум-чехлы
   - ✨ Накидки из алькантары
3. Выберите любую категорию
4. ✅ Должен запуститься процесс заказа
5. Пройдите весь флоу до отправки в Airtable
6. ✅ Лид должен появиться в Airtable FIVE_DELUXE (app1X2TpPVukeswtK)
```

#### Test 3: Fail-Safe Menu Commands
```
Для ОБОИХ tenants:

1. Отправьте "меню"
   ✅ Показывается главное меню

2. Отправьте "покажи меню"
   ✅ Показывается главное меню

3. Отправьте "каталог"
   ✅ Показывается главное меню

4. Отправьте "назад" (в середине процесса заказа)
   ✅ Возвращает в главное меню

5. Отправьте "В меню есть чехлы?" (вопрос, а не команда)
   ✅ AI должен ОТВЕТИТЬ на вопрос (НЕ показывать меню)
```

#### Test 4: AI Router (if ENABLE_DIALOG_MODE=true)
```
1. Отправьте "Хочу коврики 5D на Lexus RX 350"
   ✅ AI распознает: category=5d_mats, brand=Lexus, model=RX 350
   ✅ Запрашивает только год

2. Отправьте "Нужны чехлы на BMW"
   ✅ AI распознает: category=premium_covers, brand=BMW
   ✅ Запрашивает модель
```

### 4. Monitoring Railway Logs

Откройте Railway → Logs и следите за:

```bash
# ✅ Успешный старт
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000

# ✅ Успешная загрузка tenants
🏢 [CONFIG] Loaded tenant: evopoliki
🏢 [CONFIG] Loaded tenant: five_deluxe

# ✅ Успешная обработка меню
🏢 [FIVE_DELUXE] Generating menu for {name}
✅ [FIVE_DELUXE] Generated interactive menu with 3 categories

# ✅ Успешная отправка в Airtable
✅ [AIRTABLE] Lead created for five_deluxe: rec...
```

### 5. Common Issues & Solutions

#### Issue 1: "catalog_categories not found"
```
❌ [FIVE_DELUXE] catalog_categories not found or empty!
```
**Причина**: Не загрузился файл локализации `packages/core/locales/five_deluxe/ru.json`

**Решение**:
1. Проверьте, что файл существует в репозитории
2. Проверьте права доступа к файлу
3. Перезапустите Railway deployment

#### Issue 2: "Failed to create lead in Airtable"
```
❌ [AIRTABLE] Failed to create lead for five_deluxe
```
**Причина**: Неверные Airtable credentials или нет доступа

**Решение**:
1. Проверьте правильность переменных окружения на Railway
2. Убедитесь, что API token имеет права на запись
3. Проверьте, что Base ID и Table ID корректны

#### Issue 3: Menu shows EVA-коврики for Five Deluxe
```
Меню показывает 4 категории вместо 3
```
**Причина**: Используется неправильный файл локализации

**Решение**:
1. Убедитесь, что `five_deluxe_handler.py` использует `tenant_config.i18n`
2. Проверьте, что в `packages/core/locales/five_deluxe/ru.json` только 3 категории
3. Перезапустите deployment

### 6. Rollback Plan (if needed)

Если что-то пошло не так:

```bash
# 1. Откатите на предыдущий коммит
git revert 074e994518a5e2b003cdba422aa922fe0f0f99b9

# 2. Push отката
git push origin main

# 3. Railway автоматически задеплоит предыдущую версию
```

### 7. Architecture Verification

```
┌─────────────────────────────────────────────────────────┐
│                     TENANT CONFIG                        │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │   EVOPOLIKI      │         │   FIVE_DELUXE    │     │
│  │   - 4 категории  │         │   - 3 категории  │     │
│  │   - AI enabled   │         │   - AI disabled  │     │
│  └──────────────────┘         └──────────────────┘     │
└─────────────────────────────────────────────────────────┘
                      ↓                    ↓
┌─────────────────────────────────────────────────────────┐
│              MENU HANDLERS (tenant-specific)            │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │ evopoliki_       │         │ five_deluxe_     │     │
│  │ handler.py       │         │ handler.py       │     │
│  └──────────────────┘         └──────────────────┘     │
└─────────────────────────────────────────────────────────┘
                      ↓                    ↓
┌─────────────────────────────────────────────────────────┐
│           UNIVERSAL FUNNEL (shared for both)            │
│  ┌──────────────────────────────────────────────────┐  │
│  │  handle_main_menu_choice                          │  │
│  │  show_brands_page                                 │  │
│  │  handle_brand_input                               │  │
│  │  handle_contact_collection                        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│           AIRTABLE INTEGRATION (multi-tenant)           │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │   EVOPOLIKI      │         │   FIVE_DELUXE    │     │
│  │   Base: app...   │         │   Base: app1X2T  │     │
│  └──────────────────┘         └──────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 8. Success Metrics

✅ **Deployment считается успешным, если:**

1. Railway показывает "Deployment: Success"
2. Оба tenant'а отвечают на команду "Меню"
3. EVOPOLIKI показывает 4 категории (включая EVA)
4. FIVE_DELUXE показывает 3 категории (без EVA)
5. Заказы из обоих tenants попадают в правильные Airtable базы
6. Fail-safe команды ("меню", "каталог", "назад") работают
7. AI router корректно извлекает данные (если включен)

### 9. Post-Deployment Tasks

После успешного deployment:

1. ✅ Обновите OpenAI Assistant prompt (если используете AI)
2. ✅ Протестируйте все 6 сценариев из Test Plan
3. ✅ Мониторьте Railway logs первые 24 часа
4. ✅ Проверьте, что лиды корректно создаются в обеих Airtable базах

### 10. Support Contacts

**Railway Dashboard**: https://railway.app
**Airtable EVOPOLIKI**: (ваш base ID)
**Airtable FIVE_DELUXE**: https://airtable.com/app1X2TpPVukeswtK

---

## 🎉 Ready to Deploy!

Все необходимые изменения уже в коде (commit 074e994).

**Next steps:**
1. Add 3 environment variables to Railway
2. Wait for auto-deploy to complete
3. Run testing checklist
4. Monitor logs for 24h

**Estimated time**: 15-20 minutes total
