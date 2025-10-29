"""
Тестовый скрипт для проверки интеграции с НОВОЙ базой Airtable (EVOPOLIKI).

Использует новый airtable_manager с правильным маппингом полей.
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


async def test_new_airtable():
    """Тестирует отправку заявки в НОВУЮ базу Airtable."""

    # Загружаем переменные окружения
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    logger.info("🔍 Проверка переменных окружения для EVOPOLIKI...")

    # Получаем credentials для EVOPOLIKI
    api_token = os.getenv("EVOPOLIKI_AIRTABLE_API_TOKEN")
    base_id = os.getenv("EVOPOLIKI_AIRTABLE_BASE_ID")
    table_id = os.getenv("EVOPOLIKI_AIRTABLE_TABLE_ID")

    if not all([api_token, base_id, table_id]):
        logger.error("❌ ОШИБКА: Отсутствуют переменные окружения для EVOPOLIKI Airtable!")
        logger.error(f"   EVOPOLIKI_AIRTABLE_API_TOKEN: {'✅' if api_token else '❌'}")
        logger.error(f"   EVOPOLIKI_AIRTABLE_BASE_ID: {'✅' if base_id else '❌'}")
        logger.error(f"   EVOPOLIKI_AIRTABLE_TABLE_ID: {'✅' if table_id else '❌'}")
        return

    logger.info(f"✅ API Token: {api_token[:20]}...")
    logger.info(f"✅ Base ID: {base_id}")
    logger.info(f"✅ Table ID: {table_id}")

    # Импортируем airtable_manager
    from packages.core.integrations import create_lead

    # Подготавливаем тестовые данные
    test_lead_data = {
        "name": "Тестовый клиент (НОВАЯ БАЗА)",
        "phone": "+996777888999",
        "username": "996777888999@c.us",
        "category": "🔹 EVA-коврики",
        "car_brand": "Toyota",
        "car_model": "Camry 2022",
        "options": "С бортами 5 см, Черный цвет",
        "price": 2800
    }

    logger.info("\n📦 Тестовые данные для отправки:")
    for key, value in test_lead_data.items():
        logger.info(f"   {key}: {value}")

    # Отправляем заявку
    logger.info("\n🚀 Отправка заявки в НОВУЮ базу Airtable...")
    record_id = await create_lead(test_lead_data, tenant_slug="evopoliki")

    if record_id:
        logger.info("\n" + "="*70)
        logger.info("✅ ✅ ✅ ТЕСТОВАЯ ЗАЯВКА УСПЕШНО ОТПРАВЛЕНА! ✅ ✅ ✅")
        logger.info(f"📋 Record ID: {record_id}")
        logger.info("="*70)
        logger.info("\n🔍 Проверьте Airtable:")
        logger.info(f"   Base: {base_id}")
        logger.info(f"   Table: {table_id}")
        logger.info("   https://airtable.com/appVkpLFJbf0APDj5/tblUV3a6NRB0azN22/viwotYdoR4kSyXbih?blocks=hide")
    else:
        logger.error("\n" + "="*70)
        logger.error("❌ ❌ ❌ ОШИБКА ОТПРАВКИ! ❌ ❌ ❌")
        logger.error("="*70)
        logger.error("\n🔍 Проверьте логи выше для деталей ошибки.")


if __name__ == "__main__":
    asyncio.run(test_new_airtable())
