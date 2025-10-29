"""
Сервис для работы с Airtable API.

Универсальный сервис для сохранения заявок в Airtable.
Поддерживает мультитенантность - каждый клиент может иметь свою базу.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AirtableService:
    """
    Универсальный сервис для работы с Airtable.

    Используется для сохранения заявок из обоих ботов (Telegram и WhatsApp)
    в соответствующие базы Airtable каждого клиента.

    Attributes:
        api_key: Access Token для Airtable API
        base_id: ID базы в Airtable (например, app1X2TpPVukeswtK)
        table_name: Название таблицы/листа (например, "Заявки с ботов")
    """

    def __init__(self, api_key: str, base_id: str, table_name: str):
        """
        Инициализирует сервис Airtable.

        Args:
            api_key: Access Token для Airtable API
            base_id: ID базы в Airtable
            table_name: Название таблицы для сохранения заявок

        Raises:
            ValueError: Если обязательные параметры не переданы
        """
        if not api_key:
            raise ValueError("AIRTABLE_API_KEY не может быть пустым")
        if not base_id:
            raise ValueError("AIRTABLE_BASE_ID не может быть пустым")
        if not table_name:
            raise ValueError("AIRTABLE_TABLE_NAME не может быть пустым")

        self.api_key = api_key
        self.base_id = base_id
        self.table_name = table_name

        logger.info(f"✅ AirtableService инициализирован: base={base_id}, table={table_name}")

    async def create_application(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Создает новую заявку в Airtable.

        Args:
            data: Словарь с данными заявки. Ожидаемые ключи:
                - client_name: Имя клиента
                - client_phone: Телефон клиента
                - source: Источник (Telegram / WhatsApp)
                - project: Проект/Компания (EVOPOLIKI / 5DELUXE)
                - product: Товар (категория + марка + модель)
                - details: Детали заказа (опции, бортики и т.д.)
                - price: Цена (опционально)
                - user_id: User ID (опционально)
                - username: Username (опционально)

        Returns:
            str: ID созданной записи в Airtable, или None при ошибке

        Example:
            >>> service = AirtableService(api_key, base_id, table_name)
            >>> record_id = await service.create_application({
            ...     "client_name": "Иван Иванов",
            ...     "client_phone": "+996555123456",
            ...     "source": "Telegram",
            ...     "project": "EVOPOLIKI",
            ...     "product": "EVA коврики для Toyota Camry",
            ...     "details": "С бортами 5 см",
            ...     "price": 4500
            ... })
        """
        try:
            from pyairtable import Api

            logger.info("🔄 [AIRTABLE] Попытка сохранить заявку в Airtable...")
            logger.info(f"🔄 [AIRTABLE] Base: {self.base_id}, Table: {self.table_name}")
            logger.info(f"🔄 [AIRTABLE] Данные: {data}")

            # Инициализируем API клиент
            api = Api(self.api_key)
            table = api.table(self.base_id, self.table_name)

            # Формируем запись для Airtable на основе ПОЛНОЙ схемы таблицы (13 колонок)
            # Используем ТОЧНЫЕ названия колонок из Meta API!
            record_fields = {}

            # ═══════════════════════════════════════════════════════════════
            # КОНТАКТНЫЕ ДАННЫЕ
            # ═══════════════════════════════════════════════════════════════

            record_fields["Имя клиента"] = data.get("client_name", "Не указано")

            if data.get("client_phone"):
                record_fields["Телефон клиента"] = data["client_phone"]

            if data.get("username"):
                record_fields["Username"] = data["username"]

            # ═══════════════════════════════════════════════════════════════
            # ИСТОЧНИК И МЕТАДАННЫЕ
            # ═══════════════════════════════════════════════════════════════

            if data.get("source"):
                record_fields["Источник"] = data["source"]

            # ═══════════════════════════════════════════════════════════════
            # ДАННЫЕ ЗАКАЗА - РАСПРЕДЕЛЯЕМ ПО ОТДЕЛЬНЫМ КОЛОНКАМ!
            # ═══════════════════════════════════════════════════════════════

            # 1. "Товар" - ТОЛЬКО категория товара (Eva коврики, 5D коврики и т.д.)
            if data.get("product_category"):
                record_fields["Товар"] = data["product_category"]

            # 2. "Автомобиль" - марка и модель
            if data.get("car"):
                record_fields["Автомобиль"] = data["car"]

            # 3. "Детали / Опции" - опции заказа (с бортами, без бортов и т.д.)
            if data.get("options"):
                record_fields["Детали / Опции"] = data["options"]

            # 4. "Итоговая цена" - ЧИСЛОВОЕ значение для currency поля
            if data.get("price") is not None and data.get("price") > 0:
                record_fields["Итоговая цена"] = data["price"]

            # 5. "Тип заявки" - тип заявки (Заказ товара, Индивидуальный замер)
            if data.get("application_type"):
                record_fields["Тип заявки"] = data["application_type"]

            # Создаем запись
            record = table.create(record_fields)
            record_id = record["id"]

            logger.info(f"✅ [AIRTABLE] Заявка успешно сохранена в Airtable. Record ID: {record_id}")
            logger.info(f"✅ [AIRTABLE] Клиент: {data.get('client_name')} ({data.get('client_phone')})")
            logger.info(f"✅ [AIRTABLE] Источник: {data.get('source')}")
            logger.info(f"✅ [AIRTABLE] Товар: {record_fields.get('Товар', 'Не указано')}")
            logger.info(f"✅ [AIRTABLE] Автомобиль: {record_fields.get('Автомобиль', 'Не указано')}")
            logger.info(f"✅ [AIRTABLE] Детали/Опции: {record_fields.get('Детали / Опции', 'Не указано')}")
            if record_fields.get('Итоговая цена'):
                logger.info(f"✅ [AIRTABLE] Цена: {record_fields['Итоговая цена']} сом")
            logger.info(f"✅ [AIRTABLE] Тип заявки: {record_fields.get('Тип заявки', 'Не указано')}")

            return record_id

        except ImportError:
            logger.error("❌ [AIRTABLE] ОШИБКА: Библиотека pyairtable не установлена!")
            logger.error("❌ [AIRTABLE] Выполните: pip install pyairtable")
            return None

        except Exception as e:
            logger.exception("!!! КРИТИЧЕСКАЯ ОШИБКА СОХРАНЕНИЯ В AIRTABLE !!!")
            logger.error(f"❌ [AIRTABLE] Тип ошибки: {type(e).__name__}")
            logger.error(f"❌ [AIRTABLE] Сообщение: {str(e)}")
            logger.error(f"❌ [AIRTABLE] Base: {self.base_id}, Table: {self.table_name}")
            return None
