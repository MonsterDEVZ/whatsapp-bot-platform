"""
Reply-клавиатуры для Telegram-бота.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from ..config import I18nInstance


def get_navigation_panel_keyboard(i18n: I18nInstance) -> ReplyKeyboardMarkup:
    """
    Создает постоянную навигационную панель бота.

    Панель содержит основные разделы:
    - Каталог товаров
    - Индивидуальный замер
    - Наши работы/Отзывы
    - О нас/Контакты
    - FAQ/Помощь

    Args:
        i18n: Экземпляр системы локализации

    Returns:
        ReplyKeyboardMarkup: Навигационная панель
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            # Ряд 1: Главная кнопка - Каталог
            [KeyboardButton(text=i18n.get("buttons.navigation.catalog"))],
            # Ряд 2: Услуги и социальное доказательство
            [
                KeyboardButton(text=i18n.get("buttons.navigation.individual_measure")),
                KeyboardButton(text=i18n.get("buttons.navigation.our_works"))
            ],
            # Ряд 3: Информация и поддержка
            [
                KeyboardButton(text=i18n.get("buttons.navigation.about_us")),
                KeyboardButton(text=i18n.get("buttons.navigation.help"))
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=i18n.get("placeholders.select_section")
    )
    return keyboard


def get_main_menu_button_keyboard(i18n: I18nInstance) -> ReplyKeyboardMarkup:
    """
    DEPRECATED: Используйте get_navigation_panel_keyboard()

    Оставлено для обратной совместимости.

    Args:
        i18n: Экземпляр системы локализации
    """
    return get_navigation_panel_keyboard(i18n)


def get_cancel_keyboard(i18n: I18nInstance) -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру с кнопками отмены и возврата в меню.

    Args:
        i18n: Экземпляр системы локализации

    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопками отмены
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=i18n.get("buttons.actions.cancel"))],
            [KeyboardButton(text=i18n.get("buttons.actions.main_menu"))]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=i18n.get("placeholders.enter_data_or_cancel")
    )
    return keyboard


def get_phone_request_keyboard(i18n: I18nInstance) -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой для отправки номера телефона.

    Args:
        i18n: Экземпляр системы локализации

    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопкой отправки контакта
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=i18n.get("buttons.actions.send_phone"), request_contact=True)],
            [KeyboardButton(text=i18n.get("buttons.actions.cancel"))],
            [KeyboardButton(text=i18n.get("buttons.actions.main_menu"))]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=i18n.get("placeholders.click_button_below")
    )
    return keyboard
