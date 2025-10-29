"""
Конфигурация Telegram-бота с изоляцией тенантов.
Каждый экземпляр Config полностью независим.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class I18nInstance:
    """
    Изолированный экземпляр системы локализации.

    Каждый бот имеет свой собственный экземпляр i18n,
    который не влияет на другие боты.
    """

    def __init__(self, tenant_slug: str, language: str = "ru"):
        """
        Args:
            tenant_slug: Идентификатор клиента (evopoliki, five_deluxe)
            language: Код языка по умолчанию (ru, ky)
        """
        self.tenant_slug = tenant_slug
        self.language = language
        self._texts: Dict[str, Any] = {}
        self._load_texts()

    def _load_texts(self):
        """Загружает тексты из JSON файла."""
        # Путь к файлу локализации
        locales_dir = Path(__file__).parent / "locales"
        locale_file = locales_dir / self.tenant_slug / f"{self.language}.json"

        if not locale_file.exists():
            raise FileNotFoundError(
                f"Locale file not found: {locale_file}\n"
                f"Please create locales/{self.tenant_slug}/{self.language}.json"
            )

        with open(locale_file, 'r', encoding='utf-8') as f:
            self._texts = json.load(f)

    def set_language(self, language: str):
        """
        Изменяет язык интерфейса.

        Args:
            language: Код языка (ru, ky)
        """
        self.language = language
        self._load_texts()

    def get(self, key: str, **kwargs) -> str:
        """
        Получает текст по ключу с поддержкой вложенных ключей.

        Args:
            key: Ключ текста (может быть вложенным, например "faq.care.question")
            **kwargs: Параметры для форматирования строки

        Returns:
            Локализованный текст

        Examples:
            >>> i18n.get("welcome_message")
            >>> i18n.get("faq.care.question")
            >>> i18n.get("greeting", name="Иван")
        """
        # Поддержка вложенных ключей через точку
        keys = key.split('.')
        value = self._texts

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                break

        if value is None:
            return f"[Missing translation: {key}]"

        # Форматирование строки если есть параметры
        if kwargs and isinstance(value, str):
            try:
                return value.format(**kwargs)
            except KeyError as e:
                return f"[Format error in {key}: {e}]"

        return value

    @property
    def current_language(self) -> str:
        """Возвращает текущий язык."""
        return self.language

    @property
    def current_tenant(self) -> str:
        """Возвращает текущий tenant_slug."""
        return self.tenant_slug


@dataclass
class DatabaseConfig:
    """Конфигурация базы данных PostgreSQL."""

    host: str
    port: int
    name: str
    user: str
    password: str

    @property
    def async_url(self) -> str:
        """URL для асинхронного подключения (asyncpg)."""
        if self.password:
            return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        else:
            return f"postgresql+asyncpg://{self.user}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        """URL для синхронного подключения (psycopg2)."""
        if self.password:
            return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        else:
            return f"postgresql+psycopg2://{self.user}@{self.host}:{self.port}/{self.name}"


@dataclass
class AirtableConfig:
    """Конфигурация Airtable для сохранения заявок."""

    api_key: str
    base_id: str
    table_name: str


@dataclass
class BotConfig:
    """Конфигурация Telegram-бота с встроенным i18n."""

    token: str
    tenant_slug: str
    i18n: I18nInstance
    default_language: str = "ru"
    admin_ids: list[int] = field(default_factory=list)
    group_chat_id: Optional[int] = None
    instagram_url: str = ""
    enable_dialog_mode: bool = False
    openai_api_key: Optional[str] = None
    openai_assistant_id: Optional[str] = None


@dataclass
class Config:
    """Изолированная конфигурация для одного бота."""

    bot: BotConfig
    database: DatabaseConfig
    airtable: Optional[AirtableConfig] = None
    debug: bool = False


def create_config(env_path: Optional[Path] = None, tenant_slug: Optional[str] = None) -> Config:
    """
    Создает ИЗОЛИРОВАННЫЙ экземпляр конфигурации.

    ВАЖНО: Каждый вызов создает НОВЫЙ независимый экземпляр,
    который не влияет на другие боты.

    Args:
        env_path: Путь к .env файлу (если None, используется текущая директория)
        tenant_slug: Идентификатор клиента (tenant)

    Returns:
        Config: Изолированный объект конфигурации

    Raises:
        ValueError: Если обязательные переменные не установлены
    """
    # Загружаем переменные окружения из указанного файла
    if env_path:
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    # Получаем tenant_slug: приоритет у переданного параметра, затем env
    # КРИТИЧЕСКИ ВАЖНО: параметр должен иметь приоритет над env для multi-tenant
    _tenant_slug = tenant_slug or os.getenv("TENANT_SLUG", "default")

    # Проверяем обязательные переменные
    # Сначала пытаемся загрузить tenant-специфичный токен
    tenant_prefix = _tenant_slug.upper().replace("-", "_")
    bot_token = os.getenv(f"{tenant_prefix}_BOT_TOKEN")

    # Fallback на общий BOT_TOKEN (для обратной совместимости)
    if not bot_token:
        bot_token = os.getenv("BOT_TOKEN")

    if not bot_token:
        raise ValueError(
            f"BOT_TOKEN не установлен для tenant '{_tenant_slug}'. "
            f"Установите {tenant_prefix}_BOT_TOKEN или BOT_TOKEN."
        )

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_name = os.getenv("DB_NAME", "car_chatbot")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "")

    # Загружаем опциональные переменные
    debug = os.getenv("DEBUG", "false").lower() == "true"
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

    # Group Chat ID для отправки заявок
    group_chat_id_str = os.getenv("GROUP_CHAT_ID", "")
    group_chat_id = int(group_chat_id_str) if group_chat_id_str else None

    # Instagram URL
    instagram_url = os.getenv("INSTAGRAM_URL", "")

    # ========================================================================
    # ENABLE DIALOG MODE (AI-powered responses)
    # ========================================================================
    # Читаем tenant-специфичную переменную для dialog mode с fallback chain
    tenant_prefix = _tenant_slug.upper().replace("-", "_")

    # Fallback chain: tenant-specific -> global -> default false
    enable_dialog_mode_str = (
        os.getenv(f"{tenant_prefix}_ENABLE_DIALOG_MODE") or
        os.getenv("ENABLE_DIALOG_MODE") or
        "false"
    )
    enable_dialog_mode = str(enable_dialog_mode_str).strip().lower() in ("true", "1", "yes")

    # ========================================================================
    # ДИНАМИЧЕСКАЯ ЗАГРУЗКА OPENAI CREDENTIALS ПО TENANT
    # ========================================================================
    # Формируем имена переменных окружения с использованием tenant_slug
    # Пример: для "evopoliki" -> "EVOPOLIKI_OPENAI_API_KEY"
    #         для "five_deluxe" -> "FIVE_DELUXE_OPENAI_API_KEY"

    tenant_prefix = _tenant_slug.upper().replace("-", "_")

    # Пытаемся загрузить tenant-специфичные переменные
    openai_api_key = os.getenv(f"{tenant_prefix}_OPENAI_API_KEY")
    openai_assistant_id = os.getenv(f"{tenant_prefix}_OPENAI_ASSISTANT_ID")

    # Fallback на общие переменные (для обратной совместимости)
    if not openai_api_key:
        openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_assistant_id:
        openai_assistant_id = os.getenv("OPENAI_ASSISTANT_ID")

    # ========================================================================
    # AIRTABLE CONFIGURATION
    # ========================================================================
    # Читаем переменные для Airtable (для сохранения заявок)
    airtable_api_key = os.getenv("AIRTABLE_API_KEY")
    airtable_base_id = os.getenv("AIRTABLE_BASE_ID")
    airtable_table_name = os.getenv("AIRTABLE_TABLE_NAME", "Заявки с ботов")

    # Создаем конфигурацию Airtable если все переменные присутствуют
    airtable_config = None
    if airtable_api_key and airtable_base_id:
        airtable_config = AirtableConfig(
            api_key=airtable_api_key,
            base_id=airtable_base_id,
            table_name=airtable_table_name
        )

    # ========================================================================

    # Создаем ИЗОЛИРОВАННЫЙ экземпляр i18n для этого бота
    i18n_instance = I18nInstance(tenant_slug=_tenant_slug, language="ru")

    # Логирование конфигурации (для диагностики multi-tenant изоляции)
    logger.info(f"[create_config] tenant={_tenant_slug}")
    logger.info(f"[create_config] enable_dialog_mode={enable_dialog_mode_str!r} -> {enable_dialog_mode}")
    logger.info(f"[create_config] openai_configured={bool(openai_api_key and openai_assistant_id)}")

    return Config(
        bot=BotConfig(
            token=bot_token,
            tenant_slug=_tenant_slug,
            i18n=i18n_instance,
            default_language="ru",
            admin_ids=admin_ids,
            group_chat_id=group_chat_id,
            instagram_url=instagram_url,
            enable_dialog_mode=enable_dialog_mode,
            openai_api_key=openai_api_key,
            openai_assistant_id=openai_assistant_id
        ),
        database=DatabaseConfig(
            host=db_host,
            port=db_port,
            name=db_name,
            user=db_user,
            password=db_password
        ),
        airtable=airtable_config,
        debug=debug
    )
