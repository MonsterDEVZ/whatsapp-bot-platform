"""
Менеджер для работы с Airtable API.

Сохраняет заявки от клиентов в Airtable с поддержкой tenant-specific конфигураций.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def create_lead(lead_data: Dict[str, Any], tenant_slug: str = "evopoliki") -> Optional[str]:
    """
    Создает новую заявку (лид) в Airtable.

    Args:
        lead_data: Словарь с данными заявки:
            - name: Имя клиента (обязательно)
            - phone: Телефон клиента (обязательно)
            - username: Username из WhatsApp (опционально)
            - category: Название категории товара (опционально)
            - car_brand: Марка автомобиля (опционально)
            - car_model: Модель автомобиля (опционально)
            - options: Описание выбранных опций (опционально)
            - price: Итоговая цена (опционально)
        tenant_slug: Идентификатор тенанта (evopoliki, five_deluxe)

    Returns:
        str: ID созданной записи в Airtable, или None при ошибке

    Example:
        >>> lead_data = {
        ...     "name": "Иван Иванов",
        ...     "phone": "+996777123456",
        ...     "username": "ivan_ivanov",
        ...     "category": "EVA-коврики",
        ...     "car_brand": "Toyota",
        ...     "car_model": "Camry",
        ...     "options": "С бортами 5 см, Черный цвет",
        ...     "price": 2800
        ... }
        >>> record_id = await create_lead(lead_data, "evopoliki")
    """
    try:
        from pyairtable import Api

        # Получаем tenant-specific credentials из переменных окружения
        tenant_upper = tenant_slug.upper()
        api_token = os.getenv(f"{tenant_upper}_AIRTABLE_API_TOKEN")
        base_id = os.getenv(f"{tenant_upper}_AIRTABLE_BASE_ID")
        table_id = os.getenv(f"{tenant_upper}_AIRTABLE_TABLE_ID")

        # Fallback на общие credentials (для обратной совместимости)
        if not api_token:
            api_token = os.getenv("AIRTABLE_API_KEY")
        if not base_id:
            base_id = os.getenv("AIRTABLE_BASE_ID")
        if not table_id:
            # Для старой версии использовалось table_name, пробуем его
            table_id = os.getenv("AIRTABLE_TABLE_NAME")

        if not all([api_token, base_id, table_id]):
            logger.error(f"❌ [AIRTABLE] Отсутствуют credentials для {tenant_slug}")
            logger.error(f"   API Token: {'✅' if api_token else '❌'}")
            logger.error(f"   Base ID: {'✅' if base_id else '❌'}")
            logger.error(f"   Table ID: {'✅' if table_id else '❌'}")
            return None

        logger.info(f"🔄 [AIRTABLE] Попытка создать лид в Airtable для {tenant_slug}...")
        logger.info(f"🔄 [AIRTABLE] Base: {base_id}, Table: {table_id}")
        logger.info(f"🔄 [AIRTABLE] Данные: {lead_data}")

        # Инициализируем API Airtable
        api = Api(api_token)
        table = api.table(base_id, table_id)

        # Формируем данные для Airtable согласно НОВОЙ структуре полей
        airtable_data = {}

        # ОБЯЗАТЕЛЬНЫЕ ПОЛЯ (с дефолтными значениями)
        airtable_data["Статус"] = "Новая"
        airtable_data["Источник"] = "WhatsApp"
        airtable_data["Тип заявки"] = "Заказ товара"

        # КОНТАКТНЫЕ ДАННЫЕ
        if lead_data.get("name"):
            airtable_data["Имя клиента"] = lead_data["name"]

        if lead_data.get("phone"):
            airtable_data["Телефон клиента"] = lead_data["phone"]

        if lead_data.get("username"):
            airtable_data["Username"] = lead_data["username"]

        # ДАННЫЕ О ТОВАРЕ
        if lead_data.get("category"):
            airtable_data["Товар"] = lead_data["category"]

        # ДАННЫЕ ОБ АВТОМОБИЛЕ (объединяем марку и модель)
        car_brand = lead_data.get("car_brand", "")
        car_model = lead_data.get("car_model", "")

        if car_brand or car_model:
            car_full = f"{car_brand} {car_model}".strip()
            if car_full:
                airtable_data["Автомобиль"] = car_full

        # ОПЦИИ/ДЕТАЛИ
        if lead_data.get("options"):
            airtable_data["Детали / Опции"] = lead_data["options"]

        # ЦЕНА (только если больше 0)
        if lead_data.get("price") and lead_data["price"] > 0:
            airtable_data["Итоговая цена"] = lead_data["price"]

        logger.info(f"📤 [AIRTABLE] Отправка данных в Airtable: {airtable_data}")

        # Создаем запись в Airtable
        record = table.create(airtable_data)
        record_id = record["id"]

        logger.info("="*70)
        logger.info(f"✅ [AIRTABLE] Лид успешно создан в Airtable с ID: {record_id}")
        logger.info(f"✅ [AIRTABLE] Клиент: {lead_data.get('name')} ({lead_data.get('phone')})")
        logger.info(f"✅ [AIRTABLE] Товар: {airtable_data.get('Товар', 'Не указано')}")
        logger.info(f"✅ [AIRTABLE] Автомобиль: {airtable_data.get('Автомобиль', 'Не указано')}")
        if "Итоговая цена" in airtable_data:
            logger.info(f"✅ [AIRTABLE] Цена: {airtable_data['Итоговая цена']} сом")
        logger.info("="*70)

        return record_id

    except ImportError:
        logger.error("❌ [AIRTABLE] ОШИБКА: Библиотека pyairtable не установлена!")
        logger.error("❌ [AIRTABLE] Выполните: pip install pyairtable")
        return None

    except Exception as e:
        logger.exception("!!! КРИТИЧЕСКАЯ ОШИБКА СОЗДАНИЯ ЛИДА В AIRTABLE !!!")
        logger.error(f"❌ [AIRTABLE] Тип ошибки: {type(e).__name__}")
        logger.error(f"❌ [AIRTABLE] Сообщение: {str(e)}")
        logger.error(f"❌ [AIRTABLE] Base: {base_id}, Table: {table_id}")
        return None
