"""
Обработчик текстовых сообщений с AI Assistant.

Перехватывает текстовые сообщения от пользователей без активного FSM-состояния
и использует OpenAI Assistants API для консультаций и FAQ.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from core.config import Config
from core.ai.assistant import AssistantManager, get_or_create_thread
from core.ai.response_parser import (
    detect_response_type,
    extract_order_data,
    format_response_for_platform
)
from core.utils.category_mapper import get_category_name
from core.keyboards import get_main_menu_keyboard
from core.db import get_session
from core.db.queries import search_patterns, get_tenant_by_slug
from core.states import OrderFlow

logger = logging.getLogger(__name__)

router = Router()

# Глобальный экземпляр AssistantManager (инициализируется при запуске бота)
assistant_manager: AssistantManager = None


def init_assistant_manager():
    """Инициализирует глобальный AssistantManager."""
    global assistant_manager
    try:
        assistant_manager = AssistantManager()
        logger.info("✅ Telegram: AssistantManager initialized")
    except Exception as e:
        logger.error(f"❌ Telegram: Failed to initialize AssistantManager: {e}")
        raise


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message_with_ai(message: Message, state: FSMContext, config: Config):
    """
    Обрабатывает текстовые сообщения с помощью AI Assistant.

    Вызывается только если:
    - Сообщение текстовое
    - Не является командой (не начинается с /)
    - У пользователя нет активного FSM-состояния

    Args:
        message: Сообщение от пользователя
        state: FSM контекст
        config: Конфигурация tenant
    """
    # ДИАГНОСТИКА: Логируем ВСЕ входящие текстовые сообщения
    logger.info(f"🔍 [AI_HANDLER] Caught text message: '{message.text[:50]}...' from user {message.from_user.id}")

    # ИЗОЛЯЦИЯ: Для five_deluxe AI отключен - используется только FSM
    if config.bot.tenant_slug == "five_deluxe":
        logger.info(f"⏭️  [AI_HANDLER] Skipping - five_deluxe uses FSM-only mode (no AI)")
        # Игнорируем сообщение - пользователь должен использовать кнопки
        return

    # Проверяем, есть ли активное FSM-состояние
    current_state = await state.get_state()

    logger.info(f"🔍 [AI_HANDLER] Current FSM state: {current_state}")

    # Если есть активное состояние - игнорируем (другие обработчики сработают)
    if current_state is not None:
        logger.info(f"⏭️  [AI_HANDLER] Skipping - user has active FSM state: {current_state}")
        return

    # Проверяем, инициализирован ли AssistantManager
    if assistant_manager is None:
        logger.error("❌ AssistantManager не инициализирован")
        await message.answer(
            text="🤖 AI-помощник временно недоступен. Попробуйте позже.",
            reply_markup=get_main_menu_keyboard(config.bot.i18n)
        )
        return

    user_text = message.text
    user_id = str(message.from_user.id)

    logger.info(f"🤖 AI Assistant: Processing message from user {user_id}: {user_text[:50]}...")

    # Получаем или создаем thread для пользователя
    thread_id = get_or_create_thread(user_id, assistant_manager)

    try:
        # Получаем ответ от Ассистента
        response, ai_command = await assistant_manager.get_response(thread_id, user_text, chat_id=user_id)

        logger.info(f"✅ Получен ответ от Ассистента ({len(response)} символов)")

        # ============================================================
        # ОБРАБОТКА СИСТЕМНЫХ КОМАНД ОТ AI
        # ============================================================
        if ai_command:
            intent = ai_command.get("intent")
            logger.info(f"🎯 [AI_COMMAND] Обнаружена команда от AI: {intent}")

            if intent == "SHOW_CATALOG":
                logger.info("📖 [AI_COMMAND] Показываю каталог (главное меню)")
                await message.answer(
                    text="📖 Вот наш каталог товаров:",
                    reply_markup=get_main_menu_keyboard(config.bot.i18n)
                )
                return

            elif intent == "SHOW_MAIN_MENU":
                logger.info("🏠 [AI_COMMAND] Показываю главное меню")
                await message.answer(
                    text="🏠 Главное меню:",
                    reply_markup=get_main_menu_keyboard(config.bot.i18n)
                )
                return

        # ============================================================
        # ОБРАБОТКА ОБЫЧНЫХ ОТВЕТОВ (продолжаем как было)
        # ============================================================

        # Определяем тип ответа
        response_type, parsed_data = detect_response_type(response)

        if response_type == "json" and parsed_data:
            # Проверяем тип намерения
            intent = parsed_data.get("intent", "order").upper()
            logger.info(f"🎯 Обнаружен JSON с намерением: {intent}")

            # ============================================================
            # НОВЫЙ СЦЕНАРИЙ: CALLBACK_REQUEST (Запрос на обратный звонок)
            # ============================================================
            if intent == "CALLBACK_REQUEST":
                logger.info(f"📞 [CALLBACK_REQUEST] Запрос на обратный звонок")

                # Извлекаем детали вопроса
                callback_details = parsed_data.get("details", "Не указано")
                logger.info(f"📝 [CALLBACK_REQUEST] Детали: {callback_details}")

                # Сохраняем детали в FSM state
                await state.update_data(
                    callback_details=callback_details,
                    request_type="callback"
                )

                # Переходим к сбору контактов
                await state.set_state(OrderFlow.waiting_for_name)

                await message.answer(
                    text="✅ Отлично! Я передам ваш запрос менеджеру.\n\n"
                         "📝 Шаг 1/2: Введите ваше имя",
                    parse_mode="HTML"
                )
                return

            # ============================================================
            # СУЩЕСТВУЮЩИЙ СЦЕНАРИЙ: ORDER (Заказ товара)
            # ============================================================
            # JSON ответ с намерением заказа - запускаем FSM сценарий
            logger.info(f"🛒 [ORDER] Обнаружен JSON с намерением заказа: {parsed_data}")

            order_data = extract_order_data(parsed_data)

            # Извлекаем данные
            category = order_data.get("category", "eva_mats")
            brand = order_data.get("brand")
            model = order_data.get("model")

            i18n = config.bot.i18n

            if brand and model:
                # Есть и марка и модель - запускаем поиск лекал
                logger.info(f"📋 Запуск поиска лекал: {brand} {model}")

                # Сохраняем данные в FSM state
                category_name = get_category_name(category, i18n)
                logger.info(f"🏷️  [CATEGORY_FIX] category={category} -> category_name={category_name}")

                await state.update_data(
                    category=category,
                    category_name=category_name,
                    brand_name=brand,
                    model_name=model
                )

                # Устанавливаем состояние
                await state.set_state(OrderFlow.waiting_for_model)

                # Показываем что ищем
                search_msg = await message.answer(
                    "🔍 Ищу лекала в базе данных...",
                    parse_mode="HTML"
                )

                # Ищем лекала в БД
                async for session in get_session():
                    tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)

                    if not tenant:
                        await search_msg.edit_text(
                            i18n.get("errors.configuration"),
                            parse_mode="HTML"
                        )
                        await state.clear()
                        return

                    patterns = await search_patterns(
                        session,
                        brand_name=brand,
                        model_name=model,
                        tenant_id=tenant.id,
                        category_code=category
                    )

                    if patterns:
                        # Лекала найдены! Используем handle_patterns_found из eva_mats
                        from core.handlers.eva_mats import handle_patterns_found
                        await handle_patterns_found(search_msg, state, patterns, brand, model)
                    else:
                        # Лекала не найдены - используем handle_patterns_not_found из eva_mats
                        from core.handlers.eva_mats import handle_patterns_not_found
                        await handle_patterns_not_found(search_msg, state, brand, model)

            elif brand:
                # Есть только марка - просим уточнить модель
                logger.info(f"📋 Есть марка {brand}, но нет модели - просим уточнить")

                category_name = get_category_name(category, i18n)
                logger.info(f"🏷️  [CATEGORY_FIX] category={category} -> category_name={category_name}")

                await state.update_data(
                    category=category,
                    category_name=category_name,
                    brand_name=brand
                )

                await state.set_state(OrderFlow.waiting_for_model)

                await message.answer(
                    text=f"✅ Понял, вы интересуетесь EVA-ковриками для <b>{brand}</b>.\n\n"
                         f"Пожалуйста, уточните модель вашего автомобиля.\n\n"
                         f"<i>Например: Camry, Land Cruiser, RAV4</i>",
                    parse_mode="HTML"
                )

            else:
                # Намерение заказа есть, но данных недостаточно - показываем меню
                logger.info("⚠️ Намерение заказа без марки/модели - показываем меню")
                await message.answer(
                    text=f"🤖 Понял, вы хотите заказать {i18n.get('buttons.categories.eva_mats')}.\n\n"
                         f"Давайте начнем! Выберите категорию в меню:",
                    reply_markup=get_main_menu_keyboard(i18n)
                )

        else:
            # Текстовый ответ (FAQ) - форматируем для Telegram и отправляем
            logger.info("📝 Текстовый ответ (FAQ)")
            formatted_response = format_response_for_platform(response, "telegram")
            await message.answer(text=formatted_response, parse_mode="HTML")

    except Exception as e:
        logger.error(f"❌ Ошибка при обращении к Ассистенту: {e}")

        # Fallback: показываем сообщение об ошибке
        await message.answer(
            text="🤖 Извините, произошла ошибка при обработке вашего запроса.\n\n"
                 "Попробуйте переформулировать вопрос или выберите нужный раздел:",
            reply_markup=get_main_menu_keyboard(config.bot.i18n)
        )
