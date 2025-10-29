"""
Обработчики сообщений WhatsApp.

Реализует логику сценариев аналогично Telegram-боту,
но адаптированную для текстового интерфейса WhatsApp.
"""

import sys
from pathlib import Path

# Добавляем путь к корню проекта для импорта packages
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Добавляем packages/core в sys.path чтобы работали импорты "from core.xxx"
core_path = project_root / "packages"
if str(core_path) not in sys.path:
    sys.path.insert(0, str(core_path))

from typing import Optional
import logging
import httpx
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.config import Config
from packages.core.db.queries import (
    search_patterns,
    get_tenant_by_slug,
    calculate_total_price,
    get_model_with_body_type,
    fuzzy_search_model,
    get_brand_by_name,
    get_unique_brands_from_db,
    get_models_for_brand_from_db
)
from packages.core.memory import get_memory
from packages.core.integrations import create_lead

from .state_manager import (
    WhatsAppState,
    get_state,
    set_state,
    get_user_data,
    update_user_data,
    clear_state
)

logger = logging.getLogger(__name__)

# Константы пагинации
BRANDS_PER_PAGE = 8
MODELS_PER_PAGE = 8


def extract_phone_from_chat_id(chat_id: str) -> str:
    """
    Извлекает номер телефона из WhatsApp chatId.

    Args:
        chat_id: ID чата WhatsApp (например, "996777510804@c.us")

    Returns:
        Номер телефона в международном формате (например, "+996777510804")
    """
    # Убираем @c.us и добавляем +
    phone = chat_id.replace("@c.us", "").replace("@g.us", "").strip()
    if not phone.startswith("+"):
        phone = "+" + phone
    return phone


async def handle_start_message(chat_id: str, config: Config) -> str:
    """
    Обрабатывает первое сообщение от пользователя.
    Отправляет главное меню с категориями.

    КРИТИЧЕСКИ ВАЖНО: Меню генерируется ИСКЛЮЧИТЕЛЬНО из buttons.catalog_categories!
    Никаких захардкоженных категорий! Каждый tenant имеет свой уникальный набор.

    Args:
        chat_id: ID чата WhatsApp
        config: Конфигурация tenant

    Returns:
        Текст ответа
    """
    i18n = config.i18n

    # Устанавливаем состояние главного меню
    set_state(chat_id, WhatsAppState.MAIN_MENU)

    # Получаем catalog_categories из локализации
    catalog_categories = i18n.get("buttons.catalog_categories")

    logger.info(f"🔍 [START_MESSAGE] Генерация текстового меню для WhatsApp")
    logger.info(f"🔍 [START_MESSAGE] catalog_categories: {catalog_categories}")

    if not catalog_categories or not isinstance(catalog_categories, list):
        # КРИТИЧЕСКАЯ ОШИБКА: catalog_categories не найден!
        logger.error(f"❌ [START_MESSAGE] catalog_categories НЕ НАЙДЕН!")
        return (
            f"🚗 {i18n.get('start.welcome')}\n\n"
            f"⚠️ Ошибка конфигурации меню. Свяжитесь с менеджером."
        )

    if len(catalog_categories) == 0:
        logger.error(f"❌ [START_MESSAGE] catalog_categories ПУСТОЙ!")
        return (
            f"🚗 {i18n.get('start.welcome')}\n\n"
            f"⚠️ Каталог недоступен. Свяжитесь с менеджером."
        )

    # Формируем текстовое меню ДИНАМИЧЕСКИ из catalog_categories
    menu_lines = [
        f"🚗 {i18n.get('start.welcome')}\n",
        f"📋 Чтобы продолжить, отправьте цифру нужного раздела:\n"
    ]

    logger.info(f"✅ [START_MESSAGE] Генерирую {len(catalog_categories)} категорий")

    for idx, category in enumerate(catalog_categories, start=1):
        text = category.get("text", "")
        callback_data = category.get("callback_data", "")

        logger.info(f"  [{idx}] text='{text}', callback='{callback_data}'")

        menu_lines.append(f"{idx}️⃣ - {text}")

    logger.info(f"✅ [START_MESSAGE] Меню успешно сгенерировано ({len(catalog_categories)} кнопок)")

    menu_text = "\n".join(menu_lines)
    return menu_text


async def handle_main_menu_choice(
    chat_id: str,
    choice: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает выбор пункта главного меню.

    Args:
        chat_id: ID чата WhatsApp
        choice: Выбранный пункт (1-5)
        config: Конфигурация tenant

    Returns:
        Текст ответа
    """
    i18n = config.i18n

    logger.info(f"🎯 [MENU_CHOICE] Tenant: {config.tenant_slug}, Choice: {choice}")

    # ═══════════════════════════════════════════════════════════════
    # КРИТИЧНО: Получаем catalog_categories ДИНАМИЧЕСКИ!
    # ═══════════════════════════════════════════════════════════════

    catalog_categories = i18n.get("buttons.catalog_categories")

    if not catalog_categories or not isinstance(catalog_categories, list):
        logger.error(f"❌ [MENU_CHOICE] catalog_categories не найден!")
        return "❌ Ошибка конфигурации. Свяжитесь с менеджером."

    # Преобразуем choice в индекс
    try:
        choice_idx = int(choice) - 1
    except ValueError:
        return "❌ Неверный выбор."

    if choice_idx < 0 or choice_idx >= len(catalog_categories):
        return f"❌ Неверный выбор. Отправьте цифру от 1 до {len(catalog_categories)}."

    # Получаем выбранную категорию
    selected_category = catalog_categories[choice_idx]
    callback_data = selected_category.get("callback_data", "")
    text = selected_category.get("text", "")

    logger.info(f"🎯 [MENU_CHOICE] Selected: {text} (callback: {callback_data})")

    # Парсим callback_data
    if ":" not in callback_data:
        logger.error(f"❌ [MENU_CHOICE] Неверный callback_data: {callback_data}")
        return "❌ Ошибка конфигурации."

    action_type, action_value = callback_data.split(":", 1)

    # Обработка category:xxx
    if action_type == "category":
        category_code = action_value

        logger.info(f"🛒 [MENU_CHOICE] Запуск заказа для category={category_code}")

        # ✅ ПРАВИЛЬНАЯ категория из конфигурации!
        set_state(chat_id, WhatsAppState.EVA_WAITING_BRAND, {
            "category": category_code,
            "category_name": text,
            "brands_page": 1
        })

        logger.info(f"✅ [MENU_CHOICE] category={category_code}, category_name={text}")

        return await show_brands_page(chat_id, 1, config, session)

    # Обработка action:contact_manager
    elif action_type == "action" and action_value == "contact_manager":
        set_state(chat_id, WhatsAppState.CONTACT_MANAGER)
        update_user_data(chat_id, {
            "application_type": "Запрос на звонок"  # ✅ Тип заявки для Airtable
        })
        return i18n.get("contact_manager.text")

    # Неизвестный action
    else:
        logger.error(f"❌ [MENU_CHOICE] Неизвестный action: {callback_data}")
        return "❌ Ошибка. Вернитесь в меню."

    # СТАРЫЙ СТАТИЧНЫЙ КОД УДАЛЁН!
    # Ранее здесь были хардкоженные блоки для EVOPOLIKI:
    # - elif choice == "1": category = "eva_mats" (❌ всегда eva_mats!)
    # - elif choice == "2", "3", "4", "5": другие категории
    # Теперь ВСЕ категории обрабатываются ДИНАМИЧЕСКИ через catalog_categories!


async def show_brands_page(
    chat_id: str,
    page: int,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Показывает страницу марок с пагинацией.

    Args:
        chat_id: ID чата WhatsApp
        page: Номер страницы (начиная с 1)
        config: Конфигурация tenant

    Returns:
        Текст с списком марок и командами навигации
    """
    user_data = get_user_data(chat_id)
    brands_list = user_data.get("all_brands")

    if not brands_list:
        tenant = await get_tenant_by_slug(session, config.tenant_slug)

        if not tenant:
            return "❌ Ошибка конфигурации. Попробуйте позже."

        brands_list = await get_unique_brands_from_db(tenant.id, session)
        update_user_data(chat_id, {"all_brands": brands_list})

    update_user_data(chat_id, {"brands_page": page})

    # Вычисляем пагинацию
    total_brands = len(brands_list)
    total_pages = (total_brands + BRANDS_PER_PAGE - 1) // BRANDS_PER_PAGE

    # Корректируем номер страницы
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    # Получаем марки для текущей страницы
    start_idx = (page - 1) * BRANDS_PER_PAGE
    end_idx = min(start_idx + BRANDS_PER_PAGE, total_brands)
    current_brands = brands_list[start_idx:end_idx]

    # Формируем текст
    text = (
        f"🏆 EVA-коврики\n\n"
        f"📝 Шаг 1/3: Выберите марку автомобиля\n\n"
        f"Страница {page}/{total_pages}\n\n"
    )

    # Добавляем список марок
    for i, brand in enumerate(current_brands, 1):
        text += f"{i}️⃣ - {brand}\n"

    text += "\n"

    # Добавляем команды навигации
    if page > 1:
        text += "0️⃣0️⃣ - Предыдущая страница\n"
    if page < total_pages:
        text += "9️⃣9️⃣ - Следующая страница\n"

    text += (
        "\n💡 Вы также можете ввести название марки текстом\n"
        "Например: Toyota, BMW, Mercedes"
    )

    return text


async def show_models_page(
    chat_id: str,
    page: int,
    brand_name: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Показывает страницу моделей с пагинацией.

    Args:
        chat_id: ID чата WhatsApp
        page: Номер страницы (начиная с 1)
        brand_name: Название марки
        config: Конфигурация tenant

    Returns:
        Текст с списком моделей и командами навигации
    """
    tenant = await get_tenant_by_slug(session, config.tenant_slug)

    if not tenant:
        return "❌ Ошибка конфигурации. Попробуйте позже."

    models_list = await get_models_for_brand_from_db(brand_name, tenant.id, session)

    # Сохраняем полный список моделей в состояние
    update_user_data(chat_id, {"all_models": models_list, "models_page": page})

    # Вычисляем пагинацию
    total_models = len(models_list)
    total_pages = (total_models + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE

    # Корректируем номер страницы
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    # Получаем модели для текущей страницы
    start_idx = (page - 1) * MODELS_PER_PAGE
    end_idx = min(start_idx + MODELS_PER_PAGE, total_models)
    current_models = models_list[start_idx:end_idx]

    # Формируем текст
    text = (
        f"✅ Марка: {brand_name}\n\n"
        f"📝 Шаг 2/3: Выберите модель автомобиля\n\n"
        f"Страница {page}/{total_pages}\n\n"
    )

    # Добавляем список моделей
    for i, model in enumerate(current_models, 1):
        text += f"{i}️⃣ - {model}\n"

    text += "\n"

    # Добавляем команды навигации
    if page > 1:
        text += "0️⃣0️⃣ - Предыдущая страница\n"
    if page < total_pages:
        text += "9️⃣9️⃣ - Следующая страница\n"

    text += (
        "\n💡 Вы также можете ввести название модели текстом\n"
        "Например: Camry, Land Cruiser, RAV4"
    )

    return text


async def handle_eva_brand_input(
    chat_id: str,
    user_input: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает ввод марки автомобиля для EVA-ковриков.
    Поддерживает:
    - "99" - следующая страница
    - "00" - предыдущая страница
    - Цифра 1-8 - выбор марки с текущей страницы
    - Текст - поиск марки по всему списку

    Args:
        chat_id: ID чата WhatsApp
        user_input: Ввод пользователя
        config: Конфигурация tenant

    Returns:
        Текст ответа
    """
    user_data = get_user_data(chat_id)
    current_page = user_data.get("brands_page", 1)
    all_brands = user_data.get("all_brands", [])

    # Обработка пагинации
    if user_input == "99":
        # Следующая страница
        total_pages = (len(all_brands) + BRANDS_PER_PAGE - 1) // BRANDS_PER_PAGE
        if current_page < total_pages:
            return await show_brands_page(chat_id, current_page + 1, config, session)
        else:
            return "❌ Это последняя страница. Выберите марку или введите название."

    elif user_input == "00":
        # Предыдущая страница
        if current_page > 1:
            return await show_brands_page(chat_id, current_page - 1, config, session)
        else:
            return "❌ Это первая страница. Выберите марку или введите название."

    # Обработка цифрового выбора
    elif user_input.isdigit():
        choice = int(user_input)

        if 1 <= choice <= BRANDS_PER_PAGE:
            # Вычисляем индекс в полном списке
            start_idx = (current_page - 1) * BRANDS_PER_PAGE
            brand_idx = start_idx + choice - 1

            if brand_idx < len(all_brands):
                selected_brand = all_brands[brand_idx]
                # Сохраняем марку и переходим к выбору модели
                update_user_data(chat_id, {"brand_name": selected_brand})
                set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)

                return await show_models_page(chat_id, 1, selected_brand, config, session)
            else:
                return "❌ Неверный номер. Выберите марку из списка или введите название."
        else:
            return "❌ Неверный номер. Выберите от 1 до 8, или введите название марки."

    # Обработка текстового ввода - fuzzy search по всем маркам
    else:
        brand_input = user_input.strip()

        # Поиск точного совпадения (регистронезависимый)
        exact_match = next((b for b in all_brands if b.lower() == brand_input.lower()), None)

        if exact_match:
            # Точное совпадение найдено
            update_user_data(chat_id, {"brand_name": exact_match})
            set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)

            return await show_models_page(chat_id, 1, exact_match, config, session)
        else:
            # Пробуем fuzzy search
            from difflib import get_close_matches

            matches = get_close_matches(brand_input, all_brands, n=3, cutoff=0.6)

            if matches:
                suggested_brand = matches[0]
                # Сохраняем предложение
                update_user_data(chat_id, {"suggested_brand": suggested_brand})

                return (
                    f"🤔 Марка '{brand_input}' не найдена.\n\n"
                    f"Возможно, вы имели в виду:\n"
                    f"<b>{suggested_brand}</b>\n\n"
                    f"Отправьте:\n"
                    f"1️⃣ - Да, использовать {suggested_brand}\n"
                    f"2️⃣ - Нет, ввести заново\n"
                    f"Меню - Вернуться в главное меню"
                )
            else:
                return (
                    f"❌ Марка '{brand_input}' не найдена.\n\n"
                    f"Попробуйте выбрать из списка или введите другое название.\n\n"
                    f"Отправьте '99' для следующей страницы или 'Меню' для возврата."
                )


async def handle_eva_model_input(
    chat_id: str,
    user_input: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает ввод модели автомобиля для EVA-ковриков.
    Поддерживает:
    - "99" - следующая страница
    - "00" - предыдущая страница
    - Цифра 1-8 - выбор модели с текущей страницы
    - Текст - поиск модели по всему списку

    Args:
        chat_id: ID чата WhatsApp
        user_input: Ввод пользователя
        config: Конфигурация tenant

    Returns:
        Текст ответа
    """
    user_data = get_user_data(chat_id)
    brand_name = user_data.get("brand_name", "")
    current_page = user_data.get("models_page", 1)
    all_models = user_data.get("all_models", [])
    category = user_data.get("category")

    # КРИТИЧЕСКАЯ ПРОВЕРКА: category должна быть установлена!
    if not category:
        logger.warning(f"⚠️ [MODEL_SELECTION] Category не найдена в user_data для чата {chat_id}")
        logger.warning(f"⚠️ [MODEL_SELECTION] user_data: {user_data}")
        return "❌ Ошибка: категория товара не определена. Вернитесь в главное меню."

    # Обработка пагинации
    if user_input == "99":
        # Следующая страница
        total_pages = (len(all_models) + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE
        if current_page < total_pages:
            return await show_models_page(chat_id, current_page + 1, brand_name, config, session)
        else:
            return "❌ Это последняя страница. Выберите модель или введите название."

    elif user_input == "00":
        # Предыдущая страница
        if current_page > 1:
            return await show_models_page(chat_id, current_page - 1, brand_name, config, session)
        else:
            return "❌ Это первая страница. Выберите модель или введите название."

    # Обработка цифрового выбора
    elif user_input.isdigit():
        choice = int(user_input)

        if 1 <= choice <= MODELS_PER_PAGE:
            # Вычисляем индекс в полном списке
            start_idx = (current_page - 1) * MODELS_PER_PAGE
            model_idx = start_idx + choice - 1

            if model_idx < len(all_models):
                selected_model = all_models[model_idx]
                # Сохраняем модель и ищем лекала (БЕЗ fuzzy search!)
                return await search_patterns_for_model(
                    chat_id, selected_model, brand_name, category, config, session,
                    skip_fuzzy=True  # ✅ НЕ запускать fuzzy search для цифрового выбора!
                )
            else:
                return "❌ Неверный номер. Выберите модель из списка или введите название."
        else:
            return "❌ Неверный номер. Выберите от 1 до 8, или введите название модели."

    # Обработка текстового ввода - поиск по всем моделям
    else:
        model_input = user_input.strip()

        # Поиск точного совпадения (регистронезависимый)
        exact_match = next((m for m in all_models if m.lower() == model_input.lower()), None)

        if exact_match:
            # Точное совпадение найдено - ищем лекала (БЕЗ fuzzy search!)
            return await search_patterns_for_model(
                chat_id, exact_match, brand_name, category, config, session,
                skip_fuzzy=True  # ✅ Точное совпадение - fuzzy не нужен
            )
        else:
            # Пробуем fuzzy search по списку моделей
            from difflib import get_close_matches

            matches = get_close_matches(model_input, all_models, n=3, cutoff=0.6)

            if matches:
                suggested_model = matches[0]
                # Сохраняем предложение
                update_user_data(chat_id, {"suggested_model": suggested_model})

                return (
                    f"🤔 Модель '{model_input}' не найдена.\n\n"
                    f"Возможно, вы имели в виду:\n"
                    f"<b>{suggested_model}</b>\n\n"
                    f"Отправьте:\n"
                    f"1️⃣ - Да, использовать {suggested_model}\n"
                    f"2️⃣ - Нет, ввести заново\n"
                    f"Меню - Вернуться в главное меню"
                )
            else:
                return (
                    f"❌ Модель '{model_input}' не найдена.\n\n"
                    f"Попробуйте выбрать из списка или введите другое название.\n\n"
                    f"Отправьте '99' для следующей страницы или 'Меню' для возврата."
                )


async def search_patterns_for_model(
    chat_id: str,
    model_name: str,
    brand_name: str,
    category: str,
    config: Config,
    session: AsyncSession,
    skip_fuzzy: bool = False
) -> str:
    """
    Ищет лекала для выбранной модели и обрабатывает результат.

    Args:
        chat_id: ID чата WhatsApp
        model_name: Название модели
        brand_name: Название марки
        category: Код категории
        config: Конфигурация tenant
        session: AsyncSession для БД
        skip_fuzzy: Если True, НЕ запускать fuzzy search (для цифрового выбора из меню)

    Returns:
        Текст ответа
    """
    # Сохраняем модель
    update_user_data(chat_id, {"model_name": model_name.strip()})

    tenant = await get_tenant_by_slug(session, config.tenant_slug)

    if not tenant:
        clear_state(chat_id)
        return "❌ Ошибка конфигурации. Попробуйте позже."

    # Поиск точных совпадений
    patterns = await search_patterns(
        session,
        brand_name=brand_name,
        model_name=model_name,
        tenant_id=tenant.id,
        category_code=category
    )

    if patterns:
        # Лекала найдены!
        return await handle_patterns_found(chat_id, patterns, brand_name, model_name, config)

    # Точного совпадения нет - пробуем fuzzy search через БД (только если skip_fuzzy=False)
    if not skip_fuzzy:
        brand = await get_brand_by_name(session, brand_name)

        if brand:
            suggested_model, similarity = await fuzzy_search_model(
                session,
                brand_id=brand.id,
                model_name=model_name,
                threshold=85.0
            )

            if suggested_model:
                # Найдена похожая модель
                update_user_data(chat_id, {"suggested_model": suggested_model})

                return (
                    f"🤔 Не удалось найти модель '<b>{model_name}</b>'.\n\n"
                    f"Возможно, вы имели в виду:\n"
                    f"<b>{suggested_model}</b> (схожесть: {similarity:.0f}%)\n\n"
                    f"Отправьте:\n"
                    f"1️⃣ - Да, использовать {suggested_model}\n"
                    f"2️⃣ - Нет, ввести заново\n"
                    f"Меню - Вернуться в главное меню"
                )

    # Fuzzy search отключён или не помог - сразу предлагаем индивидуальный замер
    return await handle_patterns_not_found(chat_id, brand_name, model_name, config)


async def handle_patterns_found(chat_id: str, patterns: list, brand_name: str, model_name: str, config: Config) -> str:
    """
    Обрабатывает случай, когда лекала найдены.
    Предлагает выбрать опции.

    Args:
        chat_id: ID чата WhatsApp
        patterns: Найденные лекала
        brand_name: Марка автомобиля
        model_name: Модель автомобиля
        config: Конфигурация tenant

    Returns:
        Текст ответа
    """
    # Сохраняем patterns
    update_user_data(chat_id, {
        "patterns": patterns,
        "application_type": "Заказ товара"  # ✅ Тип заявки для Airtable
    })

    # Переключаем состояние
    set_state(chat_id, WhatsAppState.EVA_SELECTING_OPTIONS)

    return (
        f"✅ <b>Отличные новости!</b>\n\n"
        f"У нас есть лекала для <b>{brand_name} {model_name}</b>!\n\n"
        f"Найдено вариантов: {len(patterns)}\n\n"
        f"📝 Шаг 3/3: Выберите дополнительные опции:\n\n"
        f"1️⃣ - ✅ С бортами (рекомендуем)\n"
        f"2️⃣ - ❌ Без бортов\n"
        f"3️⃣ - ❓ Не знаю, нужна консультация"
    )


async def handle_patterns_not_found(chat_id: str, brand_name: str, model_name: str, config: Config) -> str:
    """
    Обрабатывает случай, когда лекала не найдены.
    Предлагает индивидуальный замер.

    Args:
        chat_id: ID чата WhatsApp
        brand_name: Марка автомобиля
        model_name: Модель автомобиля
        config: Конфигурация tenant

    Returns:
        Текст ответа
    """
    # Переключаем на ожидание имени для индивидуального замера
    set_state(chat_id, WhatsAppState.WAITING_FOR_NAME)
    update_user_data(chat_id, {
        "is_individual_measure": True,
        "application_type": "Индивидуальный замер"  # ✅ Тип заявки для Airtable
    })

    return (
        f"💡 <b>Отличная новость!</b>\n\n"
        f"Похоже, готовых лекал для <b>{brand_name} {model_name}</b> "
        f"у нас пока нет в базе.\n\n"
        f"<b>Но это не проблема!</b> 🎯\n\n"
        f"Мы специализируемся на индивидуальных заказах и "
        f"создадим коврики специально для вашего автомобиля!\n\n"
        f"✨ <b>Преимущества индивидуального замера:</b>\n"
        f"• Идеальная посадка под ваш автомобиль\n"
        f"• Учет всех особенностей салона\n"
        f"• Качество как у готовых лекал\n"
        f"• Выезд мастера для замеров\n\n"
        f"📝 Шаг 1/2: Введите ваше имя"
    )


async def handle_option_selection(
    chat_id: str,
    option: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает выбор опции (с/без бортов, консультация).

    Args:
        chat_id: ID чата WhatsApp
        option: Выбранная опция (1-3)
        config: Конфигурация tenant

    Returns:
        Текст ответа
    """
    user_data = get_user_data(chat_id)
    brand_name = user_data.get("brand_name", "")
    model_name = user_data.get("model_name", "")
    category = user_data.get("category")  # КРИТИЧНО: без fallback!
    category_name = user_data.get("category_name", "EVA-коврики")

    option_mapping = {
        "1": "with_borders",
        "2": "without_borders",
        "3": "need_consultation"
    }

    option_code = option_mapping.get(option)

    if not option_code:
        return (
            f"❌ Неверный выбор. Пожалуйста, отправьте цифру от 1 до 3.\n\n"
            f"1️⃣ - ✅ С бортами (рекомендуем)\n"
            f"2️⃣ - ❌ Без бортов\n"
            f"3️⃣ - ❓ Не знаю, нужна консультация"
        )

    # Сохраняем выбор
    update_user_data(chat_id, {"selected_option": option_code})

    option_names = {
        "with_borders": "С бортами",
        "without_borders": "Без бортов",
        "need_consultation": "Требуется консультация"
    }

    option_text = option_names[option_code]

    if option_code == "need_consultation":
        # Консультация - сразу переход к контактам
        set_state(chat_id, WhatsAppState.WAITING_FOR_NAME)

        return (
            f"📋 <b>Ваша заявка:</b>\n\n"
            f"• Товар: {category_name}\n"
            f"• Автомобиль: {brand_name} {model_name}\n"
            f"• Опция: {option_text}\n\n"
            f"Для оформления заявки нам нужна ваша контактная информация.\n\n"
            f"📝 Шаг 1/2: Введите ваше имя"
        )

    tenant = await get_tenant_by_slug(session, config.tenant_slug)

    if not tenant:
        return "❌ Ошибка конфигурации. Попробуйте позже."

    # КРИТИЧЕСКАЯ ПРОВЕРКА: category должна быть в user_data!
    if not category:
        logger.error(f"❌ [ORDER_SUMMARY] Category не найдена в user_data для чата {chat_id}")
        logger.error(f"❌ [ORDER_SUMMARY] user_data: {user_data}")
        return "❌ Ошибка: категория товара не определена. Вернитесь в главное меню."

    model, body_type = await get_model_with_body_type(session, brand_name, model_name)

    selected_options = {
        'with_borders': (option_code == "with_borders"),
        'third_row': False
    }

    logger.info(f"💰 [PRICE_CALC] Расчёт цены для category={category}, body_type={body_type.code if body_type else 'sedan'}")
    total_price, price_breakdown = await calculate_total_price(
        session,
        tenant.id,
        category,  # ✅ ИЗ FSM STATE, БЕЗ ХАРДКОДА!
        body_type.code if body_type else 'sedan',
        selected_options
    )

    logger.info(f"💰 [PRICE_CALC] Итоговая цена: {total_price} сом")
    logger.info(f"💰 [PRICE_CALC] Разбивка: {price_breakdown}")

    # Сохраняем цену
    update_user_data(chat_id, {"total_price": int(total_price), "price_breakdown": price_breakdown})

    # Подтверждение заказа
    set_state(chat_id, WhatsAppState.EVA_CONFIRMING_ORDER)

    # Проверяем флаг show_price_in_summary
    show_price = config.i18n.get("company.show_price_in_summary")
    if show_price is None:
        show_price = True  # По умолчанию true для обратной совместимости
    logger.info(f"💰 [ORDER_SUMMARY] show_price_in_summary={show_price}")

    # Формируем сводку с условным показом цены
    summary_parts = [
        f"📋 <b>Сводка вашего заказа:</b>\n",
        f"🚗 <b>Автомобиль:</b> {brand_name} {model_name}",
        f"📦 <b>Товар:</b> {category_name}",
        f"⚙️ <b>Опция:</b> {option_text}"
    ]

    # Добавляем цену только если флаг = true
    if show_price:
        summary_parts.append(f"💰 <b>Итоговая стоимость:</b> {total_price} сом")

    summary_parts.extend([
        "\nГотовы оформить заказ? 🎉\n",
        "Отправьте:",
        "1️⃣ - Да, оформить заказ",
        "Меню - Вернуться в главное меню"
    ])

    return "\n".join(summary_parts)


async def handle_order_confirmation(chat_id: str, confirmation: str, config: Config) -> str:
    """
    Обрабатывает подтверждение заказа.

    Args:
        chat_id: ID чата WhatsApp
        confirmation: Ответ пользователя
        config: Конфигурация tenant

    Returns:
        Текст ответа
    """
    # Принимаем разные варианты подтверждения
    positive_answers = ["1", "да", "yes", "ок", "ok", "+", "конечно", "давай", "давайте"]

    logger.info(f"🔍 [ORDER_CONFIRMATION] User {chat_id} answered: '{confirmation}'")

    if confirmation.lower() in positive_answers:
        # Переход к сбору контактов
        logger.info(f"✅ [ORDER_CONFIRMATION] Подтверждение принято, переход к сбору контактов")
        set_state(chat_id, WhatsAppState.WAITING_FOR_NAME)

        return (
            "✅ Отлично! Чтобы завершить оформление, напишите, пожалуйста, ваше имя.\n\n"
            "Ваш номер телефона мы возьмём автоматически из WhatsApp. 😊"
        )
    else:
        logger.warning(f"⚠️ [ORDER_CONFIRMATION] Неверный ответ: '{confirmation}'")
        return (
            "❌ Неверный выбор.\n\n"
            "Отправьте:\n"
            "1️⃣ - Да, оформить заказ\n"
            "Меню - Вернуться в главное меню"
        )


async def send_whatsapp_order_to_airtable(config: Config, user_data: dict, client_name: str,
                                          client_phone: str, chat_id: str, session) -> bool:
    """
    Сохраняет заявку из WhatsApp в Airtable.

    КРИТИЧЕСКИ ВАЖНО: Эта функция теперь использует ЦЕНТРАЛИЗОВАННУЮ функцию
    build_application_data() для гарантии корректности данных!

    Args:
        config: Конфигурация tenant
        user_data: Данные заказа пользователя из FSM state
        client_name: Имя клиента
        client_phone: Телефон клиента
        chat_id: ID чата WhatsApp (для логирования)
        session: AsyncSession для работы с БД

    Returns:
        bool: True если сохранение успешно, False иначе
    """
    try:
        logger.info(f"🔍 [SEND_TO_AIRTABLE] === НАЧАЛО СОХРАНЕНИЯ ЗАЯВКИ ===")
        logger.info(f"🔍 [SEND_TO_AIRTABLE] Tenant: {config.tenant_slug}")
        logger.info(f"🔍 [SEND_TO_AIRTABLE] Клиент: {client_name} (WhatsApp: {chat_id})")

        # Проверяем конфигурацию Airtable
        if not config.airtable:
            logger.error(f"❌ [SEND_TO_AIRTABLE] Airtable не настроен для tenant={config.tenant_slug}")
            return False

        # Импортируем необходимые модули
        import sys
        from pathlib import Path
        core_path = Path(__file__).parent.parent.parent / "packages"
        if str(core_path) not in sys.path:
            sys.path.insert(0, str(core_path))

        from core.services import AirtableService
        from core.utils.application_builder import build_application_data

        # ═══════════════════════════════════════════════════════════════
        # КРИТИЧЕСКИ ВАЖНО: Используем ЕДИНУЮ функцию для сборки данных!
        # ═══════════════════════════════════════════════════════════════

        logger.info("🏗️  [SEND_TO_AIRTABLE] Вызываю build_application_data()...")

        airtable_data = await build_application_data(
            user_data=user_data,
            client_name=client_name,
            client_phone=client_phone,
            config=config,
            session=session,
            source="WhatsApp"
        )

        if not airtable_data:
            logger.error(f"❌ [SEND_TO_AIRTABLE] build_application_data() вернула None!")
            return False

        # Инициализируем сервис Airtable
        airtable_service = AirtableService(
            api_key=config.airtable.api_key,
            base_id=config.airtable.base_id,
            table_name=config.airtable.table_name
        )

        logger.info("🔄 [SEND_TO_AIRTABLE] Отправка в Airtable...")

        # Сохраняем в Airtable
        record_id = await airtable_service.create_application(airtable_data)

        if record_id:
            logger.info(f"✅ [SEND_TO_AIRTABLE] Заявка успешно сохранена! Record ID: {record_id}")
            logger.info(f"✅ [SEND_TO_AIRTABLE] Клиент: {client_name} ({client_phone})")
            logger.info(f"✅ [SEND_TO_AIRTABLE] Категория: {airtable_data.get('product_category', 'Не указано')}")
            logger.info(f"✅ [SEND_TO_AIRTABLE] Автомобиль: {airtable_data.get('car', 'Не указано')}")
            logger.info(f"🔍 [SEND_TO_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (SUCCESS) ===")
            return True
        else:
            logger.error(f"❌ [SEND_TO_AIRTABLE] Не удалось сохранить заявку в Airtable")
            logger.error(f"🔍 [SEND_TO_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
            return False

    except ValueError as e:
        # Ошибка валидации из build_application_data
        logger.error(f"❌ [SEND_TO_AIRTABLE] ОШИБКА ВАЛИДАЦИИ: {e}")
        logger.error(f"🔍 [SEND_TO_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
        return False

    except Exception as e:
        logger.exception("!!! КРИТИЧЕСКАЯ ОШИБКА СОХРАНЕНИЯ В AIRTABLE !!!")
        logger.error(f"❌ [SEND_TO_AIRTABLE] Tenant: {config.tenant_slug}")
        logger.error(f"❌ [SEND_TO_AIRTABLE] Тип ошибки: {type(e).__name__}")
        logger.error(f"❌ [SEND_TO_AIRTABLE] Сообщение: {str(e)}")
        logger.error(f"🔍 [SEND_TO_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
        return False


async def send_callback_request_to_airtable(config: Config, user_data: dict, client_name: str,
                                            client_phone: str, chat_id: str) -> bool:
    """
    Сохраняет запрос на обратный звонок в Airtable.

    Args:
        config: Конфигурация tenant
        user_data: Данные пользователя
        client_name: Имя клиента
        client_phone: Телефон клиента
        chat_id: ID чата WhatsApp (для логирования)

    Returns:
        bool: True если сохранение успешно, False иначе
    """
    try:
        logger.info(f"🔍 [CALLBACK_AIRTABLE] === НАЧАЛО СОХРАНЕНИЯ CALLBACK REQUEST ===")
        logger.info(f"🔍 [CALLBACK_AIRTABLE] Tenant: {config.tenant_slug}")
        logger.info(f"🔍 [CALLBACK_AIRTABLE] Клиент: {client_name} (WhatsApp: {chat_id})")

        # Проверяем конфигурацию Airtable
        if not config.airtable:
            logger.error(f"❌ [CALLBACK_AIRTABLE] Airtable не настроен для tenant={config.tenant_slug}")
            return False

        # Извлекаем детали запроса
        callback_details = user_data.get("callback_details", "Не указано")

        logger.info(f"📝 [CALLBACK_AIRTABLE] Детали запроса: {callback_details}")

        # Импортируем AirtableService
        import sys
        from pathlib import Path
        core_path = Path(__file__).parent.parent.parent / "packages"
        if str(core_path) not in sys.path:
            sys.path.insert(0, str(core_path))

        from core.services import AirtableService

        # Инициализируем сервис Airtable
        airtable_service = AirtableService(
            api_key=config.airtable.api_key,
            base_id=config.airtable.base_id,
            table_name=config.airtable.table_name
        )

        # Формируем данные для Airtable
        product_full_name = "Запрос на обратный звонок"
        details_text = callback_details

        airtable_data = {
            "client_name": client_name,
            "client_phone": client_phone,
            "source": "WhatsApp",
            "project": config.tenant_slug.upper(),
            "product": product_full_name,
            "details": details_text
        }

        logger.info("🔄 [CALLBACK_AIRTABLE] Попытка сохранить в Airtable...")

        # Сохраняем в Airtable
        record_id = await airtable_service.create_application(airtable_data)

        if record_id:
            logger.info(f"✅ [CALLBACK_AIRTABLE] Callback request успешно сохранён. Record ID: {record_id}")
            logger.info(f"   Клиент: {client_name} ({client_phone})")
            logger.info(f"   Детали: {callback_details}")
            logger.info(f"🔍 [CALLBACK_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (SUCCESS) ===")
            return True
        else:
            logger.error(f"❌ [CALLBACK_AIRTABLE] Не удалось сохранить callback request")
            logger.error(f"🔍 [CALLBACK_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
            return False

    except Exception as e:
        logger.exception("!!! КРИТИЧЕСКАЯ ОШИБКА СОХРАНЕНИЯ CALLBACK REQUEST В AIRTABLE !!!")
        logger.error(f"❌ [CALLBACK_AIRTABLE] Tenant: {config.tenant_slug}")
        logger.error(f"❌ [CALLBACK_AIRTABLE] Тип ошибки: {type(e).__name__}")
        logger.error(f"❌ [CALLBACK_AIRTABLE] Сообщение: {str(e)}")
        logger.error(f"🔍 [CALLBACK_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
        return False


async def handle_name_input(chat_id: str, name: str, config: Config, session) -> str:
    """
    Обрабатывает ввод имени клиента.
    Для WhatsApp автоматически извлекает номер телефона из chatId.

    Args:
        chat_id: ID чата WhatsApp
        name: Введённое имя
        config: Конфигурация tenant
        session: AsyncSession для работы с БД

    Returns:
        Текст ответа
    """
    logger.info(f"🎯 [HANDLE_NAME_INPUT] ===== НАЧАЛО ОБРАБОТКИ ИМЕНИ =====")
    logger.info(f"🎯 [HANDLE_NAME_INPUT] Chat ID: {chat_id}")
    logger.info(f"🎯 [HANDLE_NAME_INPUT] Введённое имя: {name}")

    # Сохраняем имя
    update_user_data(chat_id, {"client_name": name.strip()})
    logger.info(f"✅ [HANDLE_NAME_INPUT] Имя сохранено в user_data")

    # ОПТИМИЗАЦИЯ ДЛЯ WHATSAPP:
    # Извлекаем номер телефона из chatId (например, "996777510804@c.us" -> "+996777510804")
    phone_number = extract_phone_from_chat_id(chat_id)
    logger.info(f"📱 [HANDLE_NAME_INPUT] Извлечённый телефон: {phone_number}")

    update_user_data(chat_id, {"client_phone": phone_number})
    logger.info(f"✅ [HANDLE_NAME_INPUT] Телефон сохранён в user_data")

    # Получаем все данные для заявки
    user_data = get_user_data(chat_id)
    logger.info(f"📋 [HANDLE_NAME_INPUT] Все данные пользователя: {user_data}")

    # Проверяем тип заявки
    request_type = user_data.get("request_type", "order")
    logger.info(f"🔍 [HANDLE_NAME_INPUT] Тип заявки: {request_type}")

    # Сохраняем заявку в Airtable через новый airtable_manager
    try:
        logger.info(f"📤 [HANDLE_NAME_INPUT] ===== ПОДГОТОВКА К ОТПРАВКЕ В AIRTABLE =====")
        logger.info(f"📤 [HANDLE_NAME_INPUT] Клиент: {name.strip()}")
        logger.info(f"📤 [HANDLE_NAME_INPUT] Телефон: {phone_number}")
        logger.info(f"📤 [HANDLE_NAME_INPUT] Tenant: {config.bot.tenant_slug}")
        logger.info(f"📤 [HANDLE_NAME_INPUT] Тип заявки: {request_type}")

        # Собираем данные для отправки в Airtable
        lead_data = {
            "name": name.strip(),
            "phone": phone_number,
            "username": chat_id,  # В WhatsApp chat_id — это и есть уникальный идентификатор
        }

        # Добавляем данные о товаре и автомобиле (если есть)
        if "selected_category" in user_data:
            lead_data["category"] = user_data["selected_category"]
            logger.info(f"📤 [HANDLE_NAME_INPUT] Категория: {user_data['selected_category']}")

        if "selected_brand" in user_data:
            lead_data["car_brand"] = user_data["selected_brand"]
            logger.info(f"📤 [HANDLE_NAME_INPUT] Марка: {user_data['selected_brand']}")

        if "selected_model" in user_data:
            lead_data["car_model"] = user_data["selected_model"]
            logger.info(f"📤 [HANDLE_NAME_INPUT] Модель: {user_data['selected_model']}")

        # Добавляем опции (если есть)
        if "selected_options" in user_data:
            options_list = user_data["selected_options"]
            if isinstance(options_list, list):
                lead_data["options"] = ", ".join(options_list)
            else:
                lead_data["options"] = str(options_list)
            logger.info(f"📤 [HANDLE_NAME_INPUT] Опции: {lead_data['options']}")

        # Добавляем цену (если есть)
        if "total_price" in user_data and user_data["total_price"]:
            lead_data["price"] = user_data["total_price"]
            logger.info(f"📤 [HANDLE_NAME_INPUT] Цена: {user_data['total_price']} сом")

        # Отправляем в Airtable
        logger.info(f"🚀 [HANDLE_NAME_INPUT] Вызов create_lead...")
        record_id = await create_lead(lead_data, tenant_slug=config.bot.tenant_slug)

        if record_id:
            logger.info(f"✅ [HANDLE_NAME_INPUT] ===== ЗАЯВКА УСПЕШНО СОХРАНЕНА В AIRTABLE =====")
            logger.info(f"✅ [HANDLE_NAME_INPUT] Record ID: {record_id}")
        else:
            logger.error("❌ [HANDLE_NAME_INPUT] ===== НЕ УДАЛОСЬ СОХРАНИТЬ ЗАЯВКУ В AIRTABLE =====")
            logger.error(f"❌ [HANDLE_NAME_INPUT] create_lead вернул None")

    except Exception as e:
        logger.exception("!!! [HANDLE_NAME_INPUT] КРИТИЧЕСКАЯ ОШИБКА СОХРАНЕНИЯ ЗАЯВКИ В AIRTABLE !!!")
        logger.error(f"❌ [HANDLE_NAME_INPUT] Тип ошибки: {type(e).__name__}")
        logger.error(f"❌ [HANDLE_NAME_INPUT] Сообщение: {str(e)}")
        logger.error(f"❌ [HANDLE_NAME_INPUT] Трейсбек выше ^^^")

    # Очищаем состояние
    clear_state(chat_id)

    # Очищаем историю диалога в DialogMemory после успешного завершения заказа
    try:
        memory = get_memory()
        memory.clear_history(chat_id)
        logger.info(f"🗑️ [MEMORY] Очищена история диалога для {chat_id} после завершения заказа")
    except Exception as e:
        logger.warning(f"⚠️ [MEMORY] Не удалось очистить историю: {e}")

    # Финальное сообщение
    return (
        f"✅ Спасибо, {name}!\n\n"
        f"Мы получили ваши данные и скоро свяжемся с вами "
        f"для подтверждения заказа.\n\n"
        f"Обычно это занимает 5-10 минут. 😊\n\n"
        f"Отправьте \"Меню\" для возврата в главное меню."
    )
