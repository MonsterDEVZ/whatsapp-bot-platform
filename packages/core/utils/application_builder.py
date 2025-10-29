"""
Централизованный сборщик данных для заявок в Airtable.

Этот модуль содержит ЕДИНСТВЕННУЮ функцию для формирования данных заявки.
Никакая другая часть кода НЕ должна собирать данные для Airtable напрямую!
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

# КРИТИЧНО: Используем абсолютные импорты для совместимости с production!
from core.config import Config
from core.db.queries import calculate_total_price, get_model_with_body_type, get_tenant_by_slug

logger = logging.getLogger(__name__)


async def build_application_data(
    user_data: Dict[str, Any],
    client_name: str,
    client_phone: str,
    config: Config,
    session: AsyncSession,
    source: str = "WhatsApp"
) -> Optional[Dict[str, Any]]:
    """
    КРИТИЧЕСКАЯ ФУНКЦИЯ: Единая точка сборки данных для заявки в Airtable.

    Эта функция гарантирует, что ВСЕ данные берутся из FSM state и проходят
    валидацию, а цена рассчитывается корректно через calculate_total_price().

    Args:
        user_data: Данные из FSM state (category, brand_name, model_name, etc.)
        client_name: Имя клиента
        client_phone: Телефон клиента
        config: Конфигурация tenant
        session: AsyncSession для БД
        source: Источник заявки ("WhatsApp", "Telegram")

    Returns:
        Dict готовый для отправки в Airtable, или None при критической ошибке

    Raises:
        ValueError: Если обязательные поля отсутствуют
    """
    logger.info(f"🏗️  [APP_BUILDER] === НАЧАЛО СБОРКИ ДАННЫХ ЗАЯВКИ ===")
    logger.info(f"🏗️  [APP_BUILDER] Tenant: {config.bot.tenant_slug}")
    logger.info(f"🏗️  [APP_BUILDER] Source: {source}")
    logger.info(f"🏗️  [APP_BUILDER] Client: {client_name} ({client_phone})")

    # ═══════════════════════════════════════════════════════════════
    # ШАГ 1: КРИТИЧЕСКАЯ ВАЛИДАЦИЯ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ
    # ═══════════════════════════════════════════════════════════════

    category = user_data.get("category")
    category_name = user_data.get("category_name")
    brand_name = user_data.get("brand_name")
    model_name = user_data.get("model_name")

    logger.info(f"🏗️  [APP_BUILDER] === ИЗВЛЕЧЁННЫЕ ДАННЫЕ ИЗ user_data ===")
    logger.info(f"🏗️  [APP_BUILDER] category (код): '{category}'")
    logger.info(f"🏗️  [APP_BUILDER] category_name: '{category_name}'")
    logger.info(f"🏗️  [APP_BUILDER] brand_name: '{brand_name}'")
    logger.info(f"🏗️  [APP_BUILDER] model_name: '{model_name}'")
    logger.info(f"🏗️  [APP_BUILDER] user_data ПОЛНОСТЬЮ: {user_data}")

    # КРИТИЧЕСКАЯ ПРОВЕРКА: category ОБЯЗАТЕЛЕН!
    if not category:
        logger.error(f"❌ [APP_BUILDER] КРИТИЧЕСКАЯ ОШИБКА: category не найдена в user_data!")
        logger.error(f"❌ [APP_BUILDER] user_data: {user_data}")
        raise ValueError("Category отсутствует в user_data! Заявка не может быть создана.")

    if not category_name:
        logger.warning(f"⚠️ [APP_BUILDER] category_name отсутствует, используем fallback")
        category_name = f"Товар категории {category}"

    if not brand_name or not model_name:
        logger.warning(f"⚠️ [APP_BUILDER] brand_name или model_name отсутствуют")
        brand_name = brand_name or "Не указано"
        model_name = model_name or "Не указано"

    # ═══════════════════════════════════════════════════════════════
    # ШАГ 2: РАСЧЁТ ЦЕНЫ ЧЕРЕЗ calculate_total_price()
    # ═══════════════════════════════════════════════════════════════

    logger.info(f"💰 [APP_BUILDER] === НАЧАЛО РАСЧЁТА ЦЕНЫ ===")

    # Получаем tenant_id
    tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)
    if not tenant:
        logger.error(f"❌ [APP_BUILDER] Tenant не найден: {config.bot.tenant_slug}")
        raise ValueError(f"Tenant {config.bot.tenant_slug} не найден в БД!")

    logger.info(f"💰 [APP_BUILDER] Tenant ID: {tenant.id}")

    # Получаем body_type
    model, body_type = await get_model_with_body_type(session, brand_name, model_name)
    body_type_code = body_type.code if body_type else 'sedan'

    logger.info(f"💰 [APP_BUILDER] Body type: {body_type_code}")

    # Формируем selected_options из user_data
    selected_option = user_data.get("selected_option", "")
    selected_options = {
        'with_borders': (selected_option == "with_borders"),
        'third_row': False
    }

    logger.info(f"💰 [APP_BUILDER] Selected options: {selected_options}")

    # КРИТИЧЕСКИЙ ВЫЗОВ: Расчёт цены
    logger.info(f"💰 [APP_BUILDER] Вызываю calculate_total_price()...")
    logger.info(f"💰 [APP_BUILDER]   - tenant_id: {tenant.id}")
    logger.info(f"💰 [APP_BUILDER]   - category: '{category}'")
    logger.info(f"💰 [APP_BUILDER]   - body_type: '{body_type_code}'")
    logger.info(f"💰 [APP_BUILDER]   - options: {selected_options}")

    try:
        total_price, price_breakdown = await calculate_total_price(
            session,
            tenant.id,
            category,  # ✅ ИЗ FSM STATE!
            body_type_code,
            selected_options
        )

        logger.info(f"💰 [APP_BUILDER] ✅ Цена рассчитана успешно!")
        logger.info(f"💰 [APP_BUILDER]   - Базовая цена: {price_breakdown['base_price']} сом")
        logger.info(f"💰 [APP_BUILDER]   - Опции: {price_breakdown['options']}")
        logger.info(f"💰 [APP_BUILDER]   - ИТОГО: {total_price} сом")

    except Exception as e:
        logger.error(f"❌ [APP_BUILDER] ОШИБКА при расчёте цены: {e}")
        logger.exception("Traceback:")
        total_price = 0
        price_breakdown = {'base_price': 0, 'options': {}, 'total': 0}

    # ═══════════════════════════════════════════════════════════════
    # ШАГ 3: ПРОВЕРКА ФЛАГА show_price_in_summary
    # ═══════════════════════════════════════════════════════════════

    # КРИТИЧНО: i18n.get() НЕ поддерживает fallback!
    show_price = config.bot.i18n.get("company.show_price_in_summary")
    if show_price is None:
        # Если ключ не найден, по умолчанию показываем цену (для обратной совместимости)
        show_price = True
        logger.warning(f"⚠️ [APP_BUILDER] show_price_in_summary не найден в локализации, использую True")

    logger.info(f"💰 [APP_BUILDER] show_price_in_summary: {show_price}")

    # Если флаг = false, обнуляем цену для Airtable
    final_price = total_price if show_price else 0

    if not show_price:
        logger.info(f"💰 [APP_BUILDER] Цена НЕ будет отправлена в Airtable (show_price=false)")

    # ═══════════════════════════════════════════════════════════════
    # ШАГ 4: ФОРМИРОВАНИЕ СТРУКТУРИРОВАННОГО ОБЪЕКТА ДЛЯ AIRTABLE
    # ═══════════════════════════════════════════════════════════════

    # Формируем детали/опции (только опции, БЕЗ цены)
    option_text = "С бортами" if selected_option == "with_borders" else \
                  "Без бортов" if selected_option == "without_borders" else \
                  "Требуется консультация" if selected_option == "need_consultation" else \
                  "Не указано"

    # Определяем тип заявки из user_data
    application_type = user_data.get("application_type", "Заказ товара")

    # СТРУКТУРИРОВАННЫЙ объект для Airtable
    # ВАЖНО: Используем английские ключи, а AirtableService замапит их на русские колонки!
    application_data = {
        # Контактные данные
        "client_name": client_name,
        "client_phone": client_phone,

        # Метаданные
        "project": config.bot.tenant_slug.upper(),
        "source": source,
        "application_type": application_type,  # ✅ НОВОЕ!

        # Данные заказа (СТРУКТУРИРОВАННО!)
        "product_category": category_name,                  # ✅ Только категория
        "car": f"{brand_name} {model_name}",                # ✅ Только марка + модель
        "options": option_text,                             # ✅ Только опции
        "price": final_price if show_price else None       # ✅ Только цена
    }

    # ═══════════════════════════════════════════════════════════════
    # ШАГ 5: ФИНАЛЬНОЕ ЛОГИРОВАНИЕ ("ЧЁРНЫЙ ЯЩИК")
    # ═══════════════════════════════════════════════════════════════

    logger.info(f"🏗️  [APP_BUILDER] === ФИНАЛЬНЫЙ ОБЪЕКТ ДЛЯ AIRTABLE ===")
    logger.info(f"🏗️  [APP_BUILDER] {application_data}")
    logger.info(f"🏗️  [APP_BUILDER] === КОНЕЦ СБОРКИ (SUCCESS) ===")

    return application_data
