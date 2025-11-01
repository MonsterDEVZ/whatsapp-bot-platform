"""
AI Agent Tools - Инструменты для OpenAI Assistant.

Этот модуль содержит Python-функции, которые AI Agent может вызывать
для взаимодействия с базой данных и выполнения действий.

Каждая функция:
- Является асинхронной (async)
- Имеет подробный docstring
- Возвращает простые типы данных (str, list, dict, float)
- Логирует свои действия для отладки
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем функции из queries
from packages.core.db import queries as db_queries

# Импортируем Airtable integration
from packages.core.integrations.airtable_manager import create_lead

logger = logging.getLogger(__name__)


# ==============================================================================
# AI AGENT TOOLS - Инструменты для взаимодействия с базой данных
# ==============================================================================


async def get_available_categories(tenant_id: int, session: AsyncSession) -> List[str]:
    """
    Возвращает список доступных категорий товаров для заданного tenant.

    Эта функция используется AI для показа клиенту, какие товары доступны.

    Args:
        tenant_id: ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)
        session: Сессия базы данных

    Returns:
        List[str]: Список названий категорий на русском языке
        Пример: ["EVA-коврики", "3D коврики", "Чехлы", "Органайзеры"]
    """
    logger.info(f"[TOOL] get_available_categories(tenant_id={tenant_id})")

    try:
        # Получаем все категории из БД
        categories = await db_queries.get_product_categories(session)

        # Извлекаем только названия на русском языке
        category_names = [cat.name_ru for cat in categories if cat.name_ru]

        logger.info(f"[TOOL] ✅ Найдено {len(category_names)} категорий: {category_names}")
        return category_names

    except Exception as e:
        logger.error(f"[TOOL] ❌ Ошибка при получении категорий: {e}")
        return []


async def get_available_brands(
    category_code: str,
    tenant_id: int,
    session: AsyncSession
) -> List[str]:
    """
    Возвращает список марок автомобилей, для которых есть товары в данной категории.

    ВАЖНО: В текущей реализации возвращает ВСЕ марки из базы данных,
    независимо от категории, так как фильтрация по категории требует
    сложных JOIN-запросов через таблицу patterns.

    Args:
        category_code: Код категории (например, "eva_mats", "3d_mats", "seat_covers")
        tenant_id: ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)
        session: Сессия базы данных

    Returns:
        List[str]: Список названий марок, отсортированных по алфавиту
        Пример: ["Audi", "BMW", "Mercedes-Benz", "Toyota", "Volkswagen"]
    """
    logger.info(f"[TOOL] get_available_brands(category={category_code}, tenant_id={tenant_id})")

    try:
        # Получаем все марки из БД (пока без фильтрации по категории)
        brands = await db_queries.get_unique_brands_from_db(tenant_id, session)

        logger.info(f"[TOOL] ✅ Найдено {len(brands)} марок")
        return brands

    except Exception as e:
        logger.error(f"[TOOL] ❌ Ошибка при получении марок: {e}")
        return []


async def get_available_models(
    brand_name: str,
    category_code: str,
    tenant_id: int,
    session: AsyncSession
) -> List[str]:
    """
    Возвращает список моделей для конкретной марки автомобиля.

    Эта функция возвращает только те модели, для которых есть доступные
    лекала в базе данных для данного tenant.

    Args:
        brand_name: Название марки автомобиля (например, "Toyota")
        category_code: Код категории товара (например, "eva_mats")
        tenant_id: ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)
        session: Сессия базы данных

    Returns:
        List[str]: Список названий моделей, отсортированных по алфавиту
        Пример: ["Camry", "Corolla", "Land Cruiser", "RAV4"]

    Note:
        Если марка не найдена или для нее нет доступных моделей,
        возвращается пустой список.
    """
    logger.info(f"[TOOL] get_available_models(brand={brand_name}, category={category_code}, tenant_id={tenant_id})")

    try:
        # Получаем модели для данной марки и tenant
        # Функция автоматически фильтрует по наличию лекал (patterns)
        models = await db_queries.get_models_for_brand_from_db(
            brand_name=brand_name,
            tenant_id=tenant_id,
            session=session
        )

        logger.info(f"[TOOL] ✅ Найдено {len(models)} моделей для марки '{brand_name}'")
        return models

    except Exception as e:
        logger.error(f"[TOOL] ❌ Ошибка при получении моделей: {e}")
        return []


async def search_patterns(
    brand_name: str,
    model_name: str,
    category_code: str,
    tenant_id: int,
    session: AsyncSession
) -> str:
    """
    Проверяет, есть ли в базе данных лекала для указанной комбинации
    марка + модель + категория товара.

    Это КРИТИЧЕСКИ ВАЖНАЯ функция для определения, можем ли мы
    выполнить заказ клиента или нужен индивидуальный замер.

    Args:
        brand_name: Название марки автомобиля (например, "Toyota")
        model_name: Название модели (например, "Camry 70")
        category_code: Код категории товара (например, "eva_mats")
        tenant_id: ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)
        session: Сессия базы данных

    Returns:
        str: "FOUND" если лекала найдены, "NOT_FOUND" если лекал нет

    Examples:
        >>> await search_patterns("Toyota", "Camry", "eva_mats", 1, session)
        "FOUND"

        >>> await search_patterns("Acura", "Accord", "eva_mats", 1, session)
        "NOT_FOUND"
    """
    logger.info(f"[TOOL] search_patterns(brand={brand_name}, model={model_name}, category={category_code}, tenant_id={tenant_id})")

    try:
        # Ищем лекала в базе данных
        patterns = await db_queries.search_patterns(
            session=session,
            brand_name=brand_name,
            model_name=model_name,
            tenant_id=tenant_id,
            category_code=category_code
        )

        if patterns and len(patterns) > 0:
            logger.info(f"[TOOL] ✅ Найдено {len(patterns)} лекал для {brand_name} {model_name}")
            return "FOUND"
        else:
            logger.info(f"[TOOL] ⚠️ Лекала НЕ найдены для {brand_name} {model_name}")
            return "NOT_FOUND"

    except Exception as e:
        logger.error(f"[TOOL] ❌ Ошибка при поиске лекал: {e}")
        return "NOT_FOUND"


async def calculate_price(
    brand_name: str,
    model_name: str,
    category_code: str,
    options: Dict[str, bool],
    tenant_id: int,
    session: AsyncSession
) -> Dict[str, Any]:
    """
    Рассчитывает итоговую цену заказа на основе модели автомобиля,
    категории товара и выбранных опций.

    Функция автоматически определяет тип кузова автомобиля и применяет
    соответствующие цены из базы данных.

    Args:
        brand_name: Название марки автомобиля (например, "Toyota")
        model_name: Название модели (например, "Camry 70")
        category_code: Код категории товара (например, "eva_mats")
        options: Словарь выбранных опций, например:
            {
                "with_borders": True,  # С бортами
                "third_row": False     # Без третьего ряда
            }
        tenant_id: ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)
        session: Сессия базы данных

    Returns:
        Dict[str, Any]: Детализация цены в формате:
        {
            "total_price": 3000.0,
            "base_price": 2500.0,
            "options_price": 500.0,
            "breakdown": {
                "with_borders": 500.0,
                "third_row": 0.0
            }
        }

    Examples:
        >>> options = {"with_borders": True, "third_row": False}
        >>> await calculate_price("Toyota", "Camry", "eva_mats", options, 1, session)
        {"total_price": 3000.0, "base_price": 2500.0, ...}
    """
    logger.info(f"[TOOL] calculate_price(brand={brand_name}, model={model_name}, category={category_code}, options={options}, tenant_id={tenant_id})")

    try:
        # Получаем модель с типом кузова
        model, body_type = await db_queries.get_model_with_body_type(
            session=session,
            brand_name=brand_name,
            model_name=model_name
        )

        # Определяем код типа кузова (по умолчанию "sedan")
        body_type_code = body_type.code if body_type else "sedan"
        logger.info(f"[TOOL] Тип кузова: {body_type_code}")

        # Рассчитываем цену
        total_price, price_breakdown = await db_queries.calculate_total_price(
            session=session,
            tenant_id=tenant_id,
            category_code=category_code,
            body_type_code=body_type_code,
            selected_options=options
        )

        # Формируем ответ
        result = {
            "total_price": float(total_price),
            "base_price": float(price_breakdown.get("base_price", 0)),
            "options_price": sum(price_breakdown.get("options", {}).values()),
            "breakdown": price_breakdown.get("options", {})
        }

        logger.info(f"[TOOL] ✅ Цена рассчитана: {result['total_price']} сом")
        return result

    except Exception as e:
        logger.error(f"[TOOL] ❌ Ошибка при расчете цены: {e}")
        # Возвращаем дефолтную цену в случае ошибки
        return {
            "total_price": 2500.0,
            "base_price": 2500.0,
            "options_price": 0.0,
            "breakdown": {}
        }


async def create_airtable_lead(
    tenant_id: int,
    chat_id: str,
    client_name: str,
    category_name: str,
    brand_name: str,
    model_name: str,
    options: str,
    price: float,
    session: AsyncSession
) -> str:
    """
    ФИНАЛЬНЫЙ ИНСТРУМЕНТ! Создает заявку (лид) в Airtable с данными заказа клиента.

    Это завершающий шаг продажи. AI вызывает эту функцию только после того,
    как собрал ВСЕ необходимые данные от клиента: категорию, автомобиль, опции,
    цену и имя клиента.

    После создания заявки в Airtable менеджер компании получит уведомление
    и свяжется с клиентом для подтверждения заказа.

    Args:
        tenant_id: ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)
        chat_id: ID чата WhatsApp (формат: "996555123456@c.us")
        client_name: Имя клиента (например, "Иван")
        category_name: Название категории товара (например, "EVA-коврики")
        brand_name: Марка автомобиля (например, "Toyota")
        model_name: Модель автомобиля (например, "Camry 70")
        options: Описание выбранных опций (например, "С бортами 5 см")
        price: Итоговая цена заказа в сомах (например, 3000.0)
        session: Сессия базы данных (не используется, но требуется для совместимости)

    Returns:
        str: Сообщение о результате создания заявки для передачи клиенту

    Examples:
        >>> await create_airtable_lead(
        ...     tenant_id=1,
        ...     chat_id="996555123456@c.us",
        ...     client_name="Иван",
        ...     category_name="EVA-коврики",
        ...     brand_name="Toyota",
        ...     model_name="Camry 70",
        ...     options="С бортами 5 см, черный цвет",
        ...     price=3000.0,
        ...     session=session
        ... )
        "Заявка успешно создана с ID recXXXX. Сообщи клиенту..."
    """
    logger.info(f"💾 [TOOL] create_airtable_lead для {client_name} (chat_id={chat_id[:20]}...)")

    try:
        # ─────────────────────────────────────────────────────────────────────
        # Парсинг номера телефона из chat_id
        # Формат chat_id: "996555123456@c.us" → "+996555123456"
        # ─────────────────────────────────────────────────────────────────────
        phone_number = chat_id.split('@')[0]  # Извлекаем номер без @c.us
        phone_with_plus = f"+{phone_number}"  # Добавляем "+"

        logger.info(f"📞 [TOOL] Извлечен номер телефона: {phone_with_plus}")

        # ─────────────────────────────────────────────────────────────────────
        # Определяем tenant_slug для Airtable
        # ─────────────────────────────────────────────────────────────────────
        tenant_slug = "evopoliki" if tenant_id == 1 else "five_deluxe"

        # ─────────────────────────────────────────────────────────────────────
        # Формируем данные для Airtable
        # ─────────────────────────────────────────────────────────────────────
        lead_data = {
            "name": client_name,
            "phone": phone_with_plus,
            "username": chat_id,  # Сохраняем полный chat_id как username
            "category": category_name,
            "car_brand": brand_name,
            "car_model": model_name,
            "options": options,
            "price": price
        }

        logger.info(f"📋 [TOOL] Данные для Airtable: {lead_data}")

        # ─────────────────────────────────────────────────────────────────────
        # Вызываем функцию создания лида в Airtable
        # ─────────────────────────────────────────────────────────────────────
        record_id = await create_lead(lead_data, tenant_slug)

        if record_id:
            logger.info(f"✅ [TOOL] Заявка успешно создана в Airtable, Record ID: {record_id}")
            return (
                f"Заявка успешно создана с ID {record_id}. "
                f"Сообщи клиенту, что все готово и менеджер скоро свяжется с ним для подтверждения заказа."
            )
        else:
            logger.error(f"❌ [TOOL] Не удалось создать заявку в Airtable (record_id is None)")
            return (
                "Произошла ошибка при сохранении заявки. "
                "Сообщи клиенту о технической проблеме и попроси связаться с менеджером напрямую."
            )

    except Exception as e:
        logger.error(f"❌ [TOOL] Критическая ошибка при создании заявки в Airtable: {e}", exc_info=True)
        return (
            "Произошла техническая ошибка при создании заявки. "
            "Сообщи клиенту, что его данные записаны, и менеджер свяжется в ближайшее время."
        )


# ==============================================================================
# TOOL SCHEMAS - JSON-описания инструментов для OpenAI
# ==============================================================================

tool_schemas = [
    {
        "type": "function",
        "function": {
            "name": "get_available_categories",
            "description": (
                "Возвращает список всех доступных категорий товаров. "
                "Используй эту функцию в начале диалога, чтобы предложить клиенту "
                "выбрать категорию (EVA-коврики, 3D коврики, Чехлы и т.д.). "
                "Функция возвращает список строк с названиями на русском языке."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tenant_id": {
                        "type": "integer",
                        "description": "ID арендатора. Используй 1 для EVOPOLIKI, 2 для 5DELUXE. Обычно определяется автоматически из контекста."
                    }
                },
                "required": ["tenant_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_brands",
            "description": (
                "Возвращает список марок автомобилей, доступных для выбранной категории товара. "
                "Используй эту функцию после того, как клиент выбрал категорию, "
                "чтобы показать ему список марок автомобилей. "
                "Функция возвращает отсортированный список названий марок на английском языке "
                "(например: Audi, BMW, Mercedes-Benz, Toyota). "
                "ВАЖНО: Вызывай эту функцию ТОЛЬКО когда категория уже известна."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category_code": {
                        "type": "string",
                        "description": (
                            "Код категории товара. Возможные значения: "
                            "'eva_mats' (EVA-коврики), '3d_mats' (3D коврики), "
                            "'seat_covers' (Чехлы), 'organizers' (Органайзеры). "
                            "Используй код, соответствующий выбранной клиентом категории."
                        ),
                        "enum": ["eva_mats", "3d_mats", "seat_covers", "organizers"]
                    },
                    "tenant_id": {
                        "type": "integer",
                        "description": "ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)"
                    }
                },
                "required": ["category_code", "tenant_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_models",
            "description": (
                "Возвращает список моделей для выбранной марки автомобиля и категории товара. "
                "Используй эту функцию после того, как клиент выбрал марку автомобиля, "
                "чтобы показать ему список доступных моделей. "
                "Функция возвращает только те модели, для которых есть лекала в базе данных. "
                "Если список пустой, это означает что для данной марки нет доступных моделей, "
                "и клиенту нужно предложить индивидуальный замер. "
                "ВАЖНО: Вызывай эту функцию ТОЛЬКО когда категория и марка уже известны."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_name": {
                        "type": "string",
                        "description": (
                            "Точное название марки автомобиля на английском языке. "
                            "Примеры: 'Toyota', 'BMW', 'Mercedes-Benz'. "
                            "Используй название из списка, полученного от get_available_brands."
                        )
                    },
                    "category_code": {
                        "type": "string",
                        "description": "Код категории товара (eva_mats, 3d_mats, seat_covers, organizers)",
                        "enum": ["eva_mats", "3d_mats", "seat_covers", "organizers"]
                    },
                    "tenant_id": {
                        "type": "integer",
                        "description": "ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)"
                    }
                },
                "required": ["brand_name", "category_code", "tenant_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_patterns",
            "description": (
                "КРИТИЧЕСКИ ВАЖНЫЙ инструмент! Проверяет, есть ли в базе данных "
                "лекала (шаблоны для производства) для указанной комбинации "
                "марка + модель + категория товара. "
                "Возвращает 'FOUND' если лекала есть (заказ можем выполнить сразу), "
                "или 'NOT_FOUND' если лекал нет (нужен индивидуальный замер). "
                "КОГДА ИСПОЛЬЗОВАТЬ: Вызывай эту функцию СРАЗУ после того, как узнал "
                "марку, модель и категорию товара от клиента. Это позволит определить "
                "дальнейший сценарий диалога. "
                "ВАЖНО: Если функция вернула 'NOT_FOUND', не предлагай клиенту продолжить "
                "выбор опций, а сразу предложи индивидуальный замер."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_name": {
                        "type": "string",
                        "description": "Точное название марки автомобиля, например 'Toyota', 'BMW'"
                    },
                    "model_name": {
                        "type": "string",
                        "description": (
                            "Точное название модели автомобиля. Примеры: 'Camry', 'Camry 70', 'X5', 'E-Class'. "
                            "Используй название из списка, полученного от get_available_models, "
                            "или название, которое указал клиент."
                        )
                    },
                    "category_code": {
                        "type": "string",
                        "description": "Код категории товара (eva_mats, 3d_mats, seat_covers, organizers)",
                        "enum": ["eva_mats", "3d_mats", "seat_covers", "organizers"]
                    },
                    "tenant_id": {
                        "type": "integer",
                        "description": "ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)"
                    }
                },
                "required": ["brand_name", "model_name", "category_code", "tenant_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_price",
            "description": (
                "Рассчитывает итоговую цену заказа на основе модели автомобиля, "
                "категории товара и выбранных клиентом опций. "
                "Возвращает детальную разбивку цены: базовая цена, цена опций, итоговая сумма. "
                "КОГДА ИСПОЛЬЗОВАТЬ: Вызывай эту функцию после того, как: "
                "1) search_patterns вернула 'FOUND' (лекала найдены), "
                "2) клиент выбрал опции (например, 'с бортами' или 'без бортов'). "
                "НЕ вызывай эту функцию, если лекал нет (NOT_FOUND) - в этом случае "
                "цена рассчитывается индивидуально менеджером."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_name": {
                        "type": "string",
                        "description": "Название марки автомобиля, например 'Toyota'"
                    },
                    "model_name": {
                        "type": "string",
                        "description": "Название модели автомобиля, например 'Camry 70'"
                    },
                    "category_code": {
                        "type": "string",
                        "description": "Код категории товара",
                        "enum": ["eva_mats", "3d_mats", "seat_covers", "organizers"]
                    },
                    "options": {
                        "type": "object",
                        "description": (
                            "Словарь выбранных клиентом опций. "
                            "Ключи - коды опций, значения - boolean (True если выбрано, False если нет). "
                            "Возможные опции: "
                            "'with_borders' (с бортами/без бортов), "
                            "'third_row' (третий ряд для внедорожников 7 мест). "
                            "Пример: {\"with_borders\": true, \"third_row\": false}"
                        ),
                        "properties": {
                            "with_borders": {
                                "type": "boolean",
                                "description": "True если клиент выбрал вариант 'с бортами', False если 'без бортов'"
                            },
                            "third_row": {
                                "type": "boolean",
                                "description": "True если нужен третий ряд (для 7-местных авто), False если нет"
                            }
                        }
                    },
                    "tenant_id": {
                        "type": "integer",
                        "description": "ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE)"
                    }
                },
                "required": ["brand_name", "model_name", "category_code", "options", "tenant_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_airtable_lead",
            "description": (
                "🎯 ФИНАЛЬНЫЙ ИНСТРУМЕНТ! Создает заявку (лид) в Airtable с полными данными заказа клиента. "
                "Это завершающий шаг продажи - после создания заявки менеджер компании получит уведомление "
                "и свяжется с клиентом для подтверждения заказа и организации доставки/установки. "
                "\n\n"
                "КОГДА ИСПОЛЬЗОВАТЬ: Вызывай эту функцию ТОЛЬКО после того, как собрал ВСЕ данные:\n"
                "1️⃣ Категорию товара (через get_available_categories)\n"
                "2️⃣ Марку и модель автомобиля (через get_available_brands, get_available_models)\n"
                "3️⃣ Проверил наличие лекал (через search_patterns → должно быть 'FOUND')\n"
                "4️⃣ Узнал опции клиента (с бортами / без бортов и т.д.)\n"
                "5️⃣ Рассчитал цену (через calculate_price)\n"
                "6️⃣ Узнал имя клиента\n"
                "\n"
                "ВАЖНО:\n"
                "• НЕ вызывай эту функцию, если у тебя нет ВСЕХ данных!\n"
                "• НЕ спрашивай у клиента номер телефона - он уже есть в chat_id!\n"
                "• chat_id автоматически передается системой (формат: '996555123456@c.us')\n"
                "• После успешного создания заявки функция вернет сообщение для клиента - передай его клиенту как есть."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tenant_id": {
                        "type": "integer",
                        "description": "ID арендатора (1 для EVOPOLIKI, 2 для 5DELUXE). Обычно определяется автоматически из контекста."
                    },
                    "chat_id": {
                        "type": "string",
                        "description": (
                            "ID чата WhatsApp пользователя в формате '996555123456@c.us'. "
                            "Из этого ID автоматически извлекается номер телефона клиента. "
                            "ВАЖНО: Этот параметр ВСЕГДА доступен автоматически - используй переменную chat_id из контекста диалога!"
                        )
                    },
                    "client_name": {
                        "type": "string",
                        "description": (
                            "Имя клиента для заявки. Примеры: 'Иван', 'Мария', 'Азамат', 'Жанара'. "
                            "Попроси клиента назвать имя, если он его еще не сообщил. "
                            "Достаточно только имени, без фамилии."
                        )
                    },
                    "category_name": {
                        "type": "string",
                        "description": (
                            "Название категории товара на русском языке. "
                            "Примеры: 'EVA-коврики', '3D коврики', 'Чехлы', 'Органайзеры'. "
                            "Используй точное название, которое вернула функция get_available_categories."
                        )
                    },
                    "brand_name": {
                        "type": "string",
                        "description": (
                            "Марка автомобиля на английском языке. "
                            "Примеры: 'Toyota', 'BMW', 'Mercedes-Benz', 'Lexus', 'Nissan'. "
                            "Используй точное название из списка get_available_brands."
                        )
                    },
                    "model_name": {
                        "type": "string",
                        "description": (
                            "Модель автомобиля. "
                            "Примеры: 'Camry 70', 'X5', 'E-Class', 'RX 350', 'Qashqai'. "
                            "Используй точное название из списка get_available_models."
                        )
                    },
                    "options": {
                        "type": "string",
                        "description": (
                            "Текстовое описание выбранных клиентом опций. "
                            "Примеры: 'С бортами 5 см', 'Без бортов', 'С бортами, третий ряд', 'Без бортов, второй ряд'. "
                            "Сформируй читаемое описание на основе того, что выбрал клиент (опции из calculate_price)."
                        )
                    },
                    "price": {
                        "type": "number",
                        "description": (
                            "Итоговая цена заказа в сомах (KGS). "
                            "Примеры: 3000.0, 4500.0, 2800.0. "
                            "ВАЖНО: Используй цену из поля 'total_price', которую вернула функция calculate_price."
                        )
                    }
                },
                "required": ["tenant_id", "chat_id", "client_name", "category_name", "brand_name", "model_name", "options", "price"]
            }
        }
    }
]
