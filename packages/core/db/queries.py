"""
Запросы к базе данных.
"""

import sys
from pathlib import Path
from typing import Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем модели через относительные импорты
from ..database.models import Tenant, Brand, ProductCategory

logger = logging.getLogger(__name__)

# ==============================================================================
# POSTGRESQL DATABASE QUERIES - PRIMARY DATA SOURCE
# ==============================================================================


async def get_unique_brands_from_db(tenant_id: int, session: AsyncSession) -> list[str]:
    """
    Получает ВСЕ марки из PostgreSQL, отсортированные по имени.

    ВАЖНО: Возвращает все марки из таблицы brands без фильтрации по наличию лекал.
    Это гарантирует, что пользователь увидит полный список марок в пагинации.

    Args:
        tenant_id: ID tenant (используется для логирования, не фильтрует результаты)
        session: Сессия БД

    Returns:
        list[str]: Отсортированный список всех марок из таблицы brands
    """
    logger.info(f"[DB] Загрузка ВСЕХ марок из базы данных (tenant_id={tenant_id} для контекста)")

    # ПРОСТОЙ запрос без JOIN: SELECT name FROM brands ORDER BY name
    stmt = select(Brand.name).order_by(Brand.name)

    result = await session.execute(stmt)
    brands = [row[0] for row in result.all()]

    logger.info(f"[DB] ✅ Загружено {len(brands)} марок из таблицы brands")

    return brands


async def get_models_for_brand_from_db(
    brand_name: str,
    tenant_id: int,
    session: AsyncSession
) -> list[str]:
    """
    Возвращает список уникальных моделей для указанной марки и tenant из PostgreSQL.
    Возвращает только модели, для которых есть доступные лекала.

    Args:
        brand_name: Название марки (например, "Toyota")
        tenant_id: ID tenant
        session: Сессия БД

    Returns:
        list[str]: Список уникальных названий моделей
    """
    from core.database.models import Pattern, Model

    logger.info(f"[DB] Загрузка моделей для марки '{brand_name}', tenant_id={tenant_id}")

    # Сначала находим бренд
    brand_stmt = select(Brand).where(Brand.name.ilike(brand_name))
    brand_result = await session.execute(brand_stmt)
    brand = brand_result.scalar_one_or_none()

    if not brand:
        logger.warning(f"[DB] ❌ Марка '{brand_name}' не найдена")
        return []

    # Запрос: SELECT DISTINCT models.name FROM models
    # JOIN patterns ON models.id = patterns.model_id
    # WHERE models.brand_id = ? AND patterns.tenant_id = ? AND patterns.available = true
    # ORDER BY models.name
    stmt = (
        select(Model.name)
        .join(Pattern, Model.id == Pattern.model_id)
        .where(
            Model.brand_id == brand.id,
            Pattern.tenant_id == tenant_id,
            Pattern.available == True
        )
        .distinct()
        .order_by(Model.name)
    )

    result = await session.execute(stmt)
    models = [row[0] for row in result.all()]

    logger.info(f"[DB] ✅ Найдено {len(models)} моделей для '{brand_name}'")

    return models


async def search_patterns_in_db(
    brand_name: str,
    model_name: str,
    tenant_id: int,
    session: AsyncSession,
    category_code: str = "eva_mats"
) -> list:
    """
    Поиск лекал в PostgreSQL по марке, модели и категории.
    Это обертка над существующей функцией search_patterns() для совместимости.

    Args:
        brand_name: Название марки
        model_name: Название модели
        tenant_id: ID tenant
        session: Сессия БД
        category_code: Код категории продукта (по умолчанию "eva_mats")

    Returns:
        list: Список найденных лекал (Pattern objects)
    """
    logger.info(f"[DB] Поиск лекал для {brand_name} {model_name}, tenant_id={tenant_id}")

    # Используем существующую функцию search_patterns
    patterns = await search_patterns(
        session=session,
        brand_name=brand_name,
        model_name=model_name,
        tenant_id=tenant_id,
        category_code=category_code
    )

    logger.info(f"[DB] ✅ Найдено {len(patterns)} лекал")

    return patterns


# ==============================================================================
# LEGACY DATABASE QUERIES (KEEP FOR NOW)
# ==============================================================================


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Optional[Tenant]:
    """
    Получает tenant по slug.

    Args:
        session: Сессия БД
        slug: Slug tenant (например, "evopoliki")

    Returns:
        Tenant или None
    """
    stmt = select(Tenant).where(
        Tenant.slug == slug,
        Tenant.active == True
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_brands(session: AsyncSession) -> list[Brand]:
    """
    Получает список всех брендов.

    Args:
        session: Сессия БД

    Returns:
        Список брендов
    """
    stmt = select(Brand).order_by(Brand.name)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_product_categories(session: AsyncSession) -> list[ProductCategory]:
    """
    Получает список всех категорий продуктов.

    Args:
        session: Сессия БД

    Returns:
        Список категорий
    """
    stmt = select(ProductCategory).order_by(ProductCategory.name_ru)
    result = await session.execute(stmt)
    return result.scalars().all()


async def search_patterns(
    session: AsyncSession,
    brand_name: str,
    model_name: str,
    tenant_id: int,
    category_code: str = "eva_mats",
    return_debug_info: bool = False
):
    """
    Ищет лекала для конкретного бренда, модели и категории.

    Args:
        session: Сессия БД
        brand_name: Название бренда (например, "Toyota")
        model_name: Название модели (например, "Camry")
        tenant_id: ID tenant
        category_code: Код категории продукта
        return_debug_info: Если True, возвращает tuple (patterns, debug_info)

    Returns:
        Список найденных лекал (Pattern objects)
        Если return_debug_info=True: tuple (patterns, debug_info dict)
    """
    from core.database.models import Pattern, Model, Brand, ProductCategory
    import logging

    logger = logging.getLogger(__name__)

    # Для отладки собираем информацию
    debug_info = {
        'brand_query': '',
        'model_query': '',
        'category_query': '',
        'patterns_query': '',
        'result_count': 0
    }

    # Ищем бренд (нечувствительно к регистру)
    brand_stmt = select(Brand).where(
        Brand.name.ilike(f"%{brand_name}%")
    )

    # Захватываем SQL запрос для отладки
    if return_debug_info:
        debug_info['brand_query'] = str(brand_stmt.compile(compile_kwargs={"literal_binds": True}))

    # Логируем поиск для диагностики
    logger.info(f"[SEARCH] Ищу бренд '{brand_name}' (tenant_id={tenant_id})")
    
    brand_result = await session.execute(brand_stmt)
    brand = brand_result.scalar_one_or_none()

    if not brand:
        logger.warning(f"[SEARCH] ❌ Бренд '{brand_name}' не найден (tenant_id={tenant_id})")
        
        # Проверяем есть ли вообще бренды в БД
        count_stmt = select(func.count(Brand.id))
        count_result = await session.execute(count_stmt)
        total_brands = count_result.scalar()
        logger.warning(f"[SEARCH] В БД всего {total_brands} брендов")
        
        if return_debug_info:
            debug_info['result_count'] = 0
            debug_info['total_brands_in_db'] = total_brands
            return [], debug_info
        return []

    logger.info(f"[SEARCH] ✅ Найден бренд: {brand.name} (id={brand.id})")

    # Ищем модель для этого бренда
    # Стратегия: сначала точное совпадение, потом частичное
    model = None

    # Шаг 1: Точное совпадение (case-insensitive)
    # Ищем как в латинице (name), так и в кириллице (name_ru)
    from sqlalchemy import or_

    exact_model_stmt = select(Model).where(
        Model.brand_id == brand.id,
        or_(
            Model.name.ilike(model_name),
            Model.name_ru.ilike(model_name)
        )
    )

    # Захватываем SQL запрос для отладки
    if return_debug_info:
        debug_info['model_query'] = str(exact_model_stmt.compile(compile_kwargs={"literal_binds": True}))

    exact_model_result = await session.execute(exact_model_stmt)
    exact_models = exact_model_result.scalars().all()

    if exact_models:
        # Берем первую модель (даже если есть дубликаты)
        model = exact_models[0]
        if len(exact_models) > 1:
            logger.warning(f"Найдено {len(exact_models)} дубликатов модели '{model_name}', выбрана первая (id={model.id})")
        else:
            logger.info(f"Найдена модель (точное совпадение): {model.name} (id={model.id})")

    # Шаг 2: Если точное совпадение не найдено, ищем частичное
    # Ищем как в латинице (name), так и в кириллице (name_ru)
    if not model:
        partial_model_stmt = select(Model).where(
            Model.brand_id == brand.id,
            or_(
                Model.name.ilike(f"%{model_name}%"),
                Model.name_ru.ilike(f"%{model_name}%")
            )
        )
        partial_model_result = await session.execute(partial_model_stmt)
        models = partial_model_result.scalars().all()

        if models:
            # Если найдено несколько моделей, выбираем самую короткую
            # (это обычно базовая модель без префиксов типа "версо", "версу")
            model = min(models, key=lambda m: len(m.name))
            logger.info(f"Найдено {len(models)} моделей, выбрана '{model.name}' (id={model.id})")
        else:
            logger.info(f"Модель '{model_name}' не найдена для бренда '{brand.name}'")
            if return_debug_info:
                debug_info['result_count'] = 0
                return [], debug_info
            return []
    else:
        logger.info(f"Найдена модель (точное совпадение): {model.name} (id={model.id})")

    # Ищем категорию продукта
    category_stmt = select(ProductCategory).where(
        ProductCategory.code == category_code
    )

    # Захватываем SQL запрос для отладки
    if return_debug_info:
        debug_info['category_query'] = str(category_stmt.compile(compile_kwargs={"literal_binds": True}))

    category_result = await session.execute(category_stmt)
    category = category_result.scalar_one_or_none()

    if not category:
        logger.info(f"Категория '{category_code}' не найдена")
        if return_debug_info:
            debug_info['result_count'] = 0
            return [], debug_info
        return []

    logger.info(f"[SEARCH] ✅ Найдена категория: {category.name_ru} (id={category.id})")

    # Ищем лекала
    patterns_stmt = select(Pattern).where(
        Pattern.tenant_id == tenant_id,
        Pattern.model_id == model.id,
        Pattern.category_id == category.id,
        Pattern.available == True
    )

    # Захватываем SQL запрос для отладки
    if return_debug_info:
        debug_info['patterns_query'] = str(patterns_stmt.compile(compile_kwargs={"literal_binds": True}))

    patterns_result = await session.execute(patterns_stmt)
    patterns = patterns_result.scalars().all()

    logger.info(f"[SEARCH] ✅ Найдено {len(patterns)} лекал для tenant_id={tenant_id}, модели '{model.name}'")

    # Возвращаем результат с debug info если нужно
    if return_debug_info:
        debug_info['result_count'] = len(patterns)
        return patterns, debug_info

    return patterns


async def get_brand_by_name(session: AsyncSession, brand_name: str):
    """
    Получает бренд по имени (нечувствительно к регистру).

    Args:
        session: Сессия БД
        brand_name: Название бренда

    Returns:
        Brand или None
    """
    stmt = select(Brand).where(Brand.name.ilike(f"%{brand_name}%"))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_models_by_brand(session: AsyncSession, brand_id: int) -> list:
    """
    Получает список моделей для бренда.

    Args:
        session: Сессия БД
        brand_id: ID бренда

    Returns:
        Список моделей
    """
    from core.database.models import Model

    stmt = select(Model).where(Model.brand_id == brand_id).order_by(Model.name)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_base_price(
    session: AsyncSession,
    tenant_id: int,
    category_code: str,
    body_type_code: Optional[str] = None
) -> Optional[float]:
    """
    Получает базовую цену для категории и типа кузова.

    Args:
        session: Сессия БД
        tenant_id: ID tenant
        category_code: Код категории (например, "eva_mats")
        body_type_code: Код типа кузова (например, "sedan", "suv")

    Returns:
        Базовая цена в виде float или None
    """
    from core.database.models import Price, ProductCategory, BodyType

    # Получаем категорию
    category_stmt = select(ProductCategory).where(ProductCategory.code == category_code)
    category = (await session.execute(category_stmt)).scalar_one_or_none()

    if not category:
        return None

    # Получаем тип кузова (если указан)
    body_type_id = None
    if body_type_code:
        body_type_stmt = select(BodyType).where(BodyType.code == body_type_code)
        body_type = (await session.execute(body_type_stmt)).scalar_one_or_none()
        if body_type:
            body_type_id = body_type.id

    # Ищем цену
    price_stmt = select(Price).where(
        Price.tenant_id == tenant_id,
        Price.category_id == category.id,
        Price.option_id.is_(None)  # Базовая цена (не опция)
    )

    if body_type_id:
        price_stmt = price_stmt.where(Price.body_type_id == body_type_id)

    price = (await session.execute(price_stmt)).scalar_one_or_none()

    if price:
        return float(price.base_price)

    return None


async def get_option_price(
    session: AsyncSession,
    tenant_id: int,
    option_code: str,
    body_type_code: Optional[str] = None
) -> Optional[float]:
    """
    Получает цену опции.

    Args:
        session: Сессия БД
        tenant_id: ID tenant
        option_code: Код опции (например, "with_borders", "third_row")
        body_type_code: Код типа кузова (если цена зависит от типа кузова)

    Returns:
        Цена опции в виде float или None
    """
    from core.database.models import Price, ProductOption, BodyType

    # Получаем опцию
    option_stmt = select(ProductOption).where(ProductOption.code == option_code)
    option = (await session.execute(option_stmt)).scalar_one_or_none()

    if not option:
        return None

    # Получаем тип кузова (если указан)
    body_type_id = None
    if body_type_code:
        body_type_stmt = select(BodyType).where(BodyType.code == body_type_code)
        body_type = (await session.execute(body_type_stmt)).scalar_one_or_none()
        if body_type:
            body_type_id = body_type.id

    # Ищем цену
    price_stmt = select(Price).where(
        Price.tenant_id == tenant_id,
        Price.option_id == option.id,
        Price.category_id.is_(None)  # Это цена опции (не базовая)
    )

    if body_type_id:
        price_stmt = price_stmt.where(Price.body_type_id == body_type_id)
    else:
        # Если body_type не указан, ищем цену применимую ко всем типам
        price_stmt = price_stmt.where(Price.body_type_id.is_(None))

    price = (await session.execute(price_stmt)).scalar_one_or_none()

    if price:
        return float(price.base_price)

    return None


async def calculate_total_price(
    session: AsyncSession,
    tenant_id: int,
    category_code: str,
    body_type_code: str,
    selected_options: dict
) -> tuple[float, dict]:
    """
    Рассчитывает итоговую цену с учетом всех опций.

    Args:
        session: Сессия БД
        tenant_id: ID tenant
        category_code: Код категории продукта
        body_type_code: Код типа кузова
        selected_options: Словарь выбранных опций, например:
            {
                'with_borders': True,
                'third_row': False
            }

    Returns:
        Кортеж (total_price, price_breakdown), где:
        - total_price: итоговая цена
        - price_breakdown: детализация цены
            {
                'base_price': 2500.0,
                'options': {
                    'with_borders': 500.0,
                    'third_row': 0.0
                },
                'total': 3000.0
            }
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"💰 [CALC_PRICE] === НАЧАЛО РАСЧЁТА ЦЕНЫ ===")
    logger.info(f"💰 [CALC_PRICE] Входные параметры:")
    logger.info(f"💰 [CALC_PRICE]   - tenant_id: {tenant_id}")
    logger.info(f"💰 [CALC_PRICE]   - category_code: '{category_code}'")
    logger.info(f"💰 [CALC_PRICE]   - body_type_code: '{body_type_code}'")
    logger.info(f"💰 [CALC_PRICE]   - selected_options: {selected_options}")

    # Получаем базовую цену
    base_price = await get_base_price(session, tenant_id, category_code, body_type_code)
    logger.info(f"💰 [CALC_PRICE] get_base_price({tenant_id}, '{category_code}', '{body_type_code}') = {base_price}")

    if base_price is None:
        # Если нет цены для конкретного типа кузова, пробуем получить общую цену
        logger.warning(f"⚠️ [CALC_PRICE] Цена не найдена для body_type='{body_type_code}', пробую общую цену")
        base_price = await get_base_price(session, tenant_id, category_code, None)
        logger.info(f"💰 [CALC_PRICE] get_base_price({tenant_id}, '{category_code}', None) = {base_price}")

    if base_price is None:
        # Если цены нет в БД, возвращаем дефолтную
        logger.error(f"❌ [CALC_PRICE] КРИТИЧЕСКАЯ ОШИБКА: Цена НЕ НАЙДЕНА в БД!")
        logger.error(f"❌ [CALC_PRICE] tenant_id={tenant_id}, category='{category_code}'")
        logger.error(f"❌ [CALC_PRICE] Использую FALLBACK значение: 2500.0 сом")
        base_price = 2500.0

    # Рассчитываем цены опций
    options_prices = {}
    total_options_price = 0.0

    for option_code, is_selected in selected_options.items():
        if is_selected:
            option_price = await get_option_price(session, tenant_id, option_code, body_type_code)

            if option_price is None:
                # Если нет цены для конкретного типа кузова, берем общую
                option_price = await get_option_price(session, tenant_id, option_code, None)

            if option_price:
                options_prices[option_code] = option_price
                total_options_price += option_price
            else:
                options_prices[option_code] = 0.0
        else:
            options_prices[option_code] = 0.0

    total_price = base_price + total_options_price

    price_breakdown = {
        'base_price': base_price,
        'options': options_prices,
        'total': total_price
    }

    logger.info(f"💰 [CALC_PRICE] === РЕЗУЛЬТАТ РАСЧЁТА ===")
    logger.info(f"💰 [CALC_PRICE] Базовая цена: {base_price} сом")
    logger.info(f"💰 [CALC_PRICE] Цены опций: {options_prices}")
    logger.info(f"💰 [CALC_PRICE] Сумма опций: {total_options_price} сом")
    logger.info(f"💰 [CALC_PRICE] ИТОГО: {total_price} сом")
    logger.info(f"💰 [CALC_PRICE] === КОНЕЦ РАСЧЁТА ===")

    return total_price, price_breakdown


async def get_model_with_body_type(
    session: AsyncSession,
    brand_name: str,
    model_name: str
):
    """
    Получает модель автомобиля вместе с типом кузова.

    Args:
        session: Сессия БД
        brand_name: Название бренда
        model_name: Название модели

    Returns:
        Tuple (Model, BodyType) или (None, None)
    """
    from core.database.models import Model, Brand, BodyType

    # Ищем бренд
    brand_stmt = select(Brand).where(Brand.name.ilike(f"%{brand_name}%"))
    brand = (await session.execute(brand_stmt)).scalar_one_or_none()

    if not brand:
        return None, None

    # Ищем модель (как в латинице, так и в кириллице)
    from sqlalchemy import or_

    model_stmt = select(Model).where(
        Model.brand_id == brand.id,
        or_(
            Model.name.ilike(f"%{model_name}%"),
            Model.name_ru.ilike(f"%{model_name}%")
        )
    )
    model = (await session.execute(model_stmt)).scalar_one_or_none()

    if not model:
        return None, None

    # Получаем тип кузова
    body_type = None
    if model.body_type_id:
        body_type_stmt = select(BodyType).where(BodyType.id == model.body_type_id)
        body_type = (await session.execute(body_type_stmt)).scalar_one_or_none()

    return model, body_type


def normalize_for_fuzzy_search(text: str) -> str:
    """
    Нормализует текст для fuzzy поиска.

    Преобразования:
    1. Замена названий букв на сами буквы ("эс класс" → "s class")
    2. Транслитерация кириллицы → латиница
    3. Нижний регистр
    4. Удаление дефисов, подчеркиваний → пробелы
    5. Удаление лишних пробелов

    Примеры:
    - "Эс класс" → "s class"
    - "S-Class" → "s class"
    - "C-Class" → "c class"
    - "Таёта Камри" → "toyota camry"

    Args:
        text: Исходный текст

    Returns:
        Нормализованный текст
    """
    # Приводим к нижнему регистру
    text = text.lower()

    # Словарь названий букв → сами буквы
    # Обрабатываем до транслитерации!
    letter_names = {
        ' эс ': ' s ',
        ' икс ': ' x ',
        ' зет ': ' z ',
        ' бэ ': ' b ',
        ' цэ ': ' c ',
        ' дэ ': ' d ',
        ' джи ': ' g ',
        ' эм ': ' m ',
        ' эн ': ' n ',
        ' о ': ' o ',
        ' пэ ': ' p ',
        ' ар ': ' r ',
        ' тэ ': ' t ',
        ' ю ': ' u ',
        ' вэ ': ' v ',
    }

    # Добавляем пробелы по краям для корректного поиска
    text = ' ' + text + ' '

    # Заменяем названия букв
    for letter_name, letter in letter_names.items():
        text = text.replace(letter_name, letter)

    # Убираем добавленные пробелы
    text = text.strip()

    # Таблица транслитерации кириллицы
    cyrillic_to_latin = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
        'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
        'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
        'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
        'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    # Транслитерируем кириллицу
    result = []
    for char in text:
        if char in cyrillic_to_latin:
            result.append(cyrillic_to_latin[char])
        else:
            result.append(char)

    text = ''.join(result)

    # Удаляем дефисы и подчеркивания → пробелы
    text = text.replace('-', ' ').replace('_', ' ')

    # Удаляем лишние пробелы
    text = ' '.join(text.split())

    return text


async def fuzzy_search_model(
    session: AsyncSession,
    brand_id: int,
    model_name: str,
    threshold: float = 85.0
) -> tuple[Optional[str], float]:
    """
    Выполняет нечеткий поиск модели с использованием rapidfuzz.

    УЛУЧШЕНИЯ (v2):
    - Замена названий букв ("эс класс" → "s class")
    - Транслитерация кириллицы → латиница перед сравнением
    - Нормализация строк (удаление дефисов, нижний регистр)
    - Порог схожести 85% (оптимально для fuzzy match)

    Примеры работы:
    - "Эс класс" НЕ совпадет с "C-Class" (разные буквы)
    - "Эс класс" НАЙДЕТ "S-Class" (после транслитерации)
    - "Таёта Камри" НАЙДЕТ "Toyota Camry"

    Args:
        session: Сессия БД
        brand_id: ID бренда
        model_name: Введенное название модели
        threshold: Минимальный порог схожести (0-100), по умолчанию 90%

    Returns:
        Tuple (найденная_модель, степень_схожести) или (None, 0)
    """
    from rapidfuzz import fuzz, process
    from core.database.models import Model

    # Получаем все модели для данного бренда
    stmt = select(Model).where(Model.brand_id == brand_id)
    result = await session.execute(stmt)
    models = result.scalars().all()

    if not models:
        return None, 0.0

    # Нормализуем ввод пользователя
    normalized_input = normalize_for_fuzzy_search(model_name)
    logger.info(f"[FUZZY] Input: '{model_name}' → normalized: '{normalized_input}'")

    # Создаем словарь: normalized_name → original_name
    normalized_to_original = {}

    for model in models:
        # Латинское название
        if model.name:
            normalized = normalize_for_fuzzy_search(model.name)
            normalized_to_original[normalized] = model.name
            logger.debug(f"[FUZZY] DB model: '{model.name}' → '{normalized}'")

        # Кириллическое название (если есть)
        if model.name_ru:
            normalized = normalize_for_fuzzy_search(model.name_ru)
            normalized_to_original[normalized] = model.name_ru
            logger.debug(f"[FUZZY] DB model (ru): '{model.name_ru}' → '{normalized}'")

    # Используем rapidfuzz для поиска наиболее похожего названия
    # Сравниваем НОРМАЛИЗОВАННЫЕ строки
    # token_sort_ratio - сравнивает слова независимо от порядка,
    # лучше работает для "es klass" vs "s class"
    best_match = process.extractOne(
        normalized_input,
        list(normalized_to_original.keys()),
        scorer=fuzz.token_sort_ratio
    )

    if best_match and best_match[1] >= threshold:
        # Возвращаем ОРИГИНАЛЬНОЕ название из БД
        original_name = normalized_to_original[best_match[0]]
        logger.info(f"[FUZZY] ✅ Match found: '{original_name}' (similarity: {best_match[1]:.0f}%)")
        return original_name, best_match[1]

    if best_match:
        logger.info(f"[FUZZY] ❌ No match (best: {best_match[1]:.0f}% < threshold: {threshold}%)")

    return None, best_match[1] if best_match else 0.0
