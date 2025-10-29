"""
Обработчики для информационных разделов бота:
- Индивидуальный замер
- Наши работы
- О нас
- Помощь / FAQ
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.states import OrderFlow
from core.config import Config
from core.keyboards import get_phone_request_keyboard, get_main_menu_keyboard, get_main_menu_button_keyboard

router = Router()


# ============================================================
# ИНДИВИДУАЛЬНЫЙ ЗАМЕР
# ============================================================

@router.message(F.text == "📏 Индивидуальный замер")
async def start_individual_measure(message: Message, state: FSMContext, config: Config):
    """
    Обработчик кнопки "Индивидуальный замер".
    Запускает FSM-воронку сбора контактов для индивидуального замера.
    """
    i18n = config.bot.i18n

    # Сохраняем тип заявки
    await state.update_data(
        is_individual_measure=True,
        category_name=i18n.get("individual_measure.order_text")
    )

    # Переключаем состояние на ожидание имени
    await state.set_state(OrderFlow.waiting_for_name)

    await message.answer(
        text=i18n.get("individual_measure.short_intro"),
        parse_mode="HTML"
    )


# ============================================================
# НАШИ РАБОТЫ / ОТЗЫВЫ
# ============================================================

@router.message(F.text == "⭐️ Наши работы")
async def show_our_works(message: Message, config: Config):
    """
    Обработчик кнопки "Наши работы".
    Показывает сообщение со ссылкой на Instagram.
    """
    i18n = config.bot.i18n

    # Создаем клавиатуру с кнопкой Instagram
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.open_instagram"),
            url=config.bot.instagram_url
        )
    )

    await message.answer(
        text=i18n.get("info_sections.our_works.text"),
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


# ============================================================
# О НАС / КОНТАКТЫ
# ============================================================

@router.message(F.text == "ℹ️ О нас")
async def show_about_us(message: Message, config: Config):
    """
    Обработчик кнопки "О нас".
    Показывает информацию о компании и контакты.
    """
    i18n = config.bot.i18n
    await message.answer(
        text=i18n.get("info_sections.about_us.text"),
        parse_mode="HTML"
    )


# ============================================================
# ПОМОЩЬ / FAQ
# ============================================================

def get_faq_keyboard(i18n) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с вопросами FAQ.

    Args:
        i18n: Экземпляр I18nInstance для локализации

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками вопросов
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для каждого вопроса
    faq_keys = ["care", "timing", "delivery", "payment", "return"]
    for faq_key in faq_keys:
        builder.row(
            InlineKeyboardButton(
                text=i18n.get(f"faq.{faq_key}.question"),
                callback_data=f"faq:{faq_key}"
            )
        )

    return builder.as_markup()


@router.message(F.text == "❓ Помощь")
async def show_faq(message: Message, config: Config):
    """
    Обработчик кнопки "Помощь".
    Показывает меню с часто задаваемыми вопросами.
    """
    i18n = config.bot.i18n
    await message.answer(
        text=i18n.get("faq.intro"),
        reply_markup=get_faq_keyboard(i18n),
        parse_mode="HTML"
    )


# ============================================================
# ОБРАБОТЧИКИ CALLBACK ДЛЯ FAQ
# ============================================================

@router.callback_query(F.data.startswith("faq:"))
async def handle_faq_question(callback: CallbackQuery, config: Config):
    """
    Обработчик нажатий на кнопки FAQ.
    Отправляет ответ на выбранный вопрос.
    """
    i18n = config.bot.i18n

    # Извлекаем ключ вопроса
    faq_key = callback.data.split(":")[1]

    # Маппинг ключей на пути в JSON
    faq_answer_keys = {
        "care": "faq.care.short_answer",
        "timing": "faq.timing.answer",
        "delivery": "faq.delivery.short_answer",
        "payment": "faq.payment.answer",
        "return": "faq.return.answer"
    }

    answer_key = faq_answer_keys.get(faq_key)

    if not answer_key:
        await callback.answer(i18n.get("errors.try_again"), show_alert=True)
        return

    # Отправляем ответ
    await callback.message.answer(
        text=i18n.get(answer_key),
        parse_mode="HTML"
    )

    # Показываем меню FAQ снова
    await callback.message.answer(
        text=i18n.get("faq.select_question"),
        reply_markup=get_faq_keyboard(i18n)
    )

    await callback.answer()


# ============================================================
# ОБРАБОТЧИКИ FSM ДЛЯ СБОРА КОНТАКТОВ
# ============================================================

@router.message(OrderFlow.waiting_for_name, F.text)
async def process_name_individual_measure(message: Message, state: FSMContext, config: Config):
    """
    Обработка ввода имени для индивидуального замера.
    """
    i18n = config.bot.i18n
    
    client_name = message.text.strip()
    
    # Сохраняем имя
    await state.update_data(client_name=client_name)
    
    # Переходим к запросу телефона
    await state.set_state(OrderFlow.waiting_for_phone)
    
    await message.answer(
        text=i18n.get("order.contacts.name_received", client_name=client_name),
        reply_markup=get_phone_request_keyboard(i18n),
        parse_mode="HTML"
    )


@router.message(OrderFlow.waiting_for_phone, F.contact)
async def process_phone_individual_measure(message: Message, state: FSMContext, config: Config):
    """
    Обработка получения номера телефона для индивидуального замера.
    Отправляет заявку в группу и завершает сценарий.
    """
    i18n = config.bot.i18n
    phone = message.contact.phone_number
    
    # Сохраняем телефон
    await state.update_data(client_phone=phone)
    
    # Получаем все данные
    data = await state.get_data()
    client_name = data.get("client_name", "Не указано")
    category_name = data.get("category_name", i18n.get("individual_measure.order_text"))
    
    # Отправляем заявку в группу
    from core.handlers.requests import send_detailed_request_card
    
    success = await send_detailed_request_card(
        bot=message.bot,
        user=message.from_user,
        config=config,
        client_name=client_name,
        client_phone=phone,
        brand_name="Не указана",
        model_name="Не указана",
        category_name=category_name,
        option_details="Индивидуальный замер",
        total_price=0
    )
    
    if success:
        # Возвращаем навигационную панель
        await message.answer(
            text=i18n.get("order.confirmation.success"),
            reply_markup=get_main_menu_button_keyboard(i18n),
            parse_mode="HTML"
        )
        
        # Показываем главное меню
        await message.answer(
            text=i18n.get("menu.main"),
            reply_markup=get_main_menu_keyboard(i18n),
            parse_mode="HTML"
        )
    else:
        # Ошибка отправки - используем ДИНАМИЧЕСКИЕ контакты
        contacts = i18n.get("info_sections.contacts.text")
        error_text = (
            "⚠️ Произошла ошибка при отправке заявки.\n"
            "Пожалуйста, свяжитесь с нами напрямую:\n\n"
            f"{contacts}"
        )
        await message.answer(
            text=error_text,
            reply_markup=get_main_menu_button_keyboard(i18n),
            parse_mode="HTML"
        )
    
    # Очищаем состояние - КРИТИЧЕСКИ ВАЖНО!
    await state.clear()
