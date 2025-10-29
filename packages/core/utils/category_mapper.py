"""
Утилита для маппинга категорий товаров.

Преобразует коды категорий из AI ответа в правильные ключи локализации.
"""

import logging

logger = logging.getLogger(__name__)


# Маппинг кодов категорий на ключи локализации
# Формат: {category_code: i18n_key}
CATEGORY_I18N_MAP = {
    # EVOPOLIKI категории
    "eva_mats": "buttons.categories.eva_mats",
    "seat_covers": "buttons.categories.seat_covers",
    "5d_mats": "buttons.categories.5d_mats",
    "dashboard_covers": "buttons.categories.dashboard_covers",

    # 5DELUXE категории
    "premium_covers": "catalog_categories.premium_covers",
    "alcantara_covers": "catalog_categories.alcantara_dash",  # AI возвращает alcantara_covers, локализация ожидает alcantara_dash
    "alcantara_dash": "catalog_categories.alcantara_dash",
}

# Маппинг кодов категорий на человекочитаемые названия (fallback)
CATEGORY_NAMES_FALLBACK = {
    "eva_mats": "EVA-коврики",
    "seat_covers": "Автомобильные чехлы",
    "5d_mats": "5D-коврики Deluxe",
    "dashboard_covers": "Накидки на панель",
    "premium_covers": "Премиум-чехлы",
    "alcantara_covers": "Накидки из алькантары",
    "alcantara_dash": "Накидки из алькантары",
}


def get_category_name(category_code: str, i18n) -> str:
    """
    Получает название категории из i18n по коду категории.

    Args:
        category_code: Код категории (например, "5d_mats", "premium_covers")
        i18n: Объект локализации

    Returns:
        Название категории на текущем языке

    Example:
        >>> get_category_name("5d_mats", i18n)
        "💎 5D-коврики Deluxe"

        >>> get_category_name("premium_covers", i18n)
        "👑 Премиум-чехлы"
    """
    # Логируем входящий код категории
    logger.info(f"🔍 [CATEGORY_MAPPER] Маппинг категории: {category_code}")

    # Пробуем найти в маппинге
    i18n_key = CATEGORY_I18N_MAP.get(category_code)

    if i18n_key:
        logger.info(f"📝 [CATEGORY_MAPPER] Найден ключ локализации: {i18n_key}")

        # Для 5DELUXE используем catalog_categories (это массив)
        if i18n_key.startswith("catalog_categories."):
            # Извлекаем category_code из ключа
            target_category = i18n_key.split(".", 1)[1]

            # Получаем catalog_categories из i18n
            catalog = i18n.get("buttons.catalog_categories") or []

            if isinstance(catalog, list):
                # Ищем элемент с нужным callback_data
                for item in catalog:
                    if item.get("callback_data") == f"category:{target_category}":
                        category_name = item.get("text", "")
                        logger.info(f"✅ [CATEGORY_MAPPER] Найдено название: {category_name}")
                        return category_name

        # Для EVOPOLIKI используем buttons.categories
        else:
            category_name = i18n.get(i18n_key) or ""
            if category_name:
                logger.info(f"✅ [CATEGORY_MAPPER] Найдено название: {category_name}")
                return category_name

    # Fallback: используем статичный маппинг
    fallback_name = CATEGORY_NAMES_FALLBACK.get(category_code, "Не указано")
    logger.warning(f"⚠️  [CATEGORY_MAPPER] Использован fallback для {category_code}: {fallback_name}")
    return fallback_name
