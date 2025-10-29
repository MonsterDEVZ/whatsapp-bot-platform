"""
Inline-клавиатуры для бота.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..constants import (
    CALLBACK_INPUT_MODEL,
    CALLBACK_USE_SUGGESTION
)
from ..config import I18nInstance


def get_language_keyboard(i18n: I18nInstance) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру выбора языка.

    Args:
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками выбора языка
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.language.russian"),
            callback_data="lang:ru"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.language.kyrgyz"),
            callback_data="lang:ky"
        )
    )

    return builder.as_markup()


def get_main_menu_keyboard(i18n: I18nInstance) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру главного меню.

    КРИТИЧЕСКИ ВАЖНО: Меню генерируется ИСКЛЮЧИТЕЛЬНО из buttons.catalog_categories!
    Никаких захардкоженных категорий! Каждый tenant имеет свой уникальный набор.

    Args:
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню

    Raises:
        ValueError: Если catalog_categories не найден в локализации (критическая ошибка конфигурации)
    """
    import logging
    logger = logging.getLogger(__name__)

    builder = InlineKeyboardBuilder()

    # Получаем catalog_categories из локализации
    catalog_categories = i18n.get("buttons.catalog_categories")

    logger.info(f"🔍 [INLINE_KEYBOARD] Генерация главного меню Telegram")
    logger.info(f"🔍 [INLINE_KEYBOARD] catalog_categories type: {type(catalog_categories)}")
    logger.info(f"🔍 [INLINE_KEYBOARD] catalog_categories: {catalog_categories}")

    if not catalog_categories or not isinstance(catalog_categories, list):
        # КРИТИЧЕСКАЯ ОШИБКА: catalog_categories не найден!
        logger.error(f"❌ [INLINE_KEYBOARD] catalog_categories НЕ НАЙДЕН или неверного типа!")
        logger.error(f"❌ [INLINE_KEYBOARD] ВСЕ tenant'ы ОБЯЗАНЫ иметь buttons.catalog_categories!")

        # Возвращаем кнопку с сообщением об ошибке
        builder.row(
            InlineKeyboardButton(
                text="⚠️ Ошибка конфигурации",
                callback_data="action:contact_manager"
            )
        )
        return builder.as_markup()

    if len(catalog_categories) == 0:
        logger.error(f"❌ [INLINE_KEYBOARD] catalog_categories ПУСТОЙ!")
        builder.row(
            InlineKeyboardButton(
                text="⚠️ Каталог недоступен",
                callback_data="action:contact_manager"
            )
        )
        return builder.as_markup()

    # Генерируем кнопки из catalog_categories
    logger.info(f"✅ [INLINE_KEYBOARD] Генерирую {len(catalog_categories)} категорий")

    for idx, category in enumerate(catalog_categories, start=1):
        text = category.get("text", "")
        callback_data = category.get("callback_data", "")

        logger.info(f"  [{idx}] text='{text}', callback='{callback_data}'")

        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=callback_data
            )
        )

    logger.info(f"✅ [INLINE_KEYBOARD] Меню успешно сгенерировано ({len(catalog_categories)} кнопок)")

    return builder.as_markup()


def get_back_to_menu_keyboard(i18n: I18nInstance) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой "Вернуться в меню".

    Args:
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой возврата
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.back_to_menu"),
            callback_data="action:back_to_menu"
        )
    )

    return builder.as_markup()


def get_category_keyboard(category: str, i18n: I18nInstance) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для страницы категории с кнопкой заявки.

    Args:
        category: Код категории товара
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками
    """
    builder = InlineKeyboardBuilder()

    # Кнопка "Оставить заявку"
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.leave_request"),
            callback_data=f"request:{category}"
        )
    )

    # Кнопка "Вернуться в меню"
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.back_to_menu"),
            callback_data="action:back_to_menu"
        )
    )

    return builder.as_markup()


def get_popular_brands_keyboard(i18n: I18nInstance) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с популярными марками автомобилей.
    Марки отображаются по две в ряд для компактности.

    Args:
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        InlineKeyboardMarkup: Клавиатура с популярными марками
    """
    from core.constants import POPULAR_BRANDS, CALLBACK_BRAND_PREFIX, CALLBACK_INPUT_BRAND

    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для популярных марок
    for brand in POPULAR_BRANDS:
        builder.button(
            text=f"{i18n.get('buttons.brands.brand_prefix')}{brand}",
            callback_data=f"{CALLBACK_BRAND_PREFIX}{brand}"
        )

    # Располагаем кнопки по две в ряд
    builder.adjust(2)

    # Кнопка "Ввести другую марку" (на всю ширину)
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.brands.input_other"),
            callback_data=CALLBACK_INPUT_BRAND
        )
    )

    return builder.as_markup()


def get_popular_models_keyboard(brand: str, i18n: I18nInstance) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с популярными моделями для выбранной марки.
    Модели отображаются по две в ряд для компактности.

    Args:
        brand: Название марки
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        InlineKeyboardMarkup: Клавиатура с популярными моделями
    """
    from core.constants import POPULAR_MODELS, CALLBACK_MODEL_PREFIX, CALLBACK_INPUT_MODEL

    builder = InlineKeyboardBuilder()

    # Получаем популярные модели для выбранной марки
    models = POPULAR_MODELS.get(brand, [])

    # Добавляем кнопки для популярных моделей
    for model in models:
        builder.button(
            text=f"{i18n.get('buttons.models.model_prefix')}{model}",
            callback_data=f"{CALLBACK_MODEL_PREFIX}{model}"
        )

    # Располагаем кнопки по две в ряд
    builder.adjust(2)

    # Кнопка "Ввести другую модель" (на всю ширину)
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.models.input_other"),
            callback_data=CALLBACK_INPUT_MODEL
        )
    )

    return builder.as_markup()


def get_suggestion_keyboard(suggested_model: str, i18n: I18nInstance) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с предложением использовать найденную модель.

    Args:
        suggested_model: Предложенное название модели
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой подтверждения
    """
    from core.constants import CALLBACK_USE_SUGGESTION

    builder = InlineKeyboardBuilder()

    # Кнопка "Да, использовать [модель]"
    builder.row(
        InlineKeyboardButton(
            text=f"{i18n.get('buttons.suggestion.yes')} '{suggested_model}'",
            callback_data=f"{CALLBACK_USE_SUGGESTION}{suggested_model}"
        )
    )

    # Кнопка "Нет, ввести заново"
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.suggestion.no"),
            callback_data=CALLBACK_INPUT_MODEL
        )
    )

    return builder.as_markup()


def get_brands_keyboard_paginated(
    brands_list: list[str],
    page: int = 1,
    page_size: int = 8,
    i18n: I18nInstance = None
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с пагинацией для выбора марки автомобиля.

    Отображает 8 марок на страницу (4 ряда по 2 кнопки) с кнопками навигации внизу.

    Args:
        brands_list: Полный список всех марок
        page: Номер текущей страницы (начинается с 1)
        page_size: Количество марок на странице (по умолчанию 8)
        i18n: Экземпляр I18nInstance для локализации (опционально)

    Returns:
        InlineKeyboardMarkup: Клавиатура с марками и кнопками навигации
    """
    builder = InlineKeyboardBuilder()

    # Вычисляем индексы для текущей страницы
    total_brands = len(brands_list)
    total_pages = (total_brands + page_size - 1) // page_size  # Округление вверх

    # Корректируем номер страницы, если он выходит за границы
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    # Вычисляем начальный и конечный индексы для текущей страницы
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_brands)

    # Получаем марки для текущей страницы
    current_page_brands = brands_list[start_idx:end_idx]

    # Добавляем кнопки с марками (по 2 в ряд)
    for brand in current_page_brands:
        builder.button(
            text=brand,
            callback_data=f"brand_select:{brand}"
        )

    # Располагаем кнопки по 2 в ряд
    builder.adjust(2)

    # === КНОПКИ НАВИГАЦИИ ===
    navigation_row = []

    # Кнопка "⬅️ Назад" (только если не первая страница)
    if page > 1:
        navigation_row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"brands_page:{page - 1}"
            )
        )

    # Кнопка с информацией о текущей странице (некликабельная)
    navigation_row.append(
        InlineKeyboardButton(
            text=f"📄 {page}/{total_pages}",
            callback_data=f"page_info:{page}"  # Будем игнорировать этот callback
        )
    )

    # Кнопка "Следующий ➡️" (только если не последняя страница)
    if page < total_pages:
        navigation_row.append(
            InlineKeyboardButton(
                text="Далее ➡️",
                callback_data=f"brands_page:{page + 1}"
            )
        )

    # Добавляем ряд навигации
    builder.row(*navigation_row)

    # Кнопка "Вернуться в меню" (опционально, если передан i18n)
    if i18n:
        builder.row(
            InlineKeyboardButton(
                text=i18n.get("buttons.actions.back_to_menu"),
                callback_data="action:back_to_menu"
            )
        )

    return builder.as_markup()
