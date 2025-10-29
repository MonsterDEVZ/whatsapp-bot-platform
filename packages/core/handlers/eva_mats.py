"""
Обработчик для сценария заказа EVA-ковриков с FSM.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from core.states import OrderFlow
from core.keyboards import get_cancel_keyboard, get_back_to_menu_keyboard
from core.db import get_session
from core.db.queries import (
    search_patterns,
    get_tenant_by_slug,
    calculate_total_price,
    get_model_with_body_type
)
from core.config import Config
from core.debug_mode import debug_mode, format_debug_info

router = Router()


@router.callback_query(F.data == "category:eva_mats")
async def start_eva_mats_order(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Начало сценария заказа EVA-ковриков.
    Показывает пагинированный список всех марок из PostgreSQL.
    """
    from core.keyboards import get_brands_keyboard_paginated
    from core.db.queries import get_unique_brands_from_db, get_tenant_by_slug

    i18n = config.bot.i18n

    # Загружаем список всех марок из PostgreSQL
    async for session in get_session():
        tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)

        if not tenant:
            await callback.message.edit_text(
                i18n.get("errors.configuration"),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        brands_list = await get_unique_brands_from_db(tenant.id, session)

    # Сохраняем категорию в состоянии
    await state.update_data(category="eva_mats", category_name=i18n.get("buttons.categories.eva_mats"))

    # Переключаем состояние
    await state.set_state(OrderFlow.waiting_for_brand)

    text = i18n.get("categories.eva_mats.intro")

    await callback.message.edit_text(
        text=text,
        reply_markup=get_brands_keyboard_paginated(brands_list, page=1, i18n=i18n),
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(F.data.startswith("brands_page:"), OrderFlow.waiting_for_brand)
async def handle_brands_pagination(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обработчик переключения страниц при выборе марки.
    """
    from core.keyboards import get_brands_keyboard_paginated
    from core.db.queries import get_unique_brands_from_db, get_tenant_by_slug

    i18n = config.bot.i18n

    # Извлекаем номер страницы из callback_data
    page = int(callback.data.split(":")[1])

    # Загружаем список всех марок из PostgreSQL
    async for session in get_session():
        tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)

        if not tenant:
            await callback.answer("Configuration error", show_alert=True)
            return

        brands_list = await get_unique_brands_from_db(tenant.id, session)

    # Обновляем клавиатуру с новой страницей
    await callback.message.edit_reply_markup(
        reply_markup=get_brands_keyboard_paginated(brands_list, page=page, i18n=i18n)
    )

    await callback.answer()


@router.callback_query(F.data.startswith("brand_select:"), OrderFlow.waiting_for_brand)
async def process_brand_selection(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обработчик выбора марки из пагинированного списка.
    Ищет модели для выбранной марки в PostgreSQL.
    """
    from core.db.queries import get_models_for_brand_from_db, get_tenant_by_slug
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    i18n = config.bot.i18n

    # Извлекаем название марки из callback_data
    brand_name = callback.data.split(":", 1)[1]

    # Сохраняем марку
    await state.update_data(brand_name=brand_name)

    # Загружаем модели для выбранной марки из PostgreSQL
    async for session in get_session():
        tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)

        if not tenant:
            await callback.message.edit_text(
                i18n.get("errors.configuration"),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        models_list = await get_models_for_brand_from_db(brand_name, tenant.id, session)

    if not models_list:
        # Если моделей нет, показываем сообщение
        text = (
            f"❌ К сожалению, для марки <b>{brand_name}</b> пока нет доступных лекал.\n\n"
            f"Вы можете заказать индивидуальный замер или связаться с менеджером."
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="📞 Связаться с менеджером",
                callback_data="action:contact_manager"
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
        await state.clear()
        await callback.answer()
        return

    # Переключаем состояние на ожидание модели
    await state.set_state(OrderFlow.waiting_for_model)

    # Показываем информацию о моделях
    text = (
        f"✅ Вы выбрали марку: <b>{brand_name}</b>\n\n"
        f"Найдено моделей: {len(models_list)}\n\n"
        f"Пожалуйста, введите название модели вашего автомобиля.\n\n"
        f"<i>Например: Camry, Land Cruiser, RAV4</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад к маркам",
            callback_data="category:eva_mats"
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

    await callback.answer()


@router.callback_query(F.data.startswith("page_info:"))
async def handle_page_info_click(callback: CallbackQuery):
    """
    Обработчик нажатия на кнопку с номером страницы (некликабельная кнопка).
    Просто игнорируем клик.
    """
    await callback.answer("📄 Это информация о текущей странице", show_alert=False)


@router.callback_query(F.data == "input:brand", OrderFlow.waiting_for_brand)
async def request_brand_input(callback: CallbackQuery, config: Config):
    """
    Обрабатывает нажатие кнопки "Ввести другую марку".
    """
    i18n = config.bot.i18n
    text = i18n.get("order.brand.input")

    await callback.message.edit_text(
        text=text,
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(F.data.startswith("brand:"), OrderFlow.waiting_for_brand)
async def process_brand_button(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обрабатывает выбор марки из кнопок.
    """
    from core.keyboards import get_popular_models_keyboard
    from core.constants import CALLBACK_BRAND_PREFIX

    i18n = config.bot.i18n

    # Извлекаем название марки из callback_data
    brand_name = callback.data.replace(CALLBACK_BRAND_PREFIX, "")

    # Сохраняем марку
    await state.update_data(brand_name=brand_name)

    # Переключаем состояние
    await state.set_state(OrderFlow.waiting_for_model)

    text = i18n.get("order.brand.selected").replace("{brand_name}", brand_name)

    await callback.message.edit_text(
        text=text,
        reply_markup=get_popular_models_keyboard(brand_name, i18n=i18n),
        parse_mode="HTML"
    )

    await callback.answer()


@router.message(OrderFlow.waiting_for_brand)
async def process_brand(message: Message, state: FSMContext, config: Config):
    """
    Обработка ввода марки автомобиля вручную.
    Сохраняет марку и показывает кнопки с популярными моделями.
    """
    from core.keyboards import get_popular_models_keyboard

    i18n = config.bot.i18n
    brand_name = message.text.strip()

    # Сохраняем марку
    await state.update_data(brand_name=brand_name)

    # Переключаем состояние
    await state.set_state(OrderFlow.waiting_for_model)

    text = i18n.get("order.brand.selected").replace("{brand_name}", brand_name)

    await message.answer(
        text=text,
        reply_markup=get_popular_models_keyboard(brand_name, i18n=i18n),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "input:model", OrderFlow.waiting_for_model)
async def request_model_input(callback: CallbackQuery, config: Config):
    """
    Обрабатывает нажатие кнопки "Ввести другую модель".
    """
    i18n = config.bot.i18n
    text = i18n.get("order.model.input")

    await callback.message.edit_text(
        text=text,
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(F.data.startswith("use_suggestion:"), OrderFlow.waiting_for_model)
async def process_suggestion_confirmation(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обрабатывает подтверждение предложенной модели из fuzzy search.
    """
    from core.constants import CALLBACK_USE_SUGGESTION
    from core.db.queries import search_patterns, get_tenant_by_slug
    from core.db.session import get_session

    # Извлекаем название модели из callback_data
    model_name = callback.data.replace(CALLBACK_USE_SUGGESTION, "")

    # Получаем данные из состояния
    data = await state.get_data()
    brand_name = data.get("brand_name")
    category = data.get("category", "eva_mats")

    await callback.message.edit_text(
        "🔍 Ищу лекала в базе данных...",
        parse_mode="HTML"
    )

    # Получаем tenant и ищем лекала
    async for session in get_session():
        tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)

        if not tenant:
            i18n = config.bot.i18n
            await callback.message.edit_text(
                i18n.get("errors.configuration"),
                parse_mode="HTML"
            )
            await state.clear()
            return

        # Проверяем режим отладки
        is_debug = debug_mode.is_enabled(callback.from_user.id)

        # Ищем лекала
        if is_debug:
            patterns, debug_info = await search_patterns(
                session,
                brand_name=brand_name,
                model_name=model_name,
                tenant_id=tenant.id,
                category_code=category,
                return_debug_info=True
            )

            # Отправляем отладочную информацию
            debug_text = format_debug_info(
                brand=brand_name,
                model=model_name,
                category=category,
                sql_query=debug_info.get('patterns_query', ''),
                result_count=debug_info.get('result_count', 0),
                additional_info=f"Brand ID: {debug_info.get('brand_query', 'N/A')}\nModel ID: {debug_info.get('model_query', 'N/A')}"
            )
            await callback.message.answer(debug_text, parse_mode="HTML")
        else:
            patterns = await search_patterns(
                session,
                brand_name=brand_name,
                model_name=model_name,
                tenant_id=tenant.id,
                category_code=category
            )

        if patterns:
            # Лекала найдены!
            await handle_patterns_found(callback.message, state, patterns, brand_name, model_name)
        else:
            # Лекала не найдены (хотя не должно такого быть, т.к. модель была в БД)
            await handle_patterns_not_found(callback.message, state, brand_name, model_name)

    await callback.answer()


async def handle_patterns_found(message, state: FSMContext, patterns: list, brand_name: str, model_name: str):
    """
    Обрабатывает случай, когда лекала найдены в базе.
    Показывает опции для выбора.
    """
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    # Сохраняем данные в состояние
    await state.update_data(
        model_name=model_name,
        patterns=patterns
    )

    text = (
        f"✅ <b>Отличные новости!</b>\n\n"
        f"У нас есть лекала для <b>{brand_name} {model_name}</b>!\n\n"
        f"Найдено вариантов: {len(patterns)}\n\n"
        f"Выберите дополнительные опции:"
    )

    # Создаем клавиатуру с опциями
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ С бортами (рекомендуем)",
            callback_data="option:with_borders"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Без бортов",
            callback_data="option:without_borders"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❓ Не знаю, нужна консультация",
            callback_data="option:need_consultation"
        )
    )

    await message.edit_text(
        text=text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

    # Переключаем состояние
    await state.set_state(OrderFlow.selecting_options)


async def handle_patterns_not_found(message, state: FSMContext, brand_name: str, model_name: str):
    """
    Обрабатывает случай, когда лекала не найдены в базе.
    Предлагает индивидуальный замер или связь с менеджером.
    """
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    text = (
        f"💡 <b>Отличная новость!</b>\n\n"
        f"Похоже, готовых лекал для <b>{brand_name} {model_name}</b> "
        f"у нас пока нет в базе.\n\n"
        f"<b>Но это не проблема!</b> 🎯\n\n"
        f"Мы специализируемся на индивидуальных заказах и "
        f"создадим коврики специально для вашего автомобиля!\n\n"
        f"✨ <b>Преимущества индивидуального замера:</b>\n"
        f"• Идеальная посадка под ваш автомобиль\n"
        f"• Учет всех особенностей салона\n"
        f"• Качество как у готовых лекал\n"
        f"• Выезд мастера для замеров\n\n"
        f"Готовы оформить заказ? 😊"
    )

    # Создаем клавиатуру с альтернативами
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📝 Заказать индивидуальный замер",
            callback_data="request:individual_measure"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📞 Связаться с менеджером",
            callback_data="action:contact_manager"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Вернуться в меню",
            callback_data="action:back_to_menu"
        )
    )

    await message.edit_text(
        text=text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

    # Сбрасываем состояние
    await state.clear()


@router.callback_query(F.data.startswith("model:"), OrderFlow.waiting_for_model)
async def process_model_button(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обрабатывает выбор модели из кнопок.
    Переходит сразу к поиску лекал.
    """
    from core.constants import CALLBACK_MODEL_PREFIX

    # Извлекаем название модели из callback_data
    model_name = callback.data.replace(CALLBACK_MODEL_PREFIX, "")

    # Сохраняем модель
    await state.update_data(model_name=model_name)

    # Получаем данные из состояния
    data = await state.get_data()
    brand_name = data.get("brand_name")
    category = data.get("category", "eva_mats")

    # Показываем что ищем
    await callback.message.edit_text(
        "🔍 Ищу лекала в базе данных...",
        parse_mode="HTML"
    )

    # Выполняем поиск лекал (копируем логику из process_model)
    async for session in get_session():
        tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)

        if not tenant:
            await callback.message.edit_text(
                "❌ Ошибка конфигурации. Попробуйте позже.",
                parse_mode="HTML"
            )
            await state.clear()
            await callback.answer()
            return

        # Проверяем режим отладки
        is_debug = debug_mode.is_enabled(callback.from_user.id)

        # Ищем лекала
        if is_debug:
            patterns, debug_info = await search_patterns(
                session,
                brand_name=brand_name,
                model_name=model_name,
                tenant_id=tenant.id,
                category_code=category,
                return_debug_info=True
            )

            # Отправляем отладочную информацию
            debug_text = format_debug_info(
                brand=brand_name,
                model=model_name,
                category=category,
                sql_query=debug_info.get('patterns_query', ''),
                result_count=debug_info.get('result_count', 0),
                additional_info=f"Brand Query: {debug_info.get('brand_query', 'N/A')}\nModel Query: {debug_info.get('model_query', 'N/A')}"
            )
            await callback.message.answer(debug_text, parse_mode="HTML")
        else:
            patterns = await search_patterns(
                session,
                brand_name=brand_name,
                model_name=model_name,
                tenant_id=tenant.id,
                category_code=category
            )

        if patterns:
            # Лекала найдены! Переходим к выбору опций
            await handle_patterns_found(callback.message, state, patterns, brand_name, model_name)
        else:
            # Лекала не найдены - переходим к индивидуальному замеру
            await handle_patterns_not_found(callback.message, state, brand_name, model_name)

    await callback.answer()


@router.message(OrderFlow.waiting_for_model)
async def process_model(message: Message, state: FSMContext, config: Config):
    """
    Обработка ввода модели автомобиля.
    Ищет лекала в базе данных.
    """
    model_name = message.text.strip()

    # Получаем данные из состояния
    data = await state.get_data()
    brand_name = data.get("brand_name")
    category = data.get("category", "eva_mats")

    # Показываем что ищем
    search_msg = await message.answer(
        "🔍 Ищу лекала в базе данных...",
        parse_mode="HTML"
    )

    # Получаем tenant
    async for session in get_session():
        tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)

        if not tenant:
            await search_msg.edit_text(
                "❌ Ошибка конфигурации. Попробуйте позже.",
                parse_mode="HTML"
            )
            await state.clear()
            return

        # Проверяем режим отладки
        is_debug = debug_mode.is_enabled(message.from_user.id)

        # Ищем лекала
        if is_debug:
            patterns, debug_info = await search_patterns(
                session,
                brand_name=brand_name,
                model_name=model_name,
                tenant_id=tenant.id,
                category_code=category,
                return_debug_info=True
            )

            # Отправляем отладочную информацию
            debug_text = format_debug_info(
                brand=brand_name,
                model=model_name,
                category=category,
                sql_query=debug_info.get('patterns_query', ''),
                result_count=debug_info.get('result_count', 0),
                additional_info=f"Brand Query: {debug_info.get('brand_query', 'N/A')}\nModel Query: {debug_info.get('model_query', 'N/A')}"
            )
            await message.answer(debug_text, parse_mode="HTML")
        else:
            patterns = await search_patterns(
                session,
                brand_name=brand_name,
                model_name=model_name,
                tenant_id=tenant.id,
                category_code=category
            )

        if patterns:
            # Лекала найдены!
            await handle_patterns_found(search_msg, state, patterns, brand_name, model_name)
        else:
            # Лекала не найдены точным поиском - попробуем fuzzy search
            from core.db.queries import get_brand_by_name, fuzzy_search_model
            from core.keyboards import get_suggestion_keyboard

            # Получаем бренд для fuzzy search
            brand = await get_brand_by_name(session, brand_name)

            if brand:
                # Выполняем нечеткий поиск
                suggested_model, similarity = await fuzzy_search_model(
                    session,
                    brand_id=brand.id,
                    model_name=model_name,
                    threshold=85.0
                )

                if suggested_model:
                    # Найдена похожая модель - предлагаем пользователю
                    text = (
                        f"🤔 Не удалось найти модель '<b>{model_name}</b>'.\n\n"
                        f"Возможно, вы имели в виду:\n"
                        f"<b>{suggested_model}</b> (схожесть: {similarity:.0f}%)\n\n"
                        f"Использовать эту модель?"
                    )

                    await search_msg.edit_text(
                        text=text,
                        reply_markup=get_suggestion_keyboard(suggested_model, i18n=config.bot.i18n),
                        parse_mode="HTML"
                    )
                    return

            # Fuzzy search не помог или бренд не найден
            await handle_patterns_not_found(search_msg, state, brand_name, model_name)


@router.callback_query(F.data.startswith("option:"), OrderFlow.selecting_options)
async def process_option_selection(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обработка выбора опций продукта.
    """
    option = callback.data.split(":")[1]

    # Получаем данные
    data = await state.get_data()
    brand_name = data.get("brand_name")
    model_name = data.get("model_name")
    category_name = data.get("category_name", "EVA-коврики")

    # Сохраняем выбранную опцию
    await state.update_data(selected_option=option)

    option_names = {
        "with_borders": "С бортами",
        "without_borders": "Без бортов",
        "need_consultation": "Требуется консультация"
    }

    option_text = option_names.get(option, option)

    if option == "need_consultation":
        # Если нужна консультация, сразу отправляем заявку
        text = (
            f"📋 <b>Ваша заявка:</b>\n\n"
            f"• Товар: {category_name}\n"
            f"• Автомобиль: {brand_name} {model_name}\n"
            f"• Опция: {option_text}\n\n"
            f"✅ Заявка отправлена менеджерам!\n"
            f"Мы свяжемся с вами в ближайшее время для консультации."
        )

        # TODO: Отправить заявку в группу менеджеров
        from handlers.requests import send_request_to_group

        await send_request_to_group(
            callback.bot,
            callback,
            category=f"eva_mats ({brand_name} {model_name}, требуется консультация)",
            config=config
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_menu_keyboard(i18n=config.bot.i18n),
            parse_mode="HTML"
        )

        await state.clear()

    else:
        # Рассчитываем динамическую цену из БД
        async for session in get_session():
            tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)
            model, body_type = await get_model_with_body_type(session, brand_name, model_name)

            # Формируем выбранные опции
            selected_options = {
                'with_borders': (option == "with_borders"),
                'third_row': False  # Пока не реализовано в UI
            }

            # Рассчитываем динамическую цену
            total_price, price_breakdown = await calculate_total_price(
                session,
                tenant.id,
                'eva_mats',
                body_type.code if body_type else 'sedan',
                selected_options
            )

            # Сохраняем цену и детали ценообразования
            await state.update_data(
                total_price=int(total_price),
                price_breakdown=price_breakdown
            )

        # Подтверждение заказа
        text = (
            f"📋 <b>Сводка вашего заказа:</b>\n\n"
            f"🚗 <b>Автомобиль:</b> {brand_name} {model_name}\n"
            f"📦 <b>Товар:</b> {category_name}\n"
            f"⚙️ <b>Опция:</b> {option_text}\n"
            f"💰 <b>Итоговая стоимость:</b> {total_price} сом\n\n"
            f"Готовы оформить заказ? 🎉"
        )

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Оформить заказ",
                callback_data="confirm:order"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="◀️ Вернуться в меню",
                callback_data="action:back_to_menu"
            )
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

        await state.set_state(OrderFlow.confirming_order)

    await callback.answer()


@router.callback_query(F.data == "confirm:order", OrderFlow.confirming_order)
async def confirm_order(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Подтверждение заказа и переход к сбору контактных данных.
    """
    # Переключаем состояние на ожидание имени
    await state.set_state(OrderFlow.waiting_for_name)

    text = (
        "✅ <b>Отлично!</b>\n\n"
        "Теперь мне нужна ваша контактная информация,\n"
        "чтобы наш менеджер мог с вами связаться.\n\n"
        "📝 <b>Шаг 1/2:</b> Введите ваше имя"
    )

    await callback.message.edit_text(
        text=text,
        parse_mode="HTML"
    )

    await callback.answer()


@router.message(OrderFlow.waiting_for_name)
async def process_name(message: Message, state: FSMContext, config: Config):
    """
    Обработка ввода имени клиента.
    Сохраняет имя и запрашивает номер телефона.
    """
    client_name = message.text.strip()

    # Сохраняем имя
    await state.update_data(client_name=client_name)

    # Переключаем состояние на ожидание телефона
    await state.set_state(OrderFlow.waiting_for_phone)

    from core.keyboards import get_phone_request_keyboard

    text = (
        f"✅ Спасибо, <b>{client_name}</b>!\n\n"
        f"📱 <b>Шаг 2/2:</b> Поделитесь вашим номером телефона\n\n"
        f"<i>Нажмите кнопку ниже, чтобы отправить номер телефона.</i>\n"
        f"Это быстро и безопасно! 🔒"
    )

    await message.answer(
        text=text,
        reply_markup=get_phone_request_keyboard(config.bot.i18n),
        parse_mode="HTML"
    )


@router.message(OrderFlow.waiting_for_phone, F.contact)
async def process_phone(message: Message, state: FSMContext, config: Config):
    """
    Обработка получения номера телефона клиента.
    Создает и отправляет карточку заявки в группу менеджеров.
    """
    phone = message.contact.phone_number

    # Сохраняем телефон
    await state.update_data(client_phone=phone)

    # Получаем все данные заказа
    data = await state.get_data()
    client_name = data.get("client_name")

    # Проверяем тип заявки
    request_type = data.get("request_type", "order")
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔍 Request type: {request_type}")

    # ============================================================
    # СЦЕНАРИЙ 1: CALLBACK_REQUEST (Запрос на обратный звонок)
    # ============================================================
    if request_type == "callback":
        logger.info(f"📞 [CALLBACK] Сохранение запроса на обратный звонок")

        callback_details = data.get("callback_details", "Не указано")

        from core.handlers.requests import send_callback_request_to_airtable

        success = await send_callback_request_to_airtable(
            bot=message.bot,
            user=message.from_user,
            config=config,
            client_name=client_name,
            client_phone=phone,
            callback_details=callback_details
        )

    # ============================================================
    # СЦЕНАРИЙ 2: ORDER (Обычный заказ товара)
    # ============================================================
    else:
        logger.info(f"🛒 [ORDER] Сохранение заказа товара")

        brand_name = data.get("brand_name", "Не указана")
        model_name = data.get("model_name", "Не указана")
        category_name = data.get("category_name", "EVA-коврики")
        selected_option = data.get("selected_option")
        total_price = data.get("total_price", 0)
        is_individual_measure = data.get("is_individual_measure", False)

        # Формируем детали заказа
        if is_individual_measure:
            option_text = "Индивидуальный замер"
            total_price = 0  # Цена будет определена после замера
        else:
            option_names = {
                "with_borders": "С бортами",
                "without_borders": "Без бортов"
            }
            option_text = option_names.get(selected_option, selected_option or "Не указана")

        # Отправляем детальную карточку заявки в группу
        from core.handlers.requests import send_detailed_request_card

        success = await send_detailed_request_card(
            bot=message.bot,
            user=message.from_user,
            client_name=client_name,
            client_phone=phone,
            brand_name=brand_name,
            model_name=model_name,
            category_name=category_name,
            option_details=option_text,
            total_price=total_price,
            config=config
        )

    if success:
        from core.keyboards import get_main_menu_button_keyboard, get_main_menu_keyboard

        # Возвращаем постоянную клавиатуру
        await message.answer(
            text="✅ <b>Спасибо! Ваша заявка принята.</b>\n\n"
                 "Наш менеджер скоро свяжется с вами для уточнения деталей.\n\n"
                 "Обычно это занимает 5-10 минут. 😊",
            reply_markup=get_main_menu_button_keyboard(config.bot.i18n),
            parse_mode="HTML"
        )

        # Показываем главное меню
        await message.answer(
            text="Главное меню 📋\n\nВыберите интересующую категорию товаров:",
            reply_markup=get_main_menu_keyboard(i18n=config.bot.i18n)
        )
    else:
        # Используем контакты из конфигурации
        contacts = config.bot.i18n.get("info_sections.contacts.text")
        text = (
            "⚠️ Произошла ошибка при отправке заявки.\n"
            "Пожалуйста, свяжитесь с нами напрямую:\n\n"
            f"{contacts}"
        )
        await message.answer(text=text, parse_mode="HTML")

    # Полная очистка состояния и памяти диалога
    await state.clear()
    
    # Очищаем AI memory (если используется)
    try:
        from core.ai.memory import get_memory
        memory = get_memory()
        memory.clear_history(str(message.from_user.id))
    except Exception:
        pass  # AI memory не используется или уже очищена


@router.message(F.text == "❌ Отменить")
async def cancel_order(message: Message, state: FSMContext, config: Config):
    """
    Отмена текущего процесса заказа.
    """
    await state.clear()

    from core.keyboards import get_main_menu_keyboard, get_main_menu_button_keyboard

    await message.answer(
        text="❌ Заказ отменен. Возвращаемся в главное меню.",
        reply_markup=get_main_menu_button_keyboard(config.bot.i18n)
    )

    await message.answer(
        text="Главное меню 📋\n\nВыберите интересующую категорию товаров:",
        reply_markup=get_main_menu_keyboard(i18n=config.bot.i18n)
    )


@router.callback_query(F.data == "request:individual_measure")
async def request_individual_measure(callback: CallbackQuery, state: FSMContext, config: Config):
    """
    Обработка заявки на индивидуальный замер.
    Запускает сбор контактных данных.
    """
    # Помечаем, что это индивидуальный замер
    await state.update_data(is_individual_measure=True)

    # Запускаем сценарий сбора контактов
    await state.set_state(OrderFlow.waiting_for_name)

    text = (
        "✅ <b>Отлично!</b>\n\n"
        "Давайте оформим заявку на индивидуальный замер.\n\n"
        "📝 <b>Шаг 1/2:</b> Введите ваше имя"
    )

    await callback.message.edit_text(
        text=text,
        parse_mode="HTML"
    )

    await callback.answer()
