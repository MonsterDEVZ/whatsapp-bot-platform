"""
Обработчики для навигационной панели бота.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from core.keyboards import get_main_menu_keyboard
from core.states import OrderFlow
from core.config import Config

router = Router()


@router.message(F.text == "🗂️ Каталог товаров")
async def show_catalog(message: Message, state: FSMContext, config: Config):
    """
    Обработчик кнопки "Каталог товаров".

    Сбрасывает состояние и показывает категории товаров (главное меню).
    """
    # Сбрасываем любое текущее состояние
    await state.clear()

    i18n = config.bot.i18n
    text = i18n.get("menu.catalog")

    await message.answer(
        text=text,
        reply_markup=get_main_menu_keyboard(i18n),
        parse_mode="HTML"
    )


@router.message(F.text == "📏 Индивидуальный замер")
async def individual_measurement(message: Message, state: FSMContext, config: Config):
    """
    Обработчик кнопки "Индивидуальный замер".

    Запускает сценарий сбора контактов для индивидуального замера.
    """
    # Сбрасываем любое предыдущее состояние
    await state.clear()

    i18n = config.bot.i18n

    # Сохраняем тип заявки
    await state.update_data(
        request_type="individual_measurement",
        category_name=i18n.get("individual_measure.order_text"),
        brand_name="",
        model_name=""
    )

    # Переключаемся на сбор имени
    await state.set_state(OrderFlow.waiting_for_name)

    text = i18n.get("individual_measure.short_intro")

    await message.answer(
        text=text,
        parse_mode="HTML"
    )


@router.message(F.text == "⭐️ Наши работы")
async def our_works(message: Message, state: FSMContext, config: Config):
    """
    Обработчик кнопки "Наши работы".

    Показывает ссылку на Instagram с примерами работ.
    """
    # Сбрасываем состояние
    await state.clear()

    i18n = config.bot.i18n
    text = i18n.get("our_works.short_text")

    # Создаем кнопку со ссылкой на Instagram
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.open_instagram"),
            url=config.bot.instagram_url
        )
    )

    await message.answer(
        text=text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.message(F.text == "ℹ️ О нас")
async def about_us(message: Message, state: FSMContext, config: Config):
    """
    Обработчик кнопки "О нас".

    Показывает информацию о компании и контакты.
    """
    # Сбрасываем состояние
    await state.clear()

    i18n = config.bot.i18n
    text = i18n.get("about_us.short_text")

    await message.answer(
        text=text,
        parse_mode="HTML"
    )


@router.message(F.text == "❓ Помощь")
async def help_menu(message: Message, state: FSMContext, config: Config):
    """
    Обработчик кнопки "Помощь".

    Показывает FAQ с частыми вопросами.
    """
    # Сбрасываем состояние
    await state.clear()

    i18n = config.bot.i18n
    text = i18n.get("faq.intro")

    # Создаем меню FAQ
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("faq.care.question"),
            callback_data="faq:care"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("faq.timing.question"),
            callback_data="faq:timing"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("faq.delivery.question"),
            callback_data="faq:delivery"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("faq.payment.question"),
            callback_data="faq:payment"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("faq.return.question"),
            callback_data="faq:return"
        )
    )

    await message.answer(
        text=text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("faq:"))
async def faq_answer(callback, state: FSMContext, config: Config):
    """
    Обработчик ответов на FAQ вопросы.
    """
    faq_type = callback.data.split(":")[1]

    i18n = config.bot.i18n

    # Маппинг типов FAQ на ключи в JSON
    faq_keys = {
        "care": "faq.care.short_answer",
        "timing": "faq.timing.answer",
        "delivery": "faq.delivery.short_answer",
        "payment": "faq.payment.answer",
        "return": "faq.return.answer"
    }

    answer_key = faq_keys.get(faq_type)
    answer_text = i18n.get(answer_key) if answer_key else "Информация скоро появится"

    await callback.message.answer(
        text=answer_text,
        parse_mode="HTML"
    )

    await callback.answer()
