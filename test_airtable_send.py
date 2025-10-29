"""
Тестовый скрипт для отправки тестовой заявки в Airtable (EVOPOLIKI).

Использует реальные переменные окружения из .env
"""

import asyncio
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_airtable_send():
    """Отправляет тестовую заявку в Airtable."""

    # Загружаем переменные окружения
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    logger.info("🔍 Проверка переменных окружения...")

    # Получаем Airtable credentials
    airtable_api_key = os.getenv("AIRTABLE_API_KEY")
    airtable_base_id = os.getenv("AIRTABLE_BASE_ID")
    airtable_table_name = os.getenv("AIRTABLE_TABLE_NAME", "Заявки с ботов")

    if not airtable_api_key or not airtable_base_id:
        logger.error("❌ ОШИБКА: Отсутствуют переменные окружения для Airtable!")
        logger.error(f"   AIRTABLE_API_KEY: {'✅ установлен' if airtable_api_key else '❌ не установлен'}")
        logger.error(f"   AIRTABLE_BASE_ID: {'✅ установлен' if airtable_base_id else '❌ не установлен'}")
        return

    logger.info(f"✅ API Key: {airtable_api_key[:10]}...")
    logger.info(f"✅ Base ID: {airtable_base_id}")
    logger.info(f"✅ Table Name: {airtable_table_name}")

    # Импортируем AirtableService
    from packages.core.services.airtable_service import AirtableService

    # Создаём сервис
    logger.info("\n🔧 Создание AirtableService...")
    service = AirtableService(
        api_key=airtable_api_key,
        base_id=airtable_base_id,
        table_name=airtable_table_name
    )

    # Подготавливаем тестовые данные
    # ВАЖНО: "source" должен быть из существующих значений в Airtable
    test_data = {
        "client_name": "Тестовый клиент (из скрипта)",
        "client_phone": "+996777999888",
        "source": "WhatsApp",  # Используем стандартное значение
        "product_category": "🔹 EVA-коврики",
        "car": "Toyota Camry 2020",
        "options": "✅ С бортами 5 см\n✅ Цвет: Черный",
        "price": 2800,
        "application_type": "Заказ товара"
    }

    logger.info("\n📦 Тестовые данные для отправки:")
    for key, value in test_data.items():
        logger.info(f"   {key}: {value}")

    # Отправляем заявку
    logger.info("\n🚀 Отправка заявки в Airtable...")
    record_id = await service.create_application(test_data)

    if record_id:
        logger.info("\n" + "="*70)
        logger.info("✅ ✅ ✅ ТЕСТОВАЯ ЗАЯВКА УСПЕШНО ОТПРАВЛЕНА! ✅ ✅ ✅")
        logger.info(f"📋 Record ID: {record_id}")
        logger.info("="*70)
        logger.info("\n🔍 Проверьте Airtable, заявка должна появиться в таблице!")
    else:
        logger.error("\n" + "="*70)
        logger.error("❌ ❌ ❌ ОШИБКА ОТПРАВКИ! ❌ ❌ ❌")
        logger.error("="*70)
        logger.error("\n🔍 Проверьте логи выше для деталей ошибки.")


if __name__ == "__main__":
    asyncio.run(test_airtable_send())
