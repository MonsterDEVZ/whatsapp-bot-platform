"""
WhatsApp Gateway - FastAPI веб-сервер для приема вебхуков от GreenAPI.

Принимает входящие сообщения от пользователей WhatsApp и обрабатывает их,
используя общее ядро платформы (Config, локализация, база данных).
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from contextlib import asynccontextmanager

# Добавляем путь к корню проекта для импорта core (ВАЖНО: делаем это первым!)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import httpx
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import AsyncSession

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загружаем .env файлы из tenant-директорий (для локальной разработки)
# В production (Railway) переменные окружения устанавливаются через UI
apps_dir = project_root / "apps"
for tenant_dir in ["telegram/evopoliki", "telegram/five_deluxe"]:
    env_path = apps_dir / tenant_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded .env from {env_path}")
    else:
        logger.info(f".env file not found at {env_path}, using environment variables")

from packages.core.config import Config
from packages.core.db.connection import close_db, get_session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession as SQLAsyncSession
from sqlalchemy import text
from packages.core.memory import init_memory, get_memory
from packages.core.ai.assistant import AssistantManager, get_or_create_thread
from packages.core.ai.response_parser import (
    detect_response_type,
    extract_order_data,
    format_response_for_platform,
    clean_text_for_whatsapp
)
from packages.core.utils.category_mapper import get_category_name

# Импортируем наши обработчики
from .state_manager import get_state, get_user_data, WhatsAppState, set_state, update_user_data
from . import whatsapp_handlers

# Глобальный словарь AssistantManager для каждого tenant
# Формат: {tenant_slug: AssistantManager}
tenant_assistant_managers: Dict[str, AssistantManager] = {}

# Глобальные переменные для БД (инициализируются в lifespan)
db_engine = None
db_session_factory = None


# ============================================================================
# LIFESPAN MANAGER
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Менеджер жизненного цикла приложения.
    Инициализирует ресурсы при старте и освобождает при остановке.
    """
    global db_engine, db_session_factory

    # Startup
    logger.info("🚀 Starting WhatsApp Gateway...")

    # Инициализируем базу данных напрямую через DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL не установлен в переменных окружения!")

    # Конвертируем postgresql:// в postgresql+asyncpg:// для async engine
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Создаем async engine
    db_engine = create_async_engine(
        database_url,
        echo=False,  # Отключаем SQL логирование для production
        pool_pre_ping=True,  # Проверять соединение перед использованием
        pool_size=5,
        max_overflow=10
    )

    # Создаем фабрику сессий
    db_session_factory = async_sessionmaker(
        db_engine,
        class_=SQLAsyncSession,
        expire_on_commit=False
    )

    # Проверяем подключение
    try:
        async with db_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        raise

    # Инициализируем DialogMemory (общая для всех tenant)
    dialog_memory = init_memory(max_messages=6)
    logger.info("✅ DialogMemory initialized")

    # Загружаем конфигурации tenant и создаем их AssistantManager
    load_tenant_configs()
    logger.info("✅ WhatsApp Gateway is ready!")

    yield

    # Shutdown
    logger.info("🛑 Shutting down WhatsApp Gateway...")
    if db_engine:
        await db_engine.dispose()
        logger.info("✅ База данных закрыта")


# Создаем FastAPI приложение с lifespan
app = FastAPI(
    title="WhatsApp Gateway",
    description="Multi-tenant WhatsApp bot gateway using GreenAPI",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# КОНФИГУРАЦИЯ ТЕНАНТОВ
# ============================================================================

class TenantConfig:
    """Конфигурация WhatsApp для конкретного tenant."""

    def __init__(self, tenant_slug: str):
        self.tenant_slug = tenant_slug

        # Формируем префикс с заменой дефиса на подчеркивание
        tenant_prefix = tenant_slug.upper().replace("-", "_")

        # WhatsApp настройки
        self.instance_id = os.getenv(f"{tenant_prefix}_WHATSAPP_INSTANCE_ID")
        self.api_token = os.getenv(f"{tenant_prefix}_WHATSAPP_API_TOKEN")
        self.phone_number = os.getenv(f"{tenant_prefix}_WHATSAPP_PHONE_NUMBER")
        self.api_url = os.getenv(f"{tenant_prefix}_WHATSAPP_API_URL", "https://7107.api.green-api.com")

        # OpenAI credentials для этого tenant
        self.openai_api_key = (
            os.getenv(f"{tenant_prefix}_OPENAI_API_KEY") or
            os.getenv("OPENAI_API_KEY")
        )
        self.openai_assistant_id = (
            os.getenv(f"{tenant_prefix}_OPENAI_ASSISTANT_ID") or
            os.getenv("OPENAI_ASSISTANT_ID")
        )

        # Настройки для диалогового режима (без зависимости от Telegram Config)
        enable_dialog_mode_str = (
            os.getenv(f"{tenant_prefix}_ENABLE_DIALOG_MODE") or
            os.getenv("ENABLE_DIALOG_MODE") or
            "false"
        )
        self.enable_dialog_mode = str(enable_dialog_mode_str).strip().lower() in ("true", "1", "yes")

        # Создаем i18n экземпляр для локализации
        from packages.core.config import I18nInstance
        try:
            self.i18n = I18nInstance(tenant_slug=tenant_slug, language="ru")
        except FileNotFoundError:
            logger.warning(f"⚠️  Localization file not found for {tenant_slug}, using default")
            self.i18n = None

    def is_valid(self) -> bool:
        """Проверяет, что все необходимые параметры заданы."""
        # phone_number опциональный - GreenAPI работает без него
        return all([self.instance_id, self.api_token])


# Маппинг instance_id -> tenant_slug
TENANT_INSTANCES: Dict[str, str] = {}


def load_tenant_configs():
    """Загружает конфигурации всех тенантов при старте."""
    tenants = ["evopoliki", "five_deluxe"]  

    for tenant_slug in tenants:
        try:
            tenant_config = TenantConfig(tenant_slug)

            if tenant_config.is_valid():
                TENANT_INSTANCES[tenant_config.instance_id] = tenant_slug
                logger.info(f"✅ Loaded WhatsApp config for {tenant_slug} (instance: {tenant_config.instance_id})")
                
                # Предупреждение если phone_number отсутствует (опционально для GreenAPI)
                if not tenant_config.phone_number:
                    logger.warning(f"⚠️  {tenant_slug}: WHATSAPP_PHONE_NUMBER not set (optional)")
                
                # Создаем AssistantManager для этого tenant
                if tenant_config.openai_api_key and tenant_config.openai_assistant_id:
                    try:
                        memory = get_memory()
                        assistant_manager = AssistantManager(
                            api_key=tenant_config.openai_api_key,
                            assistant_id=tenant_config.openai_assistant_id,
                            memory=memory
                        )
                        tenant_assistant_managers[tenant_slug] = assistant_manager
                        logger.info(f"✅ AssistantManager initialized for {tenant_slug} (Assistant ID: {tenant_config.openai_assistant_id})")
                    except Exception as e:
                        logger.error(f"❌ Failed to initialize AssistantManager for {tenant_slug}: {e}")
                else:
                    logger.warning(f"⚠️  Missing OpenAI credentials for {tenant_slug}")
            else:
                logger.warning(f"⚠️  Missing WhatsApp config for {tenant_slug}")
        except Exception as e:
            logger.warning(f"⚠️  Не удалось загрузить клиента {tenant_slug}: {e}")

    logger.info(f"📱 Total active WhatsApp instances: {len(TENANT_INSTANCES)}")
    logger.info(f"🤖 Total active AI Assistants: {len(tenant_assistant_managers)}")


# ============================================================================
# GREENAPI CLIENT
# ============================================================================

class GreenAPIClient:
    """Клиент для работы с GreenAPI."""

    def __init__(self, tenant_config: TenantConfig):
        self.tenant_config = tenant_config
        self.base_url = f"{tenant_config.api_url}/waInstance{tenant_config.instance_id}"

    async def send_message(self, chat_id: str, message: str) -> bool:
        """
        Отправляет текстовое сообщение в WhatsApp.

        ВАЖНО: Автоматически очищает HTML-теги и конвертирует в WhatsApp Markdown.

        Args:
            chat_id: ID чата (номер телефона в формате 79001234567@c.us)
            message: Текст сообщения (может содержать HTML)

        Returns:
            True если успешно отправлено, False если ошибка
        """
        # 🔒 ОБЯЗАТЕЛЬНЫЙ "ТАМОЖЕННЫЙ КОНТРОЛЬ":
        # Все сообщения проходят очистку HTML → WhatsApp Markdown
        # Это гарантирует профессиональный вид для ВСЕХ сообщений
        cleaned_message = clean_text_for_whatsapp(message)

        # Логируем если были HTML-теги
        if cleaned_message != message:
            logger.debug(f"[HTML_CLEANUP] Original: {message[:100]}...")
            logger.debug(f"[HTML_CLEANUP] Cleaned:  {cleaned_message[:100]}...")

        url = f"{self.base_url}/sendMessage/{self.tenant_config.api_token}"

        payload = {
            "chatId": chat_id,
            "message": cleaned_message  # ← Используем очищенное сообщение!
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)

                if response.status_code == 200:
                    logger.info(f"✅ Message sent to {chat_id}: {message[:50]}...")
                    return True
                else:
                    logger.error(f"❌ Failed to send message: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"❌ Exception while sending message: {e}")
            return False


# ============================================================================
# WEBHOOK HANDLERS
# ============================================================================

@app.post("/webhook")
async def webhook_handler(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    Главный endpoint для приема вебхуков от GreenAPI.

    GreenAPI отправляет POST-запросы с информацией о входящих сообщениях.
    """
    try:
        # Получаем тело запроса
        body = await request.json()

        logger.info(f"📨 Received webhook: {body}")

        # Извлекаем данные из вебхука
        webhook_type = body.get("typeWebhook")
        instance_data = body.get("instanceData", {})
        message_data = body.get("messageData")

        # Определяем instance_id
        instance_id = instance_data.get("idInstance")

        if not instance_id:
            logger.warning("⚠️  No instance_id in webhook")
            return JSONResponse({"status": "error", "message": "No instance_id"}, status_code=400)

        # Определяем tenant по instance_id
        tenant_slug = TENANT_INSTANCES.get(str(instance_id))

        if not tenant_slug:
            logger.warning(f"⚠️  Unknown instance_id: {instance_id}")
            return JSONResponse({"status": "error", "message": "Unknown instance"}, status_code=400)

        logger.info(f"🏢 Tenant identified: {tenant_slug}")

        # Обрабатываем только входящие сообщения
        if webhook_type == "incomingMessageReceived":
            sender_data = body.get("senderData", {})
            await handle_incoming_message(tenant_slug, message_data, sender_data, session)

        return JSONResponse({"status": "ok"})

    except Exception as e:
        logger.error(f"❌ Error in webhook handler: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def handle_incoming_message(
    tenant_slug: str,
    message_data: Dict[str, Any],
    sender_data: Dict[str, Any],
    session: AsyncSession
):
    """
    Обрабатывает входящее сообщение от пользователя WhatsApp.
    Роутит сообщения по обработчикам в зависимости от tenant и состояния пользователя.

    Args:
        tenant_slug: Идентификатор tenant (evopoliki, five_deluxe)
        message_data: Данные сообщения из вебхука
        sender_data: Данные отправителя из вебхука
    """
    try:
        # Извлекаем информацию о сообщении
        type_message = message_data.get("typeMessage")
        text_message = message_data.get("textMessageData", {}).get("textMessage", "")
        chat_id = sender_data.get("chatId")
        sender_name = sender_data.get("senderName", "Гость")

        logger.info(f"💬 Message from {sender_name} ({chat_id}): {text_message}")

        # ====================================================================
        # 🔍 ПРОВЕРКА #1: СЕКРЕТНАЯ ОТЛАДОЧНАЯ КОМАНДА (ВЫСШИЙ ПРИОРИТЕТ)
        # ====================================================================
        if text_message.lower().startswith("ask_ai:"):
            logger.info(f"🔍 [AI_DEBUG] Detected ask_ai command from {chat_id}")
            
            # Загружаем конфигурацию tenant
            tenant_config = TenantConfig(tenant_slug)
            if not tenant_config.is_valid():
                logger.error(f"❌ Invalid tenant config for {tenant_slug}")
                return
            
            # Импортируем обработчик
            from ivr_handlers_5deluxe import handle_ask_ai_whatsapp

            # Вызываем обработчик ask_ai (передаем tenant_config вместо config)
            response = await handle_ask_ai_whatsapp(chat_id, text_message, tenant_config)
            
            # Отправляем ответ
            if response:  # Может вернуть пустую строку для неавторизованных пользователей
                client = GreenAPIClient(tenant_config)
                await client.send_message(chat_id, response)
                logger.info(f"✅ [AI_DEBUG] Sent response to {sender_name}")
            
            return  # Выходим, не обрабатывая дальше

        # ====================================================================
        # ⏱️  ПРОВЕРКА ТАЙМАУТА СЕССИИ (15 МИНУТ)
        # ====================================================================
        try:
            memory = get_memory()
            session_timed_out = memory.check_timeout(chat_id, timeout_seconds=900)

            logger.info(f"⏱️  [TIMEOUT_CHECK] User: {chat_id}")
            logger.info(f"⏱️  [TIMEOUT_CHECK] Session timed out: {session_timed_out}")

            if session_timed_out:
                # Сессия истекла - очищаем состояние и память
                from state_manager import clear_state
                clear_state(chat_id)
                memory.clear_history(chat_id)

                logger.critical(f"🔥 [TIMEOUT] Сессия для {sender_name} ({chat_id}) СБРОШЕНА по таймауту!")
                logger.info(f"🗑️  [TIMEOUT] Очищены: FSM state + AI memory")

                # ====================================================================
                # 🎯 УМНОЕ ПРИВЕТСТВИЕ ПОСЛЕ ТАЙМАУТА
                #
                # НОВАЯ ЛОГИКА:
                # - Если enable_dialog_mode=True → передаем приветствие в AI
                # - Если enable_dialog_mode=False → показываем меню
                # ====================================================================
                if is_greeting(text_message):
                    logger.info(f"👋 [TIMEOUT] Приветствие после таймаута от {sender_name}")

                    # Загружаем конфигурацию tenant
                    tenant_config = TenantConfig(tenant_slug)
                    if tenant_config.is_valid():
                        enable_ai = tenant_config.enable_dialog_mode

                        logger.info(f"🎯 [TIMEOUT] enable_dialog_mode = {enable_ai}")

                        if enable_ai:
                            # AI РЕЖИМ: Пропускаем дальше, чтобы AI обработал приветствие
                            logger.info(f"🤖 [TIMEOUT] AI режим → Передаем приветствие в AI Assistant")
                            # НЕ делаем return - продолжаем выполнение, чтобы дойти до AI-обработчика
                        else:
                            # IVR РЕЖИМ: Показываем меню
                            logger.info(f"📋 [TIMEOUT] IVR режим → Показываем меню")

                            greeting_response = await whatsapp_handlers.handle_start_message(chat_id, tenant_config)
                            personalized_greeting = f"Здравствуйте, {sender_name}! Снова рад вас видеть. 😊\n\n{greeting_response}"

                            client = GreenAPIClient(tenant_config)
                            await client.send_message(chat_id, personalized_greeting)
                            logger.info(f"✅ [TIMEOUT] Отправлено IVR-меню для {sender_name}")

                            return  # Завершаем - меню показано

        except Exception as e:
            logger.error(f"❌ [TIMEOUT] Ошибка при проверке таймаута: {e}", exc_info=True)

        # ====================================================================
        # ✅ WHITELIST ОТКЛЮЧЕН - БОТ ОТВЕЧАЕТ ВСЕМ ПОЛЬЗОВАТЕЛЯМ
        # ====================================================================
        logger.info(f"✅ Processing message from {chat_id} (whitelist disabled)")

        # Загружаем конфигурацию tenant
        tenant_config = TenantConfig(tenant_slug)

        if not tenant_config.is_valid():
            logger.error(f"❌ Invalid tenant config for {tenant_slug}")
            return

        # ====================================================================
        # УНИФИЦИРОВАННЫЙ РОУТИНГ: ДИНАМИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ AI/IVR
        # ====================================================================
        enable_ai = tenant_config.enable_dialog_mode

        logger.debug(f"[ROUTING] tenant={tenant_slug} enable_dialog_mode={enable_ai}")
        logger.info(f"🔀 [ROUTING] {tenant_slug}: {'AI mode' if enable_ai else 'IVR mode'}")

        if enable_ai:
            # ========== РЕЖИМ AI ВКЛЮЧЕН ==========
            logger.info(f"🤖 [ROUTING] Dialog mode ENABLED -> AI Assistant flow")

            # Обработка команды "Меню" - возврат в главное меню
            if text_message.lower() in ["меню", "menu", "/start", "start"]:
                # Очищаем историю диалога
                try:
                    memory = get_memory()
                    memory.clear_history(chat_id)
                    logger.info(f"🗑️ [MEMORY] Очищена история для {chat_id}")
                except Exception as e:
                    logger.warning(f"⚠️ [MEMORY] Ошибка очистки: {e}")

                # Показываем IVR меню
                if tenant_slug == "five_deluxe":
                    from ivr_handlers_5deluxe import handle_5deluxe_message
                    response = await handle_5deluxe_message(chat_id, text_message, tenant_config, session, sender_name=sender_name)
                else:
                    response = await whatsapp_handlers.handle_start_message(chat_id, tenant_config)
            else:
                # Роутим через AI Assistant
                response = await route_message_by_state(chat_id, text_message, tenant_config, tenant_slug, session)

        else:
            # ========== РЕЖИМ IVR ONLY ==========
            logger.info(f"📋 [ROUTING] Dialog mode DISABLED -> IVR menu flow ONLY")

            # Используем только IVR обработчики
            if tenant_slug == "five_deluxe":
                from ivr_handlers_5deluxe import handle_5deluxe_message
                response = await handle_5deluxe_message(chat_id, text_message, tenant_config, session, sender_name=sender_name)
            else:
                # Для evopoliki создадим базовый IVR
                response = await whatsapp_handlers.handle_start_message(chat_id, tenant_config)

        # Отправляем ответ
        client = GreenAPIClient(tenant_config)
        logger.info(f"📤 [SEND_MESSAGE] Sending response to {chat_id}: {response[:100]}...")
        await client.send_message(chat_id, response)
        logger.info(f"✅ [SEND_MESSAGE] Successfully sent response to {sender_name}")

    except Exception as e:
        logger.error(f"❌ Error handling incoming message: {e}", exc_info=True)


def is_greeting(text: str) -> bool:
    """
    Проверяет, является ли сообщение приветствием.

    Args:
        text: Текст сообщения

    Returns:
        True если это приветствие, False в противном случае
    """
    greetings = [
        "привет", "здравствуй", "здравствуйте", "приветствую",
        "hello", "hi", "hey", "добрый день", "доброе утро", "добрый вечер",
        "доброй ночи", "хай", "хей", "салам", "сәлем"
    ]
    text_lower = text.lower().strip()
    return any(greeting in text_lower for greeting in greetings)


def is_ivr_command(text: str, state: WhatsAppState) -> bool:
    """
    Проверяет, является ли текстовое сообщение ожидаемой IVR-командой
    для текущего состояния.

    Args:
        text: Текст сообщения
        state: Текущее состояние FSM

    Returns:
        True если это ожидаемая IVR-команда, False если это свободный текст для AI
    """
    text = text.strip()

    # Главное меню: ожидаем цифры 1-5
    if state == WhatsAppState.MAIN_MENU:
        return text in ["1", "2", "3", "4", "5"]

    # EVA: ожидание марки - цифры 1-8, пагинация 00/99, или текст марки
    elif state == WhatsAppState.EVA_WAITING_BRAND:
        # Пагинация
        if text in ["00", "99"]:
            return True
        # Выбор из списка (1-8)
        if text.isdigit() and 1 <= int(text) <= 8:
            return True
        # Текстовый ввод марки - считаем IVR-командой (обработчик поддерживает)
        return True

    # EVA: ожидание модели - цифры 1-8, пагинация 00/99, или текст модели
    elif state == WhatsAppState.EVA_WAITING_MODEL:
        # Пагинация
        if text in ["00", "99"]:
            return True
        # Выбор из списка (1-8)
        if text.isdigit() and 1 <= int(text) <= 8:
            return True
        # Ответы на fuzzy suggestion (1 или 2)
        if text in ["1", "2"]:
            return True
        # Текстовый ввод модели - считаем IVR-командой
        return True

    # EVA: выбор опций - ожидаем цифры 1-3
    elif state == WhatsAppState.EVA_SELECTING_OPTIONS:
        return text in ["1", "2", "3"]

    # EVA: подтверждение заказа - ожидаем "1" или текстовые варианты подтверждения
    elif state == WhatsAppState.EVA_CONFIRMING_ORDER:
        positive_answers = ["1", "да", "yes", "ок", "ok", "+", "конечно", "давай", "давайте"]
        return text.lower() in positive_answers

    # Сбор контактов - любой текст является ожидаемым вводом
    elif state in [WhatsAppState.WAITING_FOR_NAME, WhatsAppState.WAITING_FOR_PHONE]:
        return True

    # Для всех остальных состояний - не IVR-команда
    return False


async def route_message_by_state(
    chat_id: str,
    text: str,
    tenant_config: TenantConfig,
    tenant_slug: str,
    session: AsyncSession
) -> str:
    """
    Роутит входящее сообщение к соответствующему обработчику
    в зависимости от состояния пользователя.

    УМНЫЙ РОУТИНГ:
    - Если пользователь в IDLE или сообщение не является IVR-командой -> AI Assistant
    - Если пользователь в FSM-состоянии и ввод соответствует ожиданиям -> IVR-обработчик

    Args:
        chat_id: ID чата WhatsApp
        text: Текст сообщения
        tenant_config: Конфигурация tenant
        tenant_slug: Идентификатор tenant (для получения правильного AssistantManager)
        session: Сессия БД

    Returns:
        Текст ответа для отправки пользователю
    """
    
    # Получаем AssistantManager для этого tenant
    assistant_manager = tenant_assistant_managers.get(tenant_slug)
    current_state = get_state(chat_id)
    logger.info(f"🔀 [ROUTE] User {chat_id} in state: {current_state}, message: '{text}'")

    # IDLE или первое сообщение - используем AI Assistant для консультации
    if current_state == WhatsAppState.IDLE:
        logger.info(f"🤖 IDLE state - using AI Assistant for message: {text}")
        logger.info("=" * 60)
        logger.info("🤖 *** AI HANDLER TRIGGERED *** 🤖")
        logger.info("=" * 60)

        # Получаем или создаем thread для пользователя
        thread_id = get_or_create_thread(chat_id, assistant_manager)

        try:
            # Получаем ответ от Ассистента с передачей chat_id для сохранения истории
            response = await assistant_manager.get_response(thread_id, text, chat_id=chat_id)
            logger.info(f"📨 [AI_RESPONSE] Получен ответ от AI: {response}")
            logger.info(f"✅ Получен ответ от Ассистента ({len(response)} символов)")

            # Определяем тип ответа
            response_type, parsed_data = detect_response_type(response)
            logger.info(f"🔍 [AI_RESPONSE] Тип ответа: {response_type}, Parsed data: {parsed_data}")

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

                    # Сохраняем детали в user_data
                    update_user_data(chat_id, {
                        "callback_details": callback_details,
                        "request_type": "callback"
                    })

                    # Переходим к сбору контактов
                    set_state(chat_id, WhatsAppState.WAITING_FOR_NAME)

                    return (
                        "✅ Отлично! Я передам ваш запрос менеджеру.\n\n"
                        "📝 Шаг 1/2: Введите ваше имя"
                    )

                # ============================================================
                # СУЩЕСТВУЮЩИЙ СЦЕНАРИЙ: ORDER (Заказ товара)
                # ============================================================
                elif intent == "ORDER" or "category" in parsed_data:
                    logger.info(f"🛒 [ORDER] Обнаружен JSON с намерением заказа")

                    order_data = extract_order_data(parsed_data)

                    # Извлекаем данные
                    category = order_data.get("category")
                    brand = order_data.get("brand")
                    model = order_data.get("model")

                    # КРИТИЧЕСКАЯ ПРОВЕРКА: AI Assistant ОБЯЗАН вернуть category!
                    if not category:
                        logger.error(f"❌ [AI_RESPONSE] AI Assistant не вернул category в ORDER JSON!")
                        logger.error(f"❌ [AI_RESPONSE] order_data: {order_data}")
                        return "❌ Ошибка: не удалось определить категорию товара. Попробуйте ещё раз."

                    # Устанавливаем начальное состояние для сценария ORDER
                    if brand and model:
                        # Есть и марка и модель - запускаем поиск лекал
                        logger.info(f"📋 Запуск поиска лекал: {brand} {model}")

                        # Сохраняем данные в состояние
                        category_name = get_category_name(category, tenant_config.i18n)
                        logger.info(f"🏷️  [CATEGORY_FIX] category={category} -> category_name={category_name}")

                        update_user_data(chat_id, {
                            "category": category,
                            "category_name": category_name,
                            "brand_name": brand,
                            "model_name": model
                        })

                        # Устанавливаем состояние ожидания модели (для корректного флоу)
                        set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)

                        # Запускаем поиск лекал
                        logger.info(f"🚀 [FSM_START] Запуск поиска лекал для {brand} {model} (category: {category})")
                        return await whatsapp_handlers.search_patterns_for_model(
                            chat_id, model, brand, category, tenant_config, session
                        )

                    elif brand:
                        # Есть только марка - показываем модели
                        logger.info(f"📋 Показываем модели для марки: {brand}")

                        category_name = get_category_name(category, tenant_config.i18n)
                        logger.info(f"🏷️  [CATEGORY_FIX] category={category} -> category_name={category_name}")

                        update_user_data(chat_id, {
                            "category": category,
                            "category_name": category_name,
                            "brand_name": brand
                        })

                        set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)

                        return await whatsapp_handlers.show_models_page(chat_id, 1, brand, tenant_config, session)

                    else:
                        # Намерение заказа есть, но данных недостаточно - показываем меню
                        logger.info("⚠️ Намерение заказа без марки/модели - показываем меню")
                        return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)

            else:
                # Текстовый ответ (FAQ) - форматируем для WhatsApp и отправляем
                logger.info("📝 Текстовый ответ (FAQ)")
                formatted_response = format_response_for_platform(response, "whatsapp")
                return formatted_response

        except Exception as e:
            logger.error(f"❌ Ошибка при обращении к Ассистенту: {e}")

            # Fallback: показываем главное меню
            return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)

    # Главное меню - проверяем, является ли это IVR-командой
    elif current_state == WhatsAppState.MAIN_MENU:
        if is_ivr_command(text, current_state):
            # Ожидаемая цифра 1-5 - обрабатываем через IVR
            return await whatsapp_handlers.handle_main_menu_choice(chat_id, text, tenant_config, session)
        else:
            # Свободный текст (например, "кто ты?", "какая гарантия?") - передаем в AI
            logger.info(f"🤖 Main menu: unexpected text '{text}' - routing to AI Assistant")
            logger.info("=" * 60)
            logger.info("🤖 *** AI HANDLER TRIGGERED *** 🤖")
            logger.info("=" * 60)

            # Получаем или создаем thread для пользователя
            thread_id = get_or_create_thread(chat_id, assistant_manager)

            try:
                # Получаем ответ от Ассистента с передачей chat_id для сохранения истории
                response = await assistant_manager.get_response(thread_id, text, chat_id=chat_id)
                logger.info(f"✅ Получен ответ от Ассистента ({len(response)} символов)")

                # Определяем тип ответа
                response_type, parsed_data = detect_response_type(response)

                if response_type == "json" and parsed_data:
                    # JSON ответ с намерением заказа - запускаем FSM сценарий
                    logger.info(f"🎯 Обнаружен JSON с намерением заказа: {parsed_data}")

                    order_data = extract_order_data(parsed_data)

                    # Извлекаем данные
                    category = order_data.get("category")
                    brand = order_data.get("brand")
                    model = order_data.get("model")

                    # КРИТИЧЕСКАЯ ПРОВЕРКА: AI Assistant ОБЯЗАН вернуть category!
                    if not category:
                        logger.error(f"❌ [AI_RESPONSE] AI Assistant не вернул category в ORDER JSON!")
                        logger.error(f"❌ [AI_RESPONSE] order_data: {order_data}")
                        return "❌ Ошибка: не удалось определить категорию товара. Попробуйте ещё раз."

                    if brand and model:
                        # Есть и марка и модель - запускаем поиск лекал
                        logger.info(f"📋 Запуск поиска лекал: {brand} {model}")

                        # Сохраняем данные в состояние
                        category_name = get_category_name(category, tenant_config.i18n)
                        logger.info(f"🏷️  [CATEGORY_FIX] category={category} -> category_name={category_name}")

                        update_user_data(chat_id, {
                            "category": category,
                            "category_name": category_name,
                            "brand_name": brand,
                            "model_name": model
                        })

                        # Устанавливаем состояние ожидания модели (для корректного флоу)
                        set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)

                        # Запускаем поиск лекал
                        return await whatsapp_handlers.search_patterns_for_model(
                            chat_id, model, brand, category, tenant_config, session
                        )

                    elif brand:
                        # Есть только марка - показываем модели
                        logger.info(f"📋 Показываем модели для марки: {brand}")

                        category_name = get_category_name(category, tenant_config.i18n)
                        logger.info(f"🏷️  [CATEGORY_FIX] category={category} -> category_name={category_name}")

                        update_user_data(chat_id, {
                            "category": category,
                            "category_name": category_name,
                            "brand_name": brand
                        })

                        set_state(chat_id, WhatsAppState.EVA_WAITING_MODEL)

                        return await whatsapp_handlers.show_models_page(chat_id, 1, brand, tenant_config, session)

                    else:
                        # Намерение заказа есть, но данных недостаточно - показываем меню
                        logger.info("⚠️ Намерение заказа без марки/модели - показываем меню")
                        return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)

                else:
                    # Текстовый ответ (FAQ) - форматируем для WhatsApp и отправляем
                    logger.info("📝 Текстовый ответ (FAQ)")
                    formatted_response = format_response_for_platform(response, "whatsapp")
                    return formatted_response

            except Exception as e:
                logger.error(f"❌ Ошибка при обращении к Ассистенту: {e}")

                # Fallback: показываем главное меню
                return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)

    # EVA-коврики: ожидание марки
    elif current_state == WhatsAppState.EVA_WAITING_BRAND:
        # Проверяем, это ответ на fuzzy suggestion или обычный ввод
        user_data = get_user_data(chat_id)

        if "suggested_brand" in user_data and text in ["1", "2"]:
            if text == "1":
                # Используем предложенную марку
                suggested_brand = user_data["suggested_brand"]
                # Очищаем suggestion из user_data
                update_user_data(chat_id, {"suggested_brand": None})
                return await whatsapp_handlers.handle_eva_brand_input(chat_id, suggested_brand, tenant_config, session)
            else:
                # Очищаем suggestion и показываем текущую страницу заново
                update_user_data(chat_id, {"suggested_brand": None})
                current_page = user_data.get("brands_page", 1)
                return await whatsapp_handlers.show_brands_page(chat_id, current_page, tenant_config, session)
        else:
            # Обычный ввод марки
            return await whatsapp_handlers.handle_eva_brand_input(chat_id, text, tenant_config, session)

    # EVA-коврики: ожидание модели
    elif current_state == WhatsAppState.EVA_WAITING_MODEL:
        # Проверяем, это ответ на fuzzy suggestion или обычный ввод
        user_data = get_user_data(chat_id)

        if "suggested_model" in user_data and text in ["1", "2"]:
            if text == "1":
                # Используем предложенную модель
                suggested_model = user_data["suggested_model"]
                # Очищаем suggestion из user_data
                update_user_data(chat_id, {"suggested_model": None})
                return await whatsapp_handlers.handle_eva_model_input(chat_id, suggested_model, tenant_config, session)
            else:
                # Очищаем suggestion и показываем текущую страницу заново
                update_user_data(chat_id, {"suggested_model": None})
                brand_name = user_data.get("brand_name", "")
                current_page = user_data.get("models_page", 1)
                return await whatsapp_handlers.show_models_page(chat_id, current_page, brand_name, tenant_config, session)
        else:
            # Обычный ввод модели
            return await whatsapp_handlers.handle_eva_model_input(chat_id, text, tenant_config, session)

    # EVA-коврики: выбор опций (С бортами / Без бортов)
    elif current_state == WhatsAppState.EVA_SELECTING_OPTIONS:
        return await whatsapp_handlers.handle_option_selection(chat_id, text, tenant_config, session)

    # EVA-коврики: подтверждение заказа
    elif current_state == WhatsAppState.EVA_CONFIRMING_ORDER:
        logger.info(f"🎯 [ROUTE] EVA_CONFIRMING_ORDER state - calling handle_order_confirmation with text: '{text}'")
        return await whatsapp_handlers.handle_order_confirmation(chat_id, text, tenant_config)

    # Сбор контактов: ожидание имени
    elif current_state == WhatsAppState.WAITING_FOR_NAME:
        return await whatsapp_handlers.handle_name_input(chat_id, text, tenant_config, session)  # ✅ Передаём session!

    # Сбор контактов: ожидание телефона
    elif current_state == WhatsAppState.WAITING_FOR_PHONE:
        return await whatsapp_handlers.handle_phone_input(chat_id, text, tenant_config)

    # Связь с менеджером
    elif current_state == WhatsAppState.CONTACT_MANAGER:
        # Возвращаем в меню
        return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)

    # Неизвестное состояние - сбрасываем в главное меню
    else:
        logger.warning(f"Unknown state: {current_state}, resetting to main menu")
        return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)


# ============================================================================
# HEALTH CHECK & STARTUP
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "WhatsApp Gateway",
        "version": "1.0.0",
        "active_tenants": len(TENANT_INSTANCES)
    }





# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Запускаем сервер
    port = int(os.getenv("WHATSAPP_GATEWAY_PORT", "8000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload при изменениях (для разработки)
        log_level="info"
    )
