"""
IVR Handlers для 5deluxe - простое цифровое меню без AI.

Обрабатывает входящие текстовые сообщения с цифрами и переводит их
в вызовы существующей бизнес-логики из packages/core/.
"""

import sys
from pathlib import Path
import logging

# Добавляем путь к packages
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "packages"))

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Config
from core.ai.assistant import AssistantManager, get_or_create_thread
from core.ai.response_parser import detect_response_type, extract_order_data
from smart_input_handler import (
    handle_text_or_digit_input,
    apply_two_level_fuzzy,
    generate_confirmation_message,
    generate_not_found_message
)
from core.keyboards.whatsapp_ui import (
    get_whatsapp_main_menu,
    get_whatsapp_options_menu,
    get_whatsapp_confirmation_menu,
    get_whatsapp_brand_selection_text,
    get_whatsapp_model_selection_text,
    get_whatsapp_fuzzy_suggestion_text,
    format_whatsapp_message
)
from core.db.queries import (
    get_tenant_by_slug,
    get_unique_brands_from_db,
    get_models_for_brand_from_db,
    search_patterns,
    fuzzy_search_model,
    get_brand_by_name
)

from state_manager import (
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


async def handle_5deluxe_message(
    chat_id: str,
    text: str,
    config: Config,
    session: AsyncSession,
    sender_name: str = "Гость"
) -> str:
    """
    Главный роутер для обработки сообщений от 5deluxe.
    Определяет текущее состояние пользователя и вызывает соответствующий обработчик.

    Args:
        chat_id: ID чата WhatsApp
        text: Текст сообщения от пользователя
        config: Конфигурация tenant
        session: Сессия БД
        sender_name: Имя отправителя из вебхука WhatsApp

    Returns:
        str: Текст ответа для отправки пользователю
    """
    # Сохраняем sender_name в user_data при первом контакте
    user_data = get_user_data(chat_id)
    if not user_data.get("sender_name"):
        update_user_data(chat_id, {"sender_name": sender_name})
    # 🔍 СЕКРЕТНАЯ ОТЛАДОЧНАЯ КОМАНДА: ask_ai: (только для админов)
    if text.lower().startswith("ask_ai:"):
        return await handle_ask_ai_whatsapp(chat_id, text, config)
    
    current_state = get_state(chat_id)
    logger.info(f"[5DELUXE_IVR] User {chat_id} in state: {current_state}, message: '{text}'")

    # Обработка команды RESET (только для админов)
    if text.lower() in ["reset_dialog", "/reset", "reset"]:
        # Проверка прав администратора (по номеру телефона в chat_id)
        # Формат chat_id: "996XXXXXXXXX@c.us"
        phone_number = chat_id.split("@")[0] if "@" in chat_id else chat_id
        admin_phones = [str(admin_id) for admin_id in []]
        
        if phone_number not in admin_phones:
            logger.warning(f"[RESET] Unauthorized access attempt from {chat_id}")
            return "⛔️ У вас нет прав для использования этой команды."
        
        logger.info(f"[RESET] Admin {chat_id} requested dialog reset")
        clear_state(chat_id)
        
        # Попытка очистить историю AI (если используется)
        try:
            from core.ai.memory import get_memory
            memory = get_memory()
            memory.clear_history(chat_id)
            logger.info(f"[RESET] AI memory cleared for {chat_id}")
        except Exception as e:
            logger.debug(f"[RESET] AI memory not available: {e}")
        
        reset_message = (
            "🔄 *Диалог сброшен!*\n\n"
            "Все данные удалены. Начинаем с чистого листа.\n\n"
            "Выберите категорию товаров:"
        )
        return reset_message + "\n" + (await show_main_menu(chat_id, config))

    # Обработка команд "Меню" / "Start" - короткое меню
    if text.lower() in ["меню", "menu", "/start", "start"]:
        clear_state(chat_id)
        return await show_main_menu(chat_id, config, is_return=True)

    # UX FIX: Для новых пользователей (IDLE) - длинное приветствие
    if current_state == WhatsAppState.IDLE:
        logger.info(f"[5DELUXE_IVR] New user detected, showing first contact welcome")
        return await show_main_menu(chat_id, config, is_first_contact=True)

    # Роутинг по состояниям
    if current_state == WhatsAppState.MAIN_MENU:
        return await handle_main_menu_input(chat_id, text, config, session)

    elif current_state == WhatsAppState.EVA_WAITING_BRAND:
        return await handle_brand_selection(chat_id, text, config, session)

    elif current_state == WhatsAppState.EVA_WAITING_MODEL:
        return await handle_model_selection(chat_id, text, config, session)

    elif current_state == WhatsAppState.EVA_SELECTING_OPTIONS:
        return await handle_options_selection(chat_id, text, config, session)

    elif current_state == WhatsAppState.EVA_CONFIRMING_ORDER:
        return await handle_order_confirmation(chat_id, text, config)

    # УДАЛЕНО: WAITING_FOR_NAME и WAITING_FOR_PHONE - больше не используются в WhatsApp

    elif current_state == WhatsAppState.CONTACT_MANAGER:
        return await handle_contact_manager(chat_id, text, config)

    else:
        logger.warning(f"[5DELUXE_IVR] Unknown state: {current_state}")
        return await show_main_menu(chat_id, config)


async def show_main_menu(chat_id: str, config: Config, is_first_contact: bool = False, is_return: bool = False) -> str:
    """
    Показывает главное меню.

    Args:
        chat_id: ID чата WhatsApp
        config: Конфигурация tenant
        is_first_contact: True для длинного приветствия (первый контакт)
        is_return: True для короткого меню (команда "Меню")

    Returns:
        str: Текст главного меню
    """
    i18n = config.i18n
    set_state(chat_id, WhatsAppState.MAIN_MENU)

    # Выбираем правильный текст
    if is_first_contact:
        # Приветствие с ВСТРОЕННЫМ меню - не добавляем menu_text!
        return i18n.get('start.first_contact_welcome')
    elif is_return:
        # Короткое меню при возврате
        welcome_text = f"{i18n.get('start.main_menu')}\n"
    else:
        # Стандартное меню
        welcome_text = f"{i18n.get('start.main_menu')}\n"

    menu_text, _ = get_whatsapp_main_menu(i18n)
    return format_whatsapp_message(welcome_text, menu_text)


async def handle_main_menu_input(
    chat_id: str,
    text: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает выбор в главном меню.

    Args:
        chat_id: ID чата WhatsApp
        text: Введенная цифра
        config: Конфигурация tenant

    Returns:
        str: Текст ответа
    """
    i18n = config.i18n
    _, callback_mapping = get_whatsapp_main_menu(i18n)

    if text not in callback_mapping:
        return f"Неверный выбор. Пожалуйста, введите цифру от 1 до {len(callback_mapping)}."

    callback_data = callback_mapping[text]

    # Обрабатываем callback_data
    if callback_data.startswith("category:"):
        category = callback_data.split(":")[1]
        return await start_category_flow(chat_id, category, config, session)

    elif callback_data == "action:contact_manager":
        return await handle_contact_manager_request(chat_id, config)

    else:
        return "Эта функция пока не реализована."


async def start_category_flow(
    chat_id: str,
    category: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Начинает сценарий заказа для выбранной категории.
    
    Для 5deluxe все категории используют единый flow:
    1. Выбор марки
    2. Выбор модели
    3. Поиск лекал
    4. Оформление заказа

    Args:
        chat_id: ID чата WhatsApp
        category: Код категории
        config: Конфигурация tenant

    Returns:
        str: Текст с предложением выбрать марку
    """
    i18n = config.i18n

    # Сохраняем категорию
    category_names = {
        "5d_mats": i18n.get("buttons.categories.5d_mats"),
        "premium_covers": i18n.get("buttons.categories.premium_covers"),
        "alcantara_dash": i18n.get("buttons.categories.alcantara_dash"),
        "eva_mats": i18n.get("buttons.categories.eva_mats")
    }

    category_name = category_names.get(category, category)

    update_user_data(chat_id, {
        "category": category,
        "category_name": category_name
    })

    tenant = await get_tenant_by_slug(session, config.tenant_slug)

    if not tenant:
        return "Ошибка конфигурации. Попробуйте позже."

    brands_list = await get_unique_brands_from_db(tenant.id, session)

    if not brands_list:
        return "К сожалению, база марок пуста. Свяжитесь с менеджером."

    # Показываем первую страницу марок
    return await show_brands_page(chat_id, 1, brands_list, config)


async def show_brands_page(chat_id: str, page: int, brands_list: list, config: Config) -> str:
    """
    Показывает страницу с марками.

    Args:
        chat_id: ID чата WhatsApp
        page: Номер страницы
        brands_list: Полный список марок
        config: Конфигурация tenant

    Returns:
        str: Текст с пагинированным списком марок
    """
    i18n = config.i18n

    # Пагинация
    total_brands = len(brands_list)
    total_pages = (total_brands + BRANDS_PER_PAGE - 1) // BRANDS_PER_PAGE

    start_idx = (page - 1) * BRANDS_PER_PAGE
    end_idx = start_idx + BRANDS_PER_PAGE
    brands_on_page = brands_list[start_idx:end_idx]

    # Генерируем меню
    menu_text, callback_mapping = get_whatsapp_brand_selection_text(
        brands_on_page, page, total_pages, i18n
    )

    # Сохраняем состояние
    set_state(chat_id, WhatsAppState.EVA_WAITING_BRAND)
    update_user_data(chat_id, {
        "brands_page": page,
        "brands_list": brands_list,
        "brands_callback_mapping": callback_mapping
    })

    user_data = get_user_data(chat_id)
    category_name = user_data.get("category_name", "продукта")

    intro = f"Вы выбрали: {category_name}"
    return format_whatsapp_message(intro, menu_text)


async def handle_jump_with_model(
    chat_id: str,
    brand_name: str,
    model_input: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает "ПРЫЖОК ЧЕРЕЗ ШАГИ" когда AI извлек марку И модель одновременно.
    
    Args:
        chat_id: ID чата
        brand_name: Подтвержденная марка (уже прошла fuzzy >70%)
        model_input: Модель от AI (нужно проверить через fuzzy)
        config: Конфигурация
        session: Сессия БД
        
    Returns:
        str: Ответ пользователю
    """
    logger.info(f"[🚀 JUMP] Processing jump: {brand_name} + {model_input}")
    
    # Получаем список моделей для данной марки
    tenant = await get_tenant_by_slug(session, config.tenant_slug)
    if not tenant:
        return "Ошибка конфигурации. Попробуйте позже."
    
    models_list = await get_models_for_brand_from_db(brand_name, tenant.id, session)
    
    if not models_list:
        logger.warning(f"[🚀 JUMP] No models for {brand_name} - fallback to normal flow")
        # Нет моделей - обычный флоу
        return await process_brand(chat_id, brand_name, config, session)
    
    # Применяем двухуровневый fuzzy к модели
    model_fuzzy = apply_two_level_fuzzy(model_input, models_list, 70.0, 60.0)
    
    if model_fuzzy["action"] == "apply":
        # >70% - автоматически применяем, ПРЫЖОК завершен успешно!
        model_name = model_fuzzy["value"]
        logger.info(
            f"[🚀 JUMP] ✅ Success! Auto-matched model: '{model_input}' → '{model_name}' "
            f"({model_fuzzy['similarity']:.1f}%)"
        )
        
        # Сохраняем обе выбранные значения
        update_user_data(chat_id, {
            "brand_name": brand_name,
            "model_name": model_name
        })
        
        # ПРЫЖОК - сразу к поиску лекал
        return await process_model(chat_id, model_name, config, session)
        
    elif model_fuzzy["action"] == "ask":
        # 60-70% - спрашиваем подтверждение по модели
        logger.info(
            f"[🚀 JUMP] Need model confirmation: '{model_input}' → '{model_fuzzy['value']}' "
            f"({model_fuzzy['similarity']:.1f}%)"
        )
        
        # Сохраняем марку, спрашиваем про модель
        update_user_data(chat_id, {
            "brand_name": brand_name,
            "suggested_model": model_fuzzy["value"],
            "original_model_input": model_input
        })
        set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)
        
        return (
            f"✅ Марка: {brand_name}\n"
            f"{generate_confirmation_message('model', model_input, model_fuzzy['value'], model_fuzzy['similarity'])}"
        )
        
    else:
        # <60% - модель не найдена, переходим к обычному выбору модели
        logger.warning(f"[🚀 JUMP] Model not found: '{model_input}' - showing models list")
        update_user_data(chat_id, {"brand_name": brand_name})
        return await process_brand(chat_id, brand_name, config, session)


async def handle_brand_selection(
    chat_id: str,
    text: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает выбор марки используя УНИФИЦИРОВАННУЮ "умную" логику.

    Args:
        chat_id: ID чата WhatsApp
        text: Введенная цифра или текст
        config: Конфигурация tenant
        session: Сессия БД

    Returns:
        str: Текст ответа
    """
    i18n = config.i18n
    user_data = get_user_data(chat_id)
    callback_mapping = user_data.get("brands_callback_mapping", {})
    brands_list = user_data.get("brands_list", [])
    category_name = user_data.get("category_name", "автоаксессуары")
    
    # === ОБРАБОТКА ПОДТВЕРЖДЕНИЯ (для схожести 60-70%) ===
    suggested_brand = user_data.get("suggested_brand")
    if suggested_brand and text in ["1", "2"]:
        if text == "1":
            # Подтвердил
            update_user_data(chat_id, {"suggested_brand": None, "original_input": None})
            return await process_brand(chat_id, suggested_brand, config, session)
        elif text == "2":
            # Отказался
            update_user_data(chat_id, {"suggested_brand": None, "original_input": None})
            return "Введите название марки еще раз:"
    
    # === ПРОВЕРКА: ЦИФРОВОЙ ВВОД (до AI) ===
    # КРИТИЧЕСКИ ВАЖНО: проверяем цифры ДО вызова AI!
    if text.strip() in callback_mapping:
        logger.info(f"[BRAND_SELECT] Digit input: '{text}' -> processing directly without AI")
        callback_data = callback_mapping[text.strip()]
        
        # Пагинация
        if callback_data.startswith("brands_page:"):
            page = int(callback_data.split(":")[1])
            return await show_brands_page(chat_id, page, brands_list, config)
        
        # Выбор марки
        elif callback_data.startswith("brand:"):
            brand_name = callback_data.split(":", 1)[1]
            return await process_brand(chat_id, brand_name, config, session)
    
    # === УНИФИЦИРОВАННАЯ ОБРАБОТКА через handle_text_or_digit_input (ONLY for text) ===
    logger.info(f"[BRAND_SELECT] Text input detected: '{text}' -> using AI+Fuzzy")
    result = await handle_text_or_digit_input(
        user_input=text.strip(),
        context="brand",
        chat_id=chat_id,
        callback_mapping=callback_mapping,
        database_list=brands_list,
        category_name=category_name,
        brand_name=None,
        session=session,
        config=config  # Передаем для заглушек
    )
    
    result_type = result.get("type")
    
    # === ОБРАБОТКА "ПРЫЖКА ЧЕРЕЗ ШАГИ" (марка+модель одновременно) ===
    if result_type == "jump":
        brand_ai = result.get("brand")
        model_ai = result.get("model")
        
        logger.info(f"[🚀 JUMP] Detected both: '{brand_ai}' + '{model_ai}'")
        
        # Проверяем марку через fuzzy
        brand_fuzzy = apply_two_level_fuzzy(brand_ai, brands_list, 70.0, 60.0)
        
        if brand_fuzzy["action"] == "apply":
            # Марка >70% - переходим к обработке модели
            brand_name = brand_fuzzy["value"]
            return await handle_jump_with_model(
                chat_id, brand_name, model_ai, config, session
            )
        elif brand_fuzzy["action"] == "ask":
            # Марка 60-70% - спрашиваем подтверждение
            update_user_data(chat_id, {
                "suggested_brand": brand_fuzzy["value"],
                "pending_model": model_ai  # Сохраняем модель для последующего прыжка
            })
            set_state(chat_id, WhatsAppState.EVA_WAITING_BRAND)
            return generate_confirmation_message(
                "brand", text, brand_fuzzy["value"], brand_fuzzy["similarity"]
            )
        else:
            # Марка не найдена
            return generate_not_found_message("brand", text)
    
    # === ОБРАБОТКА ТЕКСТОВОГО ВВОДА (>70%) ===
    elif result_type == "text_auto":
        brand_name = result.get("value")
        logger.info(f"[BRAND_AUTO] Auto-apply: '{brand_name}' ({result.get('similarity'):.1f}%)")
        return await process_brand(chat_id, brand_name, config, session)
    
    # === ОБРАБОТКА ТЕКСТОВОГО ВВОДА (60-70%) ===
    elif result_type == "text_ask":
        suggested_value = result.get("value")
        similarity = result.get("similarity")
        
        logger.info(f"[BRAND_ASK] Need confirmation: '{suggested_value}' ({similarity:.1f}%)")
        
        update_user_data(chat_id, {
            "suggested_brand": suggested_value,
            "original_input": text.strip()
        })
        set_state(chat_id, WhatsAppState.EVA_WAITING_BRAND)
        
        return generate_confirmation_message("brand", text, suggested_value, similarity)
    
    # === ОБРАБОТКА: НЕ НАЙДЕНО (<60%) ===
    else:  # text_not_found
        logger.warning(f"[BRAND_NOT_FOUND] '{text}' similarity <60%")
        return generate_not_found_message("brand", text)


async def process_brand(
    chat_id: str,
    brand_name: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает выбранную марку и показывает модели.

    Args:
        chat_id: ID чата WhatsApp
        brand_name: Название марки
        config: Конфигурация tenant

    Returns:
        str: Текст с моделями
    """
    i18n = config.i18n

    # Сохраняем марку
    update_user_data(chat_id, {"brand_name": brand_name})

    tenant = await get_tenant_by_slug(session, config.tenant_slug)

    if not tenant:
        return "Ошибка конфигурации. Попробуйте позже."

    models_list = await get_models_for_brand_from_db(brand_name, tenant.id, session)

    if not models_list:
        # Нет лекал для этой марки - предлагаем индивидуальный замер
        return (
            f"Похоже, готовых лекал для марки {brand_name} у нас пока нет. "
            f"Но это не проблема! 👍\n\n"
            f"Мы специализируемся на индивидуальных заказах и создадим коврики специально для вашего автомобиля!\n"
            f"✨ Преимущества:\n"
            f"• Идеальная посадка под ваш автомобиль\n"
            f"• Учет всех особенностей салона\n"
            f"• Выезд мастера для замеров\n\n"
            f"Что выберете?\n"
            f"1 - Заказать индивидуальный замер\n"
            f"2 - Вернуться в меню"
        )

    # Показываем первую страницу моделей
    return await show_models_page(chat_id, 1, models_list, brand_name, config)


async def show_models_page(chat_id: str, page: int, models_list: list, brand_name: str, config: Config) -> str:
    """
    Показывает страницу с моделями.

    Args:
        chat_id: ID чата WhatsApp
        page: Номер страницы
        models_list: Полный список моделей
        brand_name: Название марки
        config: Конфигурация tenant

    Returns:
        str: Текст с пагинированным списком моделей
    """
    i18n = config.i18n

    # Пагинация
    total_models = len(models_list)
    total_pages = (total_models + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE

    start_idx = (page - 1) * MODELS_PER_PAGE
    end_idx = start_idx + MODELS_PER_PAGE
    models_on_page = models_list[start_idx:end_idx]

    # Генерируем меню
    menu_text, callback_mapping = get_whatsapp_model_selection_text(
        models_on_page, page, total_pages, brand_name, i18n
    )

    # Сохраняем состояние
    set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)
    update_user_data(chat_id, {
        "models_page": page,
        "models_list": models_list,
        "models_callback_mapping": callback_mapping
    })

    return menu_text


async def handle_model_selection(
    chat_id: str,
    text: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает выбор модели используя УНИФИЦИРОВАННУЮ "умную" логику.

    Args:
        chat_id: ID чата WhatsApp
        text: Введенная цифра или текст
        config: Конфигурация tenant
        session: Сессия БД

    Returns:
        str: Текст ответа
    """
    i18n = config.i18n
    user_data = get_user_data(chat_id)
    callback_mapping = user_data.get("models_callback_mapping", {})
    models_list = user_data.get("models_list", [])
    brand_name = user_data.get("brand_name", "")
    category_name = user_data.get("category_name", "автоаксессуары")
    
    # === ОБРАБОТКА ПОДТВЕРЖДЕНИЯ (для схожести 60-70%) ===
    suggested_model = user_data.get("suggested_model")
    if suggested_model and text in ["1", "2"]:
        if text == "1":
            # Подтвердил
            update_user_data(chat_id, {"suggested_model": None, "original_input": None})
            return await process_model(chat_id, suggested_model, config, session)
        elif text == "2":
            # Отказался
            update_user_data(chat_id, {"suggested_model": None, "original_input": None})
            return "Введите название модели еще раз:"
    
    # === ПРОВЕРКА: ЦИФРОВОЙ ВВОД (до AI) ===
    # КРИТИЧЕСКИ ВАЖНО: проверяем цифры ДО вызова AI!
    if text.strip() in callback_mapping:
        logger.info(f"[MODEL_SELECT] Digit input: '{text}' -> processing directly without AI")
        callback_data = callback_mapping[text.strip()]
        
        # Пагинация
        if callback_data.startswith("models_page:"):
            page = int(callback_data.split(":")[1])
            return await show_models_page(chat_id, page, models_list, brand_name, config)
        
        # Выбор модели
        elif callback_data.startswith("model:"):
            model_name = callback_data.split(":", 1)[1]
            return await process_model(chat_id, model_name, config, session)
    
    # === УНИФИЦИРОВАННАЯ ОБРАБОТКА через handle_text_or_digit_input (ONLY for text) ===
    logger.info(f"[MODEL_SELECT] Text input detected: '{text}' -> using AI+Fuzzy")
    result = await handle_text_or_digit_input(
        user_input=text.strip(),
        context="model",
        chat_id=chat_id,
        callback_mapping=callback_mapping,
        database_list=models_list,
        category_name=category_name,
        brand_name=brand_name,
        session=session,
        config=config  # Передаем для заглушек
    )
    
    result_type = result.get("type")
    
    # === ОБРАБОТКА ТЕКСТОВОГО ВВОДА (>70%) ===
    if result_type == "text_auto":
        model_name = result.get("value")
        logger.info(f"[MODEL_AUTO] Auto-apply: '{model_name}' ({result.get('similarity'):.1f}%)")
        return await process_model(chat_id, model_name, config, session)
    
    # === ОБРАБОТКА ТЕКСТОВОГО ВВОДА (60-70%) ===
    elif result_type == "text_ask":
        suggested_value = result.get("value")
        similarity = result.get("similarity")
        
        logger.info(f"[MODEL_ASK] Need confirmation: '{suggested_value}' ({similarity:.1f}%)")
        
        update_user_data(chat_id, {
            "suggested_model": suggested_value,
            "original_input": text.strip()
        })
        set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)
        
        return generate_confirmation_message("model", text, suggested_value, similarity)
    
    # === ОБРАБОТКА: НЕ НАЙДЕНО (<60%) ===
    else:  # text_not_found
        logger.warning(f"[MODEL_NOT_FOUND] '{text}' similarity <60%")
        return generate_not_found_message("model", text)


async def process_model(
    chat_id: str,
    model_name: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обрабатывает выбранную модель и ищет лекала.

    Args:
        chat_id: ID чата WhatsApp
        model_name: Название модели
        config: Конфигурация tenant

    Returns:
        str: Текст с результатами поиска
    """
    i18n = config.i18n
    user_data = get_user_data(chat_id)
    brand_name = user_data.get("brand_name", "")
    category = user_data.get("category", "5d_mats")

    # Сохраняем модель
    update_user_data(chat_id, {"model_name": model_name})

    tenant = await get_tenant_by_slug(session, config.tenant_slug)

    if not tenant:
        return "Ошибка конфигурации. Попробуйте позже."

    patterns = await search_patterns(
        session=session,
        brand_name=brand_name,
        model_name=model_name,
        tenant_id=tenant.id,
        category_code=category
    )

    if not patterns:
        # Нет лекал - предлагаем индивидуальный замер и спрашиваем опции
        update_user_data(chat_id, {"is_individual_order": True})
        return await show_options_menu(chat_id, config, patterns_found=False)

    # Найдены лекала - предлагаем выбрать опции
    return await show_options_menu(chat_id, config, patterns_found=True)


async def show_options_menu(chat_id: str, config: Config, patterns_found: bool = True) -> str:
    """
    Показывает меню выбора опций.

    Args:
        chat_id: ID чата WhatsApp
        config: Конфигурация tenant
        patterns_found: True, если лекала найдены

    Returns:
        str: Текст с опциями
    """
    i18n = config.i18n
    user_data = get_user_data(chat_id)
    category = user_data.get("category", "")

    # Меню опций теперь включает "Вернуться в меню" для индивидуального заказа
    menu_text, callback_mapping = get_whatsapp_options_menu(i18n, category, individual_order=not patterns_found)

    set_state(chat_id, WhatsAppState.EVA_SELECTING_OPTIONS)
    update_user_data(chat_id, {"options_callback_mapping": callback_mapping})

    brand_name = user_data.get("brand_name", "")
    model_name = user_data.get("model_name", "")
    category_name = user_data.get("category_name", "")

    if patterns_found:
        intro = f"Отлично! Для {brand_name} {model_name} есть лекала.\n\n{category_name}"
    else:
        intro = (
            f"Похоже, готовых лекал для {brand_name} {model_name} у нас пока нет. "
            f"Но это не проблема! 👍\n\n"
            f"Мы можем изготовить их индивидуально. "
            f"Уточните, пожалуйста, вам нужны коврики с бортами или без?"
        )

    return format_whatsapp_message(intro, menu_text)


async def handle_options_selection(chat_id: str, text: str, config: Config) -> str:
    """
    Обрабатывает выбор опций.

    Args:
        chat_id: ID чата WhatsApp
        text: Введенная цифра
        config: Конфигурация tenant

    Returns:
        str: Текст подтверждения заказа
    """
    i18n = config.i18n
    user_data = get_user_data(chat_id)
    callback_mapping = user_data.get("options_callback_mapping", {})

    if text not in callback_mapping:
        return "Неверный выбор. Выберите цифру от 1 до 3."

    callback_data = callback_mapping[text]

    if callback_data == "action:back_to_menu":
        clear_state(chat_id)
        return await show_main_menu(chat_id, config)

    # Извлекаем выбранную опцию
    if callback_data.startswith("eva_option:"):
        parts = callback_data.split(":")
        option = parts[2] if len(parts) > 2 else "with_borders"

        option_names = {
            "with_borders": i18n.get("buttons.options.with_borders"),
            "without_borders": i18n.get("buttons.options.without_borders"),
            "consultation": i18n.get("buttons.options.need_consultation")
        }

        option_name = option_names.get(option, option)
        update_user_data(chat_id, {"selected_option": option, "selected_option_name": option_name})

        return await show_order_confirmation(chat_id, config)

    return "Неизвестная команда."


async def show_order_confirmation(chat_id: str, config: Config) -> str:
    """
    Показывает подтверждение заказа.

    Args:
        chat_id: ID чата WhatsApp
        config: Конфигурация tenant

    Returns:
        str: Текст подтверждения
    """
    i18n = config.i18n
    user_data = get_user_data(chat_id)

    brand_name = user_data.get("brand_name", "")
    model_name = user_data.get("model_name", "")
    category_name = user_data.get("category_name", "")
    option_name = user_data.get("selected_option_name", "")

    summary = (
        f"Проверьте ваш заказ:\n\n"
        f"Категория: {category_name}\n"
        f"Автомобиль: {brand_name} {model_name}\n"
        f"Опция: {option_name}\n"
    )

    menu_text, callback_mapping = get_whatsapp_confirmation_menu(i18n)

    set_state(chat_id, WhatsAppState.EVA_CONFIRMING_ORDER)
    update_user_data(chat_id, {"confirmation_callback_mapping": callback_mapping})

    return format_whatsapp_message(summary, menu_text)


async def handle_order_confirmation(chat_id: str, text: str, config: Config) -> str:
    """
    Обрабатывает подтверждение заказа.

    Args:
        chat_id: ID чата WhatsApp
        text: Введенная цифра
        config: Конфигурация tenant

    Returns:
        str: Текст с запросом контактов или возврат в меню
    """
    i18n = config.i18n
    user_data = get_user_data(chat_id)
    callback_mapping = user_data.get("confirmation_callback_mapping", {})
    
    # Специальная обработка для сценария "лекала не найдены"
    # Пользователь выбирает: 1 - индивидуальный замер, 2 - вернуться в меню
    if not callback_mapping and text in ["1", "2"]:
        if text == "1":
            # WhatsApp ВОРОНКА: Сразу отправляем заявку на индивидуальный замер
            update_user_data(chat_id, {"is_individual_order": True})
            return await send_whatsapp_order(chat_id, config)
        elif text == "2":
            # Возвращаемся в меню
            clear_state(chat_id)
            return await show_main_menu(chat_id, config)

    if text not in callback_mapping:
        return "Неверный выбор. Введите 1 для подтверждения или 2 для возврата в меню."

    callback_data = callback_mapping[text]

    if callback_data == "order:confirm":
        # WhatsApp ВОРОНКА: Сразу отправляем заявку без запроса контактов
        return await send_whatsapp_order(chat_id, config)

    elif callback_data == "action:back_to_menu":
        clear_state(chat_id)
        return await show_main_menu(chat_id, config)

    return "Неизвестная команда."


# УДАЛЕНО: Функции handle_name_input и handle_phone_input больше не используются
# WhatsApp автоматически извлекает данные из chat_id и senderName
# См. функцию send_whatsapp_order() ниже


async def send_whatsapp_order(chat_id: str, config: Config) -> str:
    """
    Отправляет заявку из WhatsApp, автоматически извлекая данные из chat_id и senderName.
    
    Args:
        chat_id: ID чата WhatsApp (формат: "996XXXXXXXXX@c.us")
        config: Конфигурация tenant
        
    Returns:
        str: Подтверждение отправки заявки
    """
    user_data = get_user_data(chat_id)
    
    # Автоматически извлекаем телефон из chat_id
    customer_phone = chat_id.split("@")[0] if "@" in chat_id else chat_id
    customer_phone = f"+{customer_phone}"
    
    # Используем sender_name из user_data (сохраненный при первом контакте)
    customer_name = user_data.get("sender_name", "Клиент WhatsApp")
    
    # Извлекаем данные заказа
    brand_name = user_data.get("brand_name", "")
    model_name = user_data.get("model_name", "")
    category_name = user_data.get("category_name", "")
    option_name = user_data.get("selected_option_name", "")
    is_individual_order = user_data.get("is_individual_order", False)

    # Формируем детали для лога и сообщения
    log_details = []
    msg_details = []

    if is_individual_order:
        log_details.append("  Type: Индивидуальный замер")
        msg_details.append("✨ Тип: Индивидуальный замер")

    if option_name:
        log_details.append(f"  Option: {option_name}")
        msg_details.append(f"⚙️ Опция: {option_name}")

    log_details_str = "\n".join(log_details)
    msg_details_str = "\n".join(msg_details) if msg_details else ""

    # Логируем заявку
    logger.info(
        f"[WHATSAPP_ORDER] New order from WhatsApp:\n"
        f"  Name: {customer_name}\n"
        f"  Phone: {customer_phone}\n"
        f"  Vehicle: {brand_name} {model_name}\n"
        f"  Category: {category_name}\n"
        f"{log_details_str}"
    )
    
    # TODO: Здесь будет интеграция с Airtable или отправка в Telegram
    
    # Очищаем состояние
    clear_state(chat_id)
    
    # Формируем подтверждение
    confirmation_message = (
        f"✅ Спасибо за заказ, {customer_name}!\n"
        f"Ваша заявка принята:\n\n"
        f"📦 Категория: {category_name}\n"
        f"🚗 Автомобиль: {brand_name} {model_name}\n"
    )

    if msg_details_str:
        confirmation_message += f"{msg_details_str}\n"

    confirmation_message += (
        f"📱 Телефон: {customer_phone}\n\n"
        f"📞 Наш менеджер свяжется с вами в ближайшее время!\n"
        f"Чтобы вернуться в главное меню, отправьте 'Меню'"
    )
    
    return confirmation_message


async def handle_contact_manager_request(chat_id: str, config: Config) -> str:
    """
    Обрабатывает запрос на связь с менеджером.

    Args:
        chat_id: ID чата WhatsApp
        config: Конфигурация tenant

    Returns:
        str: Контактная информация
    """
    i18n = config.i18n
    text = i18n.get("info_sections.contacts.text")

    clear_state(chat_id)

    return f"{text}\n\nОтправьте 'меню' для возврата в главное меню."


async def handle_contact_manager(chat_id: str, text: str, config: Config) -> str:
    """
    Обрабатывает сообщения в состоянии CONTACT_MANAGER.

    Args:
        chat_id: ID чата WhatsApp
        text: Текст сообщения
        config: Конфигурация tenant

    Returns:
        str: Ответ
    """
    if text.lower() in ["меню", "menu"]:
        return await show_main_menu(chat_id, config)

    return "Отправьте 'меню' для возврата в главное меню."


async def handle_ask_ai_whatsapp(chat_id: str, text: str, config: Config) -> str:
    """
    Секретная отладочная команда для прямого общения с AI Assistant через WhatsApp.
    
    Доступна только администраторам. Игнорирует FSM и всю бизнес-логику.
    
    Формат: ask_ai: <вопрос>
    Пример: ask_ai: Привет, как тебя зовут?
    
    Args:
        chat_id: ID чата WhatsApp (формат: "996XXXXXXXXX@c.us")
        text: Полный текст сообщения с командой
        config: Конфигурация бота
    
    Returns:
        str: Ответ от AI или сообщение об ошибке
    """
    # Извлекаем номер телефона из chat_id
    phone_number = chat_id.split("@")[0] if "@" in chat_id else chat_id
    
    # Проверка прав администратора
    admin_phones = [str(admin_id) for admin_id in []]
    
    if phone_number not in admin_phones:
        logger.warning(f"[AI_DEBUG_WA] Unauthorized access attempt from {chat_id}")
        return ""  # Молча игнорируем, чтобы не раскрывать существование команды
    
    # Извлекаем текст вопроса (всё после "ask_ai: ")
    question_parts = text.split(":", 1)
    
    if len(question_parts) < 2 or not question_parts[1].strip():
        return (
            "❓ Формат команды:\n"
            "ask_ai: ваш вопрос\n\n"
            "Пример:\n"
            "ask_ai: Привет, как тебя зовут?"
        )
    
    question_text = question_parts[1].strip()
    
    logger.info(f"[AI_DEBUG_WA] Admin {phone_number} asking: '{question_text[:50]}...'")
    
    try:
        # Создаем AssistantManager
        from core.ai.assistant import AssistantManager
        
        assistant = AssistantManager()
        
        # Получаем или создаем thread_id для админа
        thread_id = assistant.create_thread()
        
        logger.info(f"[AI_DEBUG_WA] Created thread: {thread_id}")
        
        # НАПРЯМУЮ вызываем AI Assistant (без FSM, без state_manager)
        response, _ = await assistant.get_response(
            thread_id=thread_id,
            user_message=question_text,
            chat_id=chat_id,
            timeout=30
        )
        
        logger.info(f"[AI_DEBUG_WA] AI response received: {len(response)} chars")
        
        # Отправляем ответ админу
        return f"🤖 AI Assistant Response:\n\n{response}"
        
    except Exception as e:
        # Отправляем ПОЛНЫЙ текст ошибки админу для диагностики
        error_message = (
            f"❌ AI Module Error:\n\n"
            f"{type(e).__name__}: {str(e)}\n\n"
            f"Details:\n{repr(e)}"
        )
        
        logger.error(f"[AI_DEBUG_WA] Error: {e}", exc_info=True)
        
        return error_message


async def ask_ai_for_brand(
    chat_id: str,
    user_text: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обращается к AI Assistant для распознавания марки из текста пользователя.
    
    Используется когда fuzzy matching не дал результатов.
    AI может распознать марку даже из сложных фраз типа "Ауди кватро" или "мерс е класс".
    
    Args:
        chat_id: ID чата WhatsApp
        user_text: Текст от пользователя (например, "Ауди", "мерседес е класс")
        config: Конфигурация бота
        session: Сессия БД
    
    Returns:
        str: Ответ для пользователя (либо продолжение сценария, либо запрос уточнения)
    """
    logger.info(f"[🤖 AI_BRAND] Asking AI to parse brand from: '{user_text}'")
    
    try:
        # Создаем AssistantManager
        assistant = AssistantManager()
        
        # Получаем или создаем thread
        thread_id = get_or_create_thread(chat_id, assistant)
        
        # Формируем prompt для AI
        user_data = get_user_data(chat_id)
        category_name = user_data.get("category_name", "автоаксессуары")
        
        ai_prompt = (
            f"Пользователь хочет заказать {category_name}. "
            f"Он написал: '{user_text}'. "
            f"Пожалуйста, определи марку автомобиля. "
            f"Верни ТОЛЬКО название марки по-русски, без пояснений."
        )
        
        # Получаем ответ от AI
        response, _ = await assistant.get_response(
            thread_id=thread_id,
            user_message=ai_prompt,
            chat_id=chat_id,
            timeout=20
        )
        
        logger.info(f"[🤖 AI_BRAND] AI response: '{response[:100]}'")
        
        # Пытаемся извлечь марку из ответа
        # AI должен вернуть что-то типа "Audi" или "Mercedes-Benz"
        parsed_brand = response.strip().split('\n')[0].strip()
        
        # Убираем лишние символы
        parsed_brand = parsed_brand.replace('"', '').replace("'", "").strip()
        
        # Проверяем, есть ли такая марка в базе (используем fuzzy с низким порогом)
        from rapidfuzz import fuzz, process
        brands_list = user_data.get("brands_list", [])
        
        if brands_list:
            best_match = process.extractOne(
                parsed_brand,
                brands_list,
                scorer=fuzz.ratio
            )
            
            if best_match and best_match[1] >= 60.0:  # Низкий порог для AI-распознанных марок
                brand_name = best_match[0]
                logger.info(f"[🤖 AI_BRAND] Matched to database brand: '{brand_name}' (similarity: {best_match[1]:.1f}%)")
                return await process_brand(chat_id, brand_name, config, session)
        
        # AI не смог распознать или марка не в базе
        logger.warning(f"[🤖 AI_BRAND] Could not match AI response to database brands")
        return (
            f"Не удалось определить марку из вашего сообщения: '{user_text}'.\n\n"
            f"Попробуйте:"
            f"\n• Выбрать из списка (введите цифру 1-8)"
            f"\n• Написать только название марки (например: 'Toyota', 'BMW')"
            f"\n• Связаться с менеджером"
        )
        
    except Exception as e:
        logger.error(f"[🤖 AI_BRAND] Error: {e}", exc_info=True)
        # Fallback на обычное сообщение об ошибке
        return (
            f"Не удалось распознать марку.\n\n"
            f"Попробуйте:"
            f"\n• Выбрать из списка (введите цифру 1-8)"
            f"\n• Написать название точнее"
        )


async def ask_ai_for_model(
    chat_id: str,
    user_text: str,
    brand_name: str,
    config: Config,
    session: AsyncSession
) -> str:
    """
    Обращается к AI Assistant для распознавания модели из текста пользователя.
    
    Используется когда fuzzy matching не дал результатов.
    AI может распознать модель даже из сложных фраз типа "камри тридцать" или "х пятый".
    
    Args:
        chat_id: ID чата WhatsApp
        user_text: Текст от пользователя (например, "камри", "х5")
        brand_name: Уже выбранная марка
        config: Конфигурация бота
        session: Сессия БД
    
    Returns:
        str: Ответ для пользователя
    """
    logger.info(f"[🤖 AI_MODEL] Asking AI to parse model from: '{user_text}' for brand: '{brand_name}'")
    
    try:
        # Создаем AssistantManager
        assistant = AssistantManager()
        
        # Получаем или создаем thread
        thread_id = get_or_create_thread(chat_id, assistant)
        
        # Формируем prompt для AI
        user_data = get_user_data(chat_id)
        category_name = user_data.get("category_name", "автоаксессуары")
        
        ai_prompt = (
            f"Пользователь хочет заказать {category_name} для автомобиля {brand_name}. "
            f"Он написал: '{user_text}'. "
            f"Пожалуйста, определи модель автомобиля. "
            f"Верни ТОЛЬКО название модели, без пояснений."
        )
        
        # Получаем ответ от AI
        response, _ = await assistant.get_response(
            thread_id=thread_id,
            user_message=ai_prompt,
            chat_id=chat_id,
            timeout=20
        )
        
        logger.info(f"[🤖 AI_MODEL] AI response: '{response[:100]}'")
        
        # Пытаемся извлечь модель из ответа
        parsed_model = response.strip().split('\n')[0].strip()
        
        # Убираем лишние символы
        parsed_model = parsed_model.replace('"', '').replace("'", "").strip()
        
        # Проверяем, есть ли такая модель в базе (используем fuzzy с низким порогом)
        from rapidfuzz import fuzz, process
        models_list = user_data.get("models_list", [])
        
        if models_list:
            best_match = process.extractOne(
                parsed_model,
                models_list,
                scorer=fuzz.ratio
            )
            
            if best_match and best_match[1] >= 60.0:  # Низкий порог для AI-распознанных моделей
                model_name = best_match[0]
                logger.info(f"[🤖 AI_MODEL] Matched to database model: '{model_name}' (similarity: {best_match[1]:.1f}%)")
                return await process_model(chat_id, model_name, config, session)
        
        # AI не смог распознать или модель не в базе
        logger.warning(f"[🤖 AI_MODEL] Could not match AI response to database models")
        return (
            f"Не удалось определить модель из вашего сообщения: '{user_text}'.\n\n"
            f"Попробуйте:"
            f"\n• Выбрать из списка (введите цифру 1-8)"
            f"\n• Написать только название модели"
            f"\n• Заказать индивидуальный замер"
        )
        
    except Exception as e:
        logger.error(f"[🤖 AI_MODEL] Error: {e}", exc_info=True)
        # Fallback на обычное сообщение об ошибке
        return (
            f"Не удалось распознать модель.\n\n"
            f"Попробуйте:"
            f"\n• Выбрать из списка (введите цифру 1-8)"
            f"\n• Написать название точнее"
        )
