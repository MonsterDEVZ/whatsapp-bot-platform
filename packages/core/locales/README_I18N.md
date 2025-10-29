# Система локализации (i18n) для мультитенантного бота

## Обзор

Система i18n позволяет каждому клиенту (tenant) иметь свои уникальные тексты на разных языках.

## Структура файлов

```
locales/
├── evopoliki/
│   ├── ru.json    # Русский язык для EVOPOLIKI
│   └── ky.json    # Кыргызский язык для EVOPOLIKI
└── five_deluxe/
    ├── ru.json    # Русский язык для 5DELUXE
    └── ky.json    # Кыргызский язык для 5DELUXE
```

## Инициализация

Система i18n автоматически инициализируется в `bot.py`:

```python
from core.i18n import init_i18n

# Инициализация для конкретного клиента
init_i18n(tenant_slug="evopoliki", language="ru")
```

## Использование в коде

### Способ 1: Через функцию get()

```python
from core.i18n import get_i18n

i18n = get_i18n()

# Простой доступ к текстам
welcome_text = i18n.get("start.welcome")

# Доступ к вложенным ключам
company_name = i18n.get("company.name")
faq_question = i18n.get("faq.care.question")

# Форматирование с параметрами
greeting = i18n.get("order.brand.selected", brand_name="Toyota")
```

### Способ 2: Через атрибуты (только для верхнего уровня)

```python
from core.i18n import get_i18n

i18n = get_i18n()

# Прямой доступ к верхнеуровневым ключам
company_info = i18n.company  # Возвращает словарь
```

## Структура JSON файла

```json
{
  "company": {
    "name": "EVOPOLIKI",
    "address": "г. Бишкек, ул. Примерная, 123"
  },
  "start": {
    "welcome": "Добро пожаловать в {company_name}!"
  },
  "buttons": {
    "eva_mats": "🏆 EVA-коврики"
  },
  "faq": {
    "care": {
      "question": "Как ухаживать?",
      "answer": "Инструкция по уходу..."
    }
  }
}
```

## Примеры использования в handlers

### Пример 1: Приветственное сообщение

```python
from aiogram.types import Message
from core.i18n import get_i18n

async def cmd_start(message: Message):
    i18n = get_i18n()

    await message.answer(
        text=i18n.get("start.welcome"),
        reply_markup=get_language_keyboard()
    )
```

### Пример 2: Форматирование с параметрами

```python
from core.i18n import get_i18n

async def show_vehicle_summary(message: Message, brand: str, model: str):
    i18n = get_i18n()

    text = i18n.get(
        "order.brand.selected",
        brand_name=brand,
        model_name=model
    )

    await message.answer(text)
```

### Пример 3: Использование в keyboards

```python
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.i18n import get_i18n

def get_main_menu_keyboard():
    i18n = get_i18n()
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.categories.eva_mats"),
            callback_data="category:eva_mats"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.back_to_menu"),
            callback_data="action:back_to_menu"
        )
    )

    return builder.as_markup()
```

## Смена языка

Для смены языка во время работы бота:

```python
from core.i18n import get_i18n

async def set_language(language: str):
    i18n = get_i18n()
    i18n.set_language(language)  # "ru" или "ky"
```

## Добавление нового клиента

1. Создайте директорию в `locales/`:
   ```bash
   mkdir locales/new_client
   ```

2. Создайте файлы локализации:
   ```bash
   touch locales/new_client/ru.json
   touch locales/new_client/ky.json
   ```

3. Скопируйте структуру из существующего файла и адаптируйте тексты

4. В `apps/new_client/bot.py`:
   ```python
   init_i18n(tenant_slug="new_client", language="ru")
   ```

## Добавление нового языка

1. Создайте файл с нужным кодом языка (например, `en.json`)
2. Скопируйте структуру из `ru.json`
3. Переведите все тексты
4. Инициализируйте с нужным языком:
   ```python
   init_i18n(tenant_slug="evopoliki", language="en")
   ```

## Текущий статус

✅ **Реализовано:**
- Система i18n с поддержкой мультитенантности
- JSON файлы локализации для EVOPOLIKI (русский)
- JSON файлы локализации для 5DELUXE (русский, кастомизированный)
- Интеграция i18n в bot.py для обоих клиентов
- API для доступа к локализованным текстам

⏳ **Требует доработки:**
- Рефакторинг handlers для использования i18n вместо hardcoded текстов
- Рефакторинг keyboards для использования i18n
- Создание кыргызских переводов (ky.json) для обоих клиентов
- Middleware для автоматической смены языка на основе выбора пользователя

## Рекомендации

1. **Всегда используйте i18n для текстов:**
   ❌ Плохо: `await message.answer("Добро пожаловать")`
   ✅ Хорошо: `await message.answer(i18n.get("start.welcome"))`

2. **Используйте говорящие ключи:**
   ❌ Плохо: `"text1", "msg_2"`
   ✅ Хорошо: `"start.welcome", "faq.care.question"`

3. **Группируйте связанные тексты:**
   ```json
   {
     "faq": {
       "care": {...},
       "delivery": {...},
       "warranty": {...}
     }
   }
   ```

4. **Используйте параметры для динамических данных:**
   ```json
   {
     "greeting": "Привет, {name}!",
     "order_summary": "Заказ для {brand} {model}"
   }
   ```

## Поддержка

Для вопросов по системе i18n обращайтесь к документации или примерам в коде.
