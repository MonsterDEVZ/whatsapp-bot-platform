"""
Клавиатуры для Telegram-бота.
"""

from .inline import (
    get_language_keyboard,
    get_main_menu_keyboard,
    get_back_to_menu_keyboard,
    get_category_keyboard,
    get_popular_brands_keyboard,
    get_popular_models_keyboard,
    get_suggestion_keyboard,
    get_brands_keyboard_paginated
)

from .reply import (
    get_main_menu_button_keyboard,
    get_navigation_panel_keyboard,
    get_cancel_keyboard,
    get_phone_request_keyboard
)

__all__ = [
    # Inline keyboards
    "get_language_keyboard",
    "get_main_menu_keyboard",
    "get_back_to_menu_keyboard",
    "get_category_keyboard",
    "get_popular_brands_keyboard",
    "get_popular_models_keyboard",
    "get_suggestion_keyboard",
    "get_brands_keyboard_paginated",
    # Reply keyboards
    "get_main_menu_button_keyboard",
    "get_navigation_panel_keyboard",
    "get_cancel_keyboard",
    "get_phone_request_keyboard",
]
