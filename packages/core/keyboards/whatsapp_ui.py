"""
WhatsApp UI генератор - создание текстовых меню для WhatsApp.

Этот модуль преобразует Telegram Inline-клавиатуры в пронумерованные
текстовые меню для WhatsApp, сохраняя ту же структуру и callback_data.
"""

from typing import Dict, List, Tuple
from ..config import I18nInstance


def digit_to_emoji(digit: str) -> str:
    """
    Преобразует цифру в эмодзи.
    
    Args:
        digit: Цифра в виде строки ("1", "2", "00", "99" и т.д.)
        
    Returns:
        str: Эмодзи цифра (1️⃣, 2️⃣, и т.д.)
    """
    emoji_map = {
        "0": "0️⃣",
        "1": "1️⃣",
        "2": "2️⃣",
        "3": "3️⃣",
        "4": "4️⃣",
        "5": "5️⃣",
        "6": "6️⃣",
        "7": "7️⃣",
        "8": "8️⃣",
        "9": "9️⃣",
        "00": "⏪",  # Стрелка назад
        "99": "⏩",  # Стрелка вперед
    }
    return emoji_map.get(digit, digit)


def get_whatsapp_main_menu(i18n: I18nInstance) -> Tuple[str, Dict[str, str]]:
    """
    Генерирует текстовое главное меню для WhatsApp.

    КРИТИЧЕСКИ ВАЖНО: Меню генерируется ИСКЛЮЧИТЕЛЬНО из buttons.catalog_categories!
    Никаких жестко заданных категорий! Каждый tenant имеет свой уникальный набор.

    Args:
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        Tuple[str, Dict[str, str]]: (текст_меню, маппинг цифра->callback_data)

    Example:
        text, mapping = get_whatsapp_main_menu(i18n)
        # text: "1 - 💎 5D-коврики Deluxe\n2 - 👑 Премиум-чехлы\n..."
        # mapping: {"1": "category:5d_mats", "2": "category:premium_covers", ...}
    """
    import logging
    logger = logging.getLogger(__name__)

    # Получаем catalog_categories из локализации
    catalog_categories = i18n.get("buttons.catalog_categories")

    logger.info(f"🔍 [MENU_GEN] Генерация главного меню")
    logger.info(f"🔍 [MENU_GEN] catalog_categories type: {type(catalog_categories)}")
    logger.info(f"🔍 [MENU_GEN] catalog_categories: {catalog_categories}")

    if not catalog_categories or not isinstance(catalog_categories, list):
        # КРИТИЧЕСКАЯ ОШИБКА: catalog_categories не найден!
        logger.error(f"❌ [MENU_GEN] catalog_categories НЕ НАЙДЕН или неверного типа!")
        logger.error(f"❌ [MENU_GEN] Вызываю fallback с сообщением об ошибке")
        return get_whatsapp_main_menu_fallback(i18n)

    if len(catalog_categories) == 0:
        logger.error(f"❌ [MENU_GEN] catalog_categories ПУСТОЙ!")
        return get_whatsapp_main_menu_fallback(i18n)

    # Генерируем меню
    menu_items = []
    callback_mapping = {}

    intro_text = i18n.get("menu.catalog")
    menu_items.append(intro_text)

    logger.info(f"✅ [MENU_GEN] Генерирую {len(catalog_categories)} категорий")

    for idx, category in enumerate(catalog_categories, start=1):
        text = category.get("text", "")
        callback_data = category.get("callback_data", "")

        logger.info(f"  [{idx}] text='{text}', callback='{callback_data}'")

        menu_items.append(f"{digit_to_emoji(str(idx))} {text}")
        callback_mapping[str(idx)] = callback_data

    menu_text = "\n".join(menu_items)

    logger.info(f"✅ [MENU_GEN] Меню успешно сгенерировано ({len(callback_mapping)} кнопок)")

    return menu_text, callback_mapping


def get_whatsapp_main_menu_fallback(i18n: I18nInstance) -> Tuple[str, Dict[str, str]]:
    """
    КРИТИЧЕСКИ ВАЖНО: Эта функция НЕ ДОЛЖНА использоваться!
    Все tenant'ы ОБЯЗАНЫ иметь buttons.catalog_categories в локализации!

    Args:
        i18n: Экземпляр I18nInstance

    Returns:
        Tuple[str, Dict[str, str]]: (текст_меню, маппинг цифра->callback_data)

    Raises:
        RuntimeError: Если catalog_categories не найден (это критическая ошибка конфигурации)
    """
    # ❌ УДАЛЁН ЖЕСТКО ЗАДАННЫЙ FALLBACK С КАТЕГОРИЯМИ EVOPOLIKI!
    # Теперь возвращаем ОШИБКУ, если catalog_categories не найден

    error_text = (
        "⚠️ ОШИБКА КОНФИГУРАЦИИ\n\n"
        "Каталог товаров временно недоступен.\n"
        "Пожалуйста, свяжитесь с менеджером:\n\n"
        f"📞 {i18n.get('buttons.actions.contact_manager')}"
    )

    callback_mapping = {
        "1": "action:contact_manager"
    }

    return error_text, callback_mapping


def get_whatsapp_options_menu(i18n: I18nInstance, category: str, individual_order: bool = False) -> Tuple[str, Dict[str, str]]:
    """
    Генерирует меню выбора опций для EVA/5D-ковриков.

    Args:
        i18n: Экземпляр I18nInstance для локализации
        category: Код категории (eva_mats, 5d_mats, и т.д.)
        individual_order: Если True, заменяет консультацию на возврат в меню.

    Returns:
        Tuple[str, Dict[str, str]]: (текст_меню, маппинг цифра->callback_data)
    """
    menu_items = [
        "Выберите вариант:",
        f"{digit_to_emoji('1')} {i18n.get('buttons.options.with_borders')}",
        f"{digit_to_emoji('2')} {i18n.get('buttons.options.without_borders')}",
    ]

    callback_mapping = {
        "1": f"eva_option:{category}:with_borders",
        "2": f"eva_option:{category}:without_borders",
    }

    # В сценарии индивидуального заказа "Консультация" заменяется на "Вернуться в меню"
    if individual_order:
        menu_items.append(f"{digit_to_emoji('3')} {i18n.get('buttons.actions.back_to_menu')}")
        callback_mapping["3"] = "action:back_to_menu"
    else:
        menu_items.append(f"{digit_to_emoji('3')} {i18n.get('buttons.options.need_consultation')}")
        callback_mapping["3"] = f"eva_option:{category}:consultation"

    return "\n".join(menu_items), callback_mapping


def get_whatsapp_confirmation_menu(i18n: I18nInstance) -> Tuple[str, Dict[str, str]]:
    """
    Генерирует меню подтверждения заказа.

    Args:
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        Tuple[str, Dict[str, str]]: (текст_меню, маппинг цифра->callback_data)
    """
    menu_items = [
        f"{digit_to_emoji('1')} {i18n.get('buttons.actions.confirm_order')}",
        f"{digit_to_emoji('2')} {i18n.get('buttons.actions.back_to_menu')}"
    ]

    callback_mapping = {
        "1": "order:confirm",
        "2": "action:back_to_menu"
    }

    return "\n".join(menu_items), callback_mapping


def get_whatsapp_brand_selection_text(brands: List[str], page: int, total_pages: int, i18n: I18nInstance) -> Tuple[str, Dict[str, str]]:
    """
    Генерирует текстовое меню для выбора марки автомобиля с пагинацией.

    Args:
        brands: Список марок на текущей странице
        page: Номер текущей страницы (начиная с 1)
        total_pages: Общее количество страниц
        i18n: Экземпляр I18nInstance

    Returns:
        Tuple[str, Dict[str, str]]: (текст_меню, маппинг цифра->callback_data)
    """
    menu_items = [
        f"Выберите марку (страница {page}/{total_pages}):"
    ]

    callback_mapping = {}

    # Добавляем марки
    for idx, brand in enumerate(brands, start=1):
        menu_items.append(f"{digit_to_emoji(str(idx))} {brand}")
        callback_mapping[str(idx)] = f"brand:{brand}"

    # Улучшенная навигация
    if total_pages > 1:
        nav_parts = []
        if page > 1:
            nav_parts.append(f"0️⃣0️⃣ - предыдущая страница")
            callback_mapping["00"] = f"brands_page:{page-1}"
        if page < total_pages:
            nav_parts.append(f"9️⃣9️⃣ - следующая страница")
            callback_mapping["99"] = f"brands_page:{page+1}"
        
        if nav_parts:
            menu_items.append("\n" + "\n".join(nav_parts))
    
    # Умный ввод: можно написать название марки текстом
    menu_items.append("\n💡 Или напишите название марки")

    return "\n".join(menu_items), callback_mapping


def get_whatsapp_model_selection_text(models: List[str], page: int, total_pages: int, brand_name: str, i18n: I18nInstance) -> Tuple[str, Dict[str, str]]:
    """
    Генерирует текстовое меню для выбора модели автомобиля с пагинацией.

    Args:
        models: Список моделей на текущей странице
        page: Номер текущей страницы (начиная с 1)
        total_pages: Общее количество страниц
        brand_name: Название марки
        i18n: Экземпляр I18nInstance

    Returns:
        Tuple[str, Dict[str, str]]: (текст_меню, маппинг цифра->callback_data)
    """
    menu_items = [
        f"Марка: {brand_name}\n",
        f"Выберите модель (страница {page}/{total_pages}):"
    ]

    callback_mapping = {}

    # Добавляем модели
    for idx, model in enumerate(models, start=1):
        menu_items.append(f"{digit_to_emoji(str(idx))} {model}")
        callback_mapping[str(idx)] = f"model:{model}"

    # Улучшенная навигация
    if total_pages > 1:
        nav_parts = []
        if page > 1:
            nav_parts.append(f"0️⃣0️⃣ - предыдущая страница")
            callback_mapping["00"] = f"models_page:{page-1}"
        if page < total_pages:
            nav_parts.append(f"9️⃣9️⃣ - следующая страница")
            callback_mapping["99"] = f"models_page:{page+1}"
        
        if nav_parts:
            menu_items.append("\n" + "\n".join(nav_parts))
    
    # Умный ввод: можно написать название модели текстом
    menu_items.append("\n💡 Или напишите название модели")

    return "\n".join(menu_items), callback_mapping


def get_whatsapp_fuzzy_suggestion_text(original_input: str, suggested: str, i18n: I18nInstance) -> Tuple[str, Dict[str, str]]:
    """
    Генерирует текст подсказки для нечеткого поиска.

    Args:
        original_input: Оригинальный ввод пользователя
        suggested: Предложенный вариант из БД
        i18n: Экземпляр I18nInstance

    Returns:
        Tuple[str, Dict[str, str]]: (текст_сообщения, маппинг цифра->callback_data)
    """
    text = f"Вы ввели: '{original_input}'\nВозможно, вы имели в виду: '{suggested}'?\n\n{digit_to_emoji('1')} {i18n.get('buttons.suggestion.yes')}\n{digit_to_emoji('2')} {i18n.get('buttons.suggestion.no')}"

    callback_mapping = {
        "1": f"use_suggestion:{suggested}",
        "2": "reject_suggestion"
    }

    return text, callback_mapping


def get_whatsapp_back_to_menu_text(i18n: I18nInstance) -> Tuple[str, Dict[str, str]]:
    """
    Генерирует меню с кнопкой "Вернуться в меню".

    Args:
        i18n: Экземпляр I18nInstance

    Returns:
        Tuple[str, Dict[str, str]]: (текст_меню, маппинг цифра->callback_data)
    """
    text = f"\n{digit_to_emoji('0')} {i18n.get('buttons.actions.back_to_menu')}"

    callback_mapping = {
        "0": "action:back_to_menu"
    }

    return text, callback_mapping


def format_whatsapp_message(text: str, menu_text: str = None) -> str:
    """
    Форматирует итоговое сообщение для WhatsApp, объединяя текст и меню.

    Args:
        text: Основной текст сообщения
        menu_text: Текст меню (опционально)

    Returns:
        str: Отформатированное сообщение
    """
    if menu_text:
        return f"{text}\n\n{menu_text}"
    return text
