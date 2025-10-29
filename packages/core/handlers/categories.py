"""
Обработчики для категорий товаров (заглушки).
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from core.keyboards import get_back_to_menu_keyboard, get_category_keyboard
from core.config import Config

router = Router()


@router.callback_query(F.data.startswith("category:"))
async def category_selected(callback: CallbackQuery, config: Config):
    """
    Обработчик выбора категории товара (для категорий кроме EVA-ковриков).

    Пока это заглушка, которая сообщает что раздел в разработке.
    """
    # Извлекаем категорию из callback_data
    category = callback.data.split(":")[1]

    # Пропускаем категории с dedicated handlers (обрабатываются в отдельных handlers)
    # Эти категории имеют полноценные FSM-сценарии в отдельных файлах
    if category in [
        "eva_mats",           # EVA-коврики (eva_mats.py)
        "seat_covers",        # Автомобильные чехлы (seat_covers.py)
        "premium_covers",     # Премиум-чехлы для 5deluxe (seat_covers.py)
        "5d_mats",            # 5D-коврики для evopoliki (mats_5d.py)
        "5d_mats_deluxe",     # 5D-коврики для 5deluxe (mats_5d.py)
        "mats_5d",            # Legacy название (mats_5d.py)
        "dash_mats",          # Legacy название (dash_mats.py)
        "dashboard_covers",   # Накидки на панель для evopoliki (dash_mats.py)
        "alcantara_dash"      # Накидки для 5deluxe (dash_mats.py)
    ]:
        return

    i18n = config.bot.i18n

    # Названия категорий для отображения (для неподдерживаемых категорий)
    category_names = {
        # Если вдруг какая-то категория не реализована, показываем заглушку
    }

    category_name = category_names.get(category, "выбранная категория")

    # Сообщение о том, что раздел в разработке
    text = i18n.get("categories.in_development").replace("{category_name}", category_name)

    await callback.message.edit_text(
        text=text,
        reply_markup=get_category_keyboard(category, i18n),
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(F.data == "action:contact_manager")
async def contact_manager(callback: CallbackQuery, config: Config):
    """
    Обработчик кнопки "Связаться с менеджером".
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    i18n = config.bot.i18n
    text = i18n.get("contact_manager.text")

    # Создаем клавиатуру с кнопкой заявки
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.leave_request"),
            callback_data="request:contact"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.back_to_menu"),
            callback_data="action:back_to_menu"
        )
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

    await callback.answer(i18n.get("contact_manager.callback"))
