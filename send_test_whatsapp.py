"""
Скрипт для отправки тестового сообщения через WhatsApp (GreenAPI).

Использование:
    python send_test_whatsapp.py 996777123456
"""

import sys
import os
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def send_test_message(phone_number: str, tenant: str = "evopoliki"):
    """
    Отправляет тестовое сообщение через WhatsApp.

    Args:
        phone_number: Номер телефона в формате 996XXXXXXXXX
        tenant: Тенант (evopoliki или five_deluxe)
    """
    # Загружаем переменные окружения
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    # Получаем credentials для выбранного тенанта
    tenant_upper = tenant.upper()
    instance_id = os.getenv(f"{tenant_upper}_WHATSAPP_INSTANCE_ID")
    api_token = os.getenv(f"{tenant_upper}_WHATSAPP_API_TOKEN")
    api_url = os.getenv(f"{tenant_upper}_WHATSAPP_API_URL")

    if not all([instance_id, api_token, api_url]):
        logger.error(f"❌ Не найдены credentials для {tenant}")
        return

    logger.info(f"✅ Credentials загружены для {tenant.upper()}")
    logger.info(f"   Instance ID: {instance_id}")
    logger.info(f"   API URL: {api_url}")

    # Формируем chat_id (добавляем @c.us)
    chat_id = f"{phone_number}@c.us"

    # Тестовое сообщение
    test_message = """🤖 *Тестовое сообщение от бота EVOPOLIKI*

Привет! Это тестовое сообщение для проверки работы WhatsApp бота.

✅ Интеграция работает!
✅ Бот готов к работе!

Попробуйте написать любое сообщение, чтобы начать диалог.

Например:
• Привет
• Каталог
• Цены"""

    logger.info(f"\n📱 Отправка сообщения на номер: {phone_number}")
    logger.info(f"📝 Chat ID: {chat_id}")

    # Отправляем сообщение через GreenAPI
    url = f"{api_url}/waInstance{instance_id}/sendMessage/{api_token}"

    payload = {
        "chatId": chat_id,
        "message": test_message
    }

    logger.info(f"🔗 URL: {url}")
    logger.info(f"📤 Отправка запроса...")

    try:
        response = requests.post(url, json=payload, timeout=30)

        logger.info(f"📊 Status Code: {response.status_code}")
        logger.info(f"📄 Response: {response.text}")

        if response.status_code == 200:
            logger.info("\n" + "="*70)
            logger.info("✅ ✅ ✅ СООБЩЕНИЕ УСПЕШНО ОТПРАВЛЕНО! ✅ ✅ ✅")
            logger.info("="*70)
            logger.info(f"\n🔍 Проверьте WhatsApp на номере +{phone_number}")
            return True
        else:
            logger.error("\n" + "="*70)
            logger.error("❌ ❌ ❌ ОШИБКА ОТПРАВКИ! ❌ ❌ ❌")
            logger.error("="*70)
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("❌ Укажите номер телефона!")
        print("\nИспользование:")
        print("  python send_test_whatsapp.py 996777123456")
        print("\nПримеры:")
        print("  python send_test_whatsapp.py 996777510804")
        print("  python send_test_whatsapp.py 996507988088")
        sys.exit(1)

    phone_number = sys.argv[1].strip()

    # Убираем + если есть
    phone_number = phone_number.replace("+", "")

    # Проверяем формат
    if not phone_number.isdigit() or len(phone_number) != 12:
        print(f"❌ Неверный формат номера: {phone_number}")
        print("Ожидается формат: 996XXXXXXXXX (12 цифр)")
        sys.exit(1)

    # Тенант по умолчанию - evopoliki
    tenant = sys.argv[2] if len(sys.argv) > 2 else "evopoliki"

    print(f"\n🚀 Отправка тестового сообщения...")
    print(f"📱 Номер: +{phone_number}")
    print(f"🏢 Тенант: {tenant.upper()}\n")

    send_test_message(phone_number, tenant)


if __name__ == "__main__":
    main()
