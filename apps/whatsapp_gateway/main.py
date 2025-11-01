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
from .state_manager import get_state, get_user_data, WhatsAppState, set_state, update_user_data, clear_thread_id
from . import whatsapp_handlers
from . import agent_manager  # НОВЫЙ АГЕНТНЫЙ МЕНЕДЖЕР

# Импортируем модульные обработчики для каждого арендатора
from .tenant_handlers import evopoliki_handler, five_deluxe_handler

# Глобальный словарь AssistantManager для каждого tenant
# Формат: {tenant_slug: AssistantManager}
tenant_assistant_managers: Dict[str, AssistantManager] = {}

# ============================================================================
# TENANT HANDLERS DISPATCHER
# ============================================================================

# Диспетчер обработчиков меню для каждого арендатора
# Ключ: tenant_slug, Значение: функция-обработчик
TENANT_MENU_HANDLERS = {
    'evopoliki': evopoliki_handler.handle_evopoliki_menu,
    'five_deluxe': five_deluxe_handler.handle_5deluxe_menu,
}

# Диспетчер обработчиков сообщений для каждого арендатора
TENANT_MESSAGE_HANDLERS = {
    'evopoliki': None,  # evopoliki использует общие обработчики
    'five_deluxe': five_deluxe_handler.handle_5deluxe_message,
}

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
# DATABASE SESSION DEPENDENCY
# ============================================================================

async def get_session():
    """
    Dependency для получения сессии БД.
    Используется в FastAPI endpoints через Depends(get_session).
    """
    if db_session_factory is None:
        raise RuntimeError(
            "База данных не инициализирована. "
            "Приложение еще не запущено."
        )

    async with db_session_factory() as session:
        yield session


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

    async def send_interactive_list(
        self,
        chat_id: str,
        header: str,
        body: str,
        footer: str,
        button_text: str,
        sections: list
    ) -> bool:
        """
        Отправляет интерактивный список в WhatsApp через GreenAPI.

        Args:
            chat_id: ID чата (номер телефона в формате 79001234567@c.us)
            header: Заголовок сообщения
            body: Основной текст
            footer: Нижний текст (footer)
            button_text: Текст кнопки открытия списка
            sections: Список секций с элементами [{"title": "...", "rows": [...]}]

        Returns:
            True если успешно отправлено, False если ошибка
        """
        url = f"{self.base_url}/sendMessage/{self.tenant_config.api_token}"

        payload = {
            "chatId": chat_id,
            "message": {
                "text": body
            },
            "quotedMessageId": None,
            "linkPreview": False
        }

        # GreenAPI использует простые кнопки (buttons) для списков
        # Конвертируем sections в простой текст с нумерацией
        # Так как GreenAPI не поддерживает interactive lists в бесплатной версии
        # Используем текстовое меню с улучшенным форматированием

        message_parts = [f"*{header}*", "", body, ""]

        for section in sections:
            section_title = section.get("title", "")
            rows = section.get("rows", [])

            message_parts.append(f"*{section_title}*")

            for idx, row in enumerate(rows, 1):
                title = row.get("title", "")
                description = row.get("description", "")
                message_parts.append(f"{idx}️⃣ {title}")
                if description:
                    message_parts.append(f"   _{description}_")

            message_parts.append("")  # Пустая строка между секциями

        if footer:
            message_parts.append(f"_{footer}_")

        formatted_message = "\n".join(message_parts)

        payload["message"]["text"] = formatted_message

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)

                if response.status_code == 200:
                    logger.info(f"✅ Interactive list sent to {chat_id}")
                    return True
                else:
                    logger.error(f"❌ Failed to send interactive list: {response.status_code} - {response.text}")
                    # Fallback - отправляем как обычное сообщение
                    return await self.send_message(chat_id, formatted_message)

        except Exception as e:
            logger.error(f"❌ Exception while sending interactive list: {e}")
            # Fallback - отправляем как обычное сообщение
            return await self.send_message(chat_id, formatted_message)

    async def send_menu_response(self, chat_id: str, menu_data: Dict[str, Any]) -> bool:
        """
        Универсальный метод отправки ответа с меню.

        Автоматически определяет тип сообщения и вызывает нужный метод.

        Args:
            chat_id: ID чата WhatsApp
            menu_data: Данные меню от обработчика (dict с type и данными)

        Returns:
            True если успешно отправлено, False если ошибка
        """
        message_type = menu_data.get("type", "text")

        if message_type == "interactive_list":
            # Отправляем как интерактивный список
            return await self.send_interactive_list(
                chat_id=chat_id,
                header=menu_data.get("header", ""),
                body=menu_data.get("body", ""),
                footer=menu_data.get("footer", ""),
                button_text=menu_data.get("button_text", "Открыть меню"),
                sections=menu_data.get("sections", [])
            )
        else:
            # Отправляем как обычное текстовое сообщение
            return await self.send_message(chat_id, menu_data.get("message", ""))


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
    Обрабатывает входящее сообщение от пользователя WhatsApp через AI Agent.

    НОВАЯ АРХИТЕКТУРА (Agent-First):
    - Все сообщения обрабатываются через AI Agent
    - AI Agent сам вызывает нужные инструменты
    - Нет машины состояний - весь диалог контролирует AI

    Args:
        tenant_slug: Идентификатор tenant (evopoliki, five_deluxe)
        message_data: Данные сообщения из вебхука
        sender_data: Данные отправителя из вебхука
        session: AsyncSession для работы с БД
    """
    try:
        # ═══════════════════════════════════════════════════════════════════
        # ШАГ 1: Извлекаем данные из вебхука
        # ═══════════════════════════════════════════════════════════════════
        type_message = message_data.get("typeMessage")
        text_message = message_data.get("textMessageData", {}).get("textMessage", "")
        chat_id = sender_data.get("chatId")
        sender_name = sender_data.get("senderName", "Гость")

        logger.info(f"💬 [INCOMING] Message from {sender_name} ({chat_id}): '{text_message}'")

        # Загружаем конфигурацию tenant
        tenant_config = TenantConfig(tenant_slug)

        if not tenant_config.is_valid():
            logger.error(f"❌ [INCOMING] Invalid tenant config for {tenant_slug}")
            return

        # ═══════════════════════════════════════════════════════════════════
        # ШАГ 2: Обработка команды "Меню" - сброс Thread
        # ═══════════════════════════════════════════════════════════════════
        if text_message.lower() in ["меню", "menu", "/start", "start"]:
            logger.info(f"🔄 [MENU] Команда 'Меню' - сброс Thread для {chat_id}")

            # Очищаем Thread (начинаем диалог заново)
            clear_thread_id(chat_id)

            # Очищаем историю в memory (если используется)
            try:
                memory = get_memory()
                memory.clear_history(chat_id)
                logger.info(f"🗑️ [MEMORY] История очищена для {chat_id}")
            except Exception as e:
                logger.warning(f"⚠️ [MEMORY] Ошибка очистки истории: {e}")

        # ═══════════════════════════════════════════════════════════════════
        # ШАГ 3: Вызываем AI Agent для обработки сообщения
        # ═══════════════════════════════════════════════════════════════════
        logger.info(f"🤖 [AGENT] Передаю сообщение в AI Agent...")

        response = await agent_manager.process_message_with_agent(
            client=tenant_config.openai_client,
            assistant_id=tenant_config.assistant_manager.assistant_id,
            chat_id=chat_id,
            text=text_message,
            tenant_id=tenant_config.TENANT_ID,
            session=session
        )

        logger.info(f"✅ [AGENT] Получен ответ от AI: '{response[:100]}...'")

        # ═══════════════════════════════════════════════════════════════════
        # ШАГ 4: Отправляем ответ пользователю
        # ═══════════════════════════════════════════════════════════════════
        client = GreenAPIClient(tenant_config)
        await client.send_message(chat_id, response)

        logger.info(f"✅ [INCOMING] Ответ отправлен {sender_name} ({chat_id})")

    except Exception as e:
        logger.error(f"❌ [INCOMING] КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)

        # Отправляем fallback-сообщение пользователю
        try:
            tenant_config = TenantConfig(tenant_slug)
            if tenant_config.is_valid():
                client = GreenAPIClient(tenant_config)
                await client.send_message(
                    chat_id,
                    "Произошла техническая ошибка. Пожалуйста, попробуйте еще раз или напишите 'Меню'."
                )
        except Exception as fallback_error:
            logger.error(f"❌ [INCOMING] Ошибка отправки fallback-сообщения: {fallback_error}")


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


def is_likely_question(text: str) -> bool:
    """
    Определяет, является ли текст вопросом (для гибридной системы).

    Если текст похож на вопрос, его нужно отправить на AI вместо обработки как команду.

    Args:
        text: Текст сообщения

    Returns:
        True если это вопрос, False если это команда
    """
    text_lower = text.lower().strip()

    # Явный признак вопроса: знак "?"
    if "?" in text_lower:
        return True

    # Вопросительные слова
    question_words = [
        "какие", "какая", "какой", "какое",
        "что", "чего", "чему", "чем", "чём",
        "как", "сколько", "почему", "зачем",
        "где", "куда", "откуда",
        "когда", "кто", "кого", "кому", "кем",
        "можно ли", "есть ли", "может ли",
        "а если", "а что",
    ]

    # Проверяем начало предложения (первые слова)
    first_words = text_lower.split()[:3]  # Берем первые 3 слова
    for word in first_words:
        if any(qw in word for qw in question_words):
            return True

    # Длинные сообщения (>50 символов) с несколькими словами - вероятно вопросы
    if len(text) > 50 and len(text.split()) > 7:
        return True

    return False


async def get_and_handle_ai_response(
    chat_id: str,
    text: str,
    tenant_config: Config,
    session: AsyncSession
) -> str:
    """
    Получает ответ от AI и обрабатывает его (JSON или текст).

    Используется в гибридной системе когда IVR-обработчик не справился
    или когда обнаружен вопрос вместо команды.

    Args:
        chat_id: ID чата
        text: Текст сообщения
        tenant_config: Конфигурация tenant
        session: Сессия БД

    Returns:
        Обработанный ответ (текст или результат JSON-команды)
    """
    logger.info("=" * 80)
    logger.info(f"🧠 [AI_HANDLER] === НАЧАЛО ОБРАБОТКИ AI ЗАПРОСА ===")
    logger.info(f"🧠 [AI_HANDLER] Chat ID: {chat_id}")
    logger.info(f"🧠 [AI_HANDLER] Получен запрос для AI: '{text}'")
    logger.info("=" * 80)

    try:
        # Получаем или создаем thread для AI
        thread_id = get_or_create_thread(chat_id, assistant_manager)
        logger.info(f"🧠 [AI_HANDLER] Thread ID: {thread_id}")

        # Получаем ответ от AI
        logger.info(f"🧠 [AI_HANDLER] Отправляем запрос к OpenAI Assistant...")
        response = await assistant_manager.get_response(thread_id, text, chat_id=chat_id)
        logger.info(f"🧠 [AI_HANDLER] ✅ AI вернул ответ (длина: {len(response)} символов)")
        logger.info(f"🧠 [AI_HANDLER] Первые 200 символов ответа: {response[:200]}...")

        # Проверяем тип ответа (JSON или текст)
        response_type, parsed_data = detect_response_type(response)
        logger.info(f"🔍 [AI_HANDLER] Тип ответа: {response_type}")

        if response_type == "json" and parsed_data:
            intent = parsed_data.get("intent", "order").upper()
            logger.info(f"🎯 [AI_HANDLER] Обнаружен JSON с намерением: {intent}")

            # Обработка SHOW_CATALOG / SHOW_MAIN_MENU
            if intent in ["SHOW_CATALOG", "SHOW_MAIN_MENU"]:
                logger.info("🏠 [AI_HANDLER] Показываем главное меню")
                return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)

            # Обработка ORDER - НОВАЯ ГИБРИДНАЯ ЛОГИКА
            elif intent == "ORDER":
                logger.info(f"🛒 [AI_HANDLER] Обнаружен JSON с намерением ORDER")

                order_data = extract_order_data(parsed_data)
                category = order_data.get("category")
                brand = order_data.get("brand")
                model = order_data.get("model")

                logger.info(f"🧠 [AI_HANDLER] AI извлек: category={category}, brand={brand}, model={model}")

                # СЦЕНАРИЙ: AI не понял категорию → Показываем меню категорий
                if not category:
                    logger.info("🎯 [AI_HANDLER] Категория не распознана → Показываем главное меню")
                    return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)

                category_name = get_category_name(category, tenant_config.i18n)

                # Сохраняем ВСЕ распознанные данные
                update_user_data(chat_id, {
                    "category": category,
                    "category_name": category_name,
                    "brand_name": brand if brand else None,
                    "model_name": model if model else None
                })

                # Устанавливаем состояние AI_CONFIRMING_ORDER
                set_state(chat_id, WhatsAppState.AI_CONFIRMING_ORDER)

                # Формируем текстовый ответ с предложением продолжить
                if brand and model:
                    # Полные данные
                    response_text = (
                        f"Да, конечно! Мы можем изготовить {category_name} для {brand} {model}.\n\n"
                        f"Чтобы продолжить, нажмите 1 или напишите Да."
                    )
                elif brand:
                    # Только марка
                    response_text = (
                        f"Да, конечно! Мы можем изготовить {category_name} для {brand}.\n\n"
                        f"Чтобы продолжить к выбору модели, нажмите 1 или напишите Да."
                    )
                else:
                    # Только категория
                    response_text = (
                        f"Да, конечно! У нас есть {category_name}.\n\n"
                        f"Чтобы продолжить к выбору марки, нажмите 1 или напишите Да."
                    )

                logger.info(f"✅ [AI_HANDLER] Переход в AI_CONFIRMING_ORDER, ожидаем подтверждение")
                return response_text

            # Обработка CALLBACK_REQUEST
            elif intent == "CALLBACK_REQUEST":
                logger.info("📞 [AI_HANDLER] Обработка запроса обратного звонка")
                set_state(chat_id, WhatsAppState.WAITING_FOR_NAME)
                return await whatsapp_handlers.handle_callback_request(chat_id, tenant_config)

        # Если это обычный текстовый ответ (FAQ)
        logger.info("📝 [AI_HANDLER] Это текстовый ответ, форматируем для WhatsApp")
        formatted_response = format_response_for_platform(response, "whatsapp")
        logger.info(f"🧠 [AI_HANDLER] === КОНЕЦ ОБРАБОТКИ (успешно) ===")
        return formatted_response

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"💥 [AI_HANDLER] === ОШИБКА ПРИ ОБРАЩЕНИИ К AI ===")
        logger.error(f"💥 [AI_HANDLER] Ошибка: {type(e).__name__}")
        logger.error(f"💥 [AI_HANDLER] Сообщение: {str(e)}")
        logger.error("=" * 80)

        # Fallback: показываем главное меню
        logger.info(f"🔄 [AI_HANDLER] Fallback: возвращаем в главное меню")
        return await whatsapp_handlers.handle_start_message(chat_id, tenant_config)


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
    elif state == WhatsAppState.WAITING_FOR_NAME:
        return True

    # Для всех остальных состояний - не IVR-команда
    return False


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "WhatsApp Gateway",
        "version": "1.0.0",
        "active_tenants": len(TENANT_INSTANCES)
    }


@app.get("/debug/tenants")
async def debug_tenants():
    """Debug endpoint to show tenant instance mapping."""
    return {
        "status": "ok",
        "tenant_instances": TENANT_INSTANCES,
        "note": "instance_id -> tenant_slug mapping"
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
