"""
Обработчики для главного меню и выбора языка.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from core.keyboards import get_navigation_panel_keyboard, get_main_menu_keyboard
from core.config import Config

router = Router()


@router.callback_query(F.data.startswith("lang:"))
async def language_selected(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обработчик выбора языка.

    После выбора языка показывает навигационную панель и каталог товаров.
    """
    # Сбрасываем состояние
    await state.clear()

    # Извлекаем выбранный язык из callback_data
    language = callback.data.split(":")[1]  # "lang:ru" -> "ru"

    # Переключаем язык в системе i18n
    i18n = config.bot.i18n
    i18n.set_language(language)

    # Получаем тексты из i18n
    welcome_text = i18n.get("start.language_selected")
    catalog_text = i18n.get("menu.catalog")

    # Удаляем сообщение с выбором языка
    await callback.message.delete()

    # Отправляем приветствие с навигационной панелью
    await callback.message.answer(
        text=welcome_text,
        reply_markup=get_navigation_panel_keyboard(i18n)
    )

    # Сразу показываем каталог товаров
    await callback.message.answer(
        text=catalog_text,
        reply_markup=get_main_menu_keyboard(i18n),
        parse_mode="HTML"
    )

    # Отвечаем на callback
    await callback.answer()


@router.callback_query(F.data == "action:back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обработчик кнопки "Вернуться в меню".

    Возвращает пользователя в главное меню.
    """
    # Сбрасываем состояние
    await state.clear()

    # Получаем текст из i18n
    i18n = config.bot.i18n
    menu_text = i18n.get("menu.main")

    await callback.message.edit_text(
        text=menu_text,
        reply_markup=get_main_menu_keyboard(i18n)
    )

    await callback.answer()
